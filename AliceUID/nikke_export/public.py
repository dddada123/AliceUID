"""Read an explicitly shared profile using only the command sender's login.

Target IDs live in request bodies, never in saved bindings or owner snapshots.
Public exports are ephemeral; visibility and target role are rechecked for delivery.
"""
import time
from types import SimpleNamespace
from urllib.parse import urlencode
from ..nikke_api.client import REGIONS, HMT_REGION, NikkeClient
from ..nikke_character.service import CharacterQueryService
from ..nikke_roster.service import account_reads
from .model import ExportError

class PublicReader:
    def __init__(self, owner, share, check):
        self.owner, self.share, self.check = owner, share, check
        self.region = owner.region
        self.area = None

    async def request(self, path, body=None, method='POST'):
        if not await self.check():
            raise ExportError('绑定或权限已变化，已停止读取公开资料。')
        if self.area is not None and isinstance(self.owner, NikkeClient):
            return await self.owner._request(method, path, body, region=self.region)
        return await self.owner._request(method, path, body)

    async def get_privacy(self):
        data = await self.request('/api/ugc/direct/standalonesite/User/GetUserPrivacySetting', {'intl_openid': self.share})
        privacy = data.get('data')
        if not isinstance(privacy, dict) or privacy.get('show_nikke_info') != 1:
            raise ExportError('目标用户未公开妮姬信息，请先在 Blablalink 隐私设置中公开。')
        return privacy

    async def get_role(self):
        data = await self.request('/api/game/proxy/Tools/GetUserSavedRoleInfo?' + urlencode({'uid': self.share}), method='GET')
        payload = data.get('data') or {}
        if payload.get('is_banned') or payload.get('is_maintenance'):
            raise ExportError('目标资料当前不可访问或处于维护中。')
        role = payload.get('role_info')
        if payload.get('has_saved_role_info') is False:
            raise ExportError('目标尚未在 Blablalink 选择游戏角色，请检查社区角色设置。')
        if not isinstance(role, dict) or not (role.get('role_id') or role.get('role_name')):
            raise ExportError('社区未返回可识别的目标游戏角色，无法确定资料归属。')
        area = str(role.get('area_id', ''))
        if not area.isascii() or not area.isdecimal():
            raise ExportError('社区未返回有效目标区服，无法读取公开练度。')
        region = HMT_REGION if area == '91' else REGIONS.get(int(area))
        if (region is None or region.game_id != self.share.split('-')[0]
                or (role.get('game_id') and str(role['game_id']) != region.game_id)):
            raise ExportError('目标用户的游戏或区服信息不匹配。')
        self.area, self.region = region.area_id, region
        return role

    async def get_game(self, endpoint, codes=None):
        body = dict(intl_open_id=self.share.split('-')[1], nikke_area_id=self.area)
        if codes is not None:
            body['name_codes'] = codes
        data = await self.request('/api/game/proxy/Game/' + endpoint, body)
        value = data.get('data')
        if not isinstance(value, dict):
            raise ExportError('公开资料响应不完整，未生成练度文件。')
        return value

async def fetch_public(client, bind, share, check):
    if share.split('-')[0] != str(bind.game_id):
        raise ExportError('跨游戏版本的公开查询需要登录对应国际版或港澳台版账号。')
    reader = PublicReader(client, share, check)
    async def read(name, *args):
        async with account_reads.transaction(reader, bind, wait=True) as paced:
            return await getattr(paced, name)(*args)
    privacy = await read('get_privacy')
    role = await read('get_role')
    roster = (await read('get_game', 'GetUserCharacters')).get('characters')
    codes = CharacterQueryService.roster_codes(roster)
    if not codes or len(codes) > 500:
        raise ExportError('目标用户没有可导出的已拥有角色，或角色数量超出上限。')
    details = {}
    for start in range(0, len(codes), 20):
        batch = codes[start:start + 20]
        payload = await read('get_game', 'GetUserCharacterDetails', batch)
        details.update(CharacterQueryService.detail_entries(payload, batch))
    outpost = {}
    if privacy.get('show_outpost_info') == 1:
        outpost = (await read('get_game', 'GetUserProfileOutpostInfo')).get('outpost_info') or {}
    now = time.time()
    target = SimpleNamespace(area_id=reader.area, nickname=role.get('role_name') or '未知指挥官',
                             uid=str(role.get('role_id') or '未提供'), game_id=reader.region.game_id)
    snapshot = dict(complete=True, roster=roster, details=details, saved_at=now,
                    profile_checked_at=now, outpost_checked_at=now,
                    source='blablalink_public', profile=dict(chars=roster, saved=role,
                    basic={'nickname': target.nickname}, player={}, outpost=outpost))
    async def recheck():
        latest_privacy = await read('get_privacy')
        latest_role = await read('get_role')
        if (str(latest_role.get('role_id') or '未提供') != target.uid or reader.area != target.area_id
                or (not role.get('role_id') and latest_role.get('role_name') != role.get('role_name'))
                or latest_privacy.get('show_outpost_info') != privacy.get('show_outpost_info')):
            raise ExportError('目标用户区服、角色或公开设置已变化，请重新导出。')
    return snapshot, target, recheck
