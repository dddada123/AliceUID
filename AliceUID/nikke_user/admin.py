"""XWUID-style Core registration, with server-side safe binding management.

Core generic CSV/CRUD bypasses the plugin's encryption and revocation. Register
the existing model for discovery, filter read/export data, reject generic writes,
and expose a revision-checked unbind using Core's administrator authentication.
"""
from __future__ import annotations
from ..nikke_commands import command_prefix

import csv
import hashlib
import io
import json

VISIBLE = frozenset(('id','user_id','bot_id','group_id','area_id','game_id','nickname',
                     'uid','cookie_expire','is_public','is_master'))
MAX_RESPONSE = 16 * 1024 * 1024


def public_record(row):
    public = {key:value for key,value in row.items() if key in VISIBLE}
    encrypted = row.get('cookie_enc')
    if isinstance(encrypted,str):
        public['binding_version'] = hashlib.sha256(encrypted.encode()).hexdigest()
    return public


def filter_json(data):
    if isinstance(data,list):
        return [filter_json(value) for value in data]
    if not isinstance(data,dict):
        return data
    if 'cookie_enc' in data or ('user_id' in data and 'bot_id' in data):
        return public_record(data)
    result = {key:filter_json(value) for key,value in data.items()
              if key not in ('intl_open_id','cookie_enc')}
    if isinstance(data.get('columns'),list):
        result['columns'] = [column for column in data['columns'] if column.get('name') in VISIBLE]
    return result


def filter_csv(raw):
    rows = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    fields = [field for field in (rows.fieldnames or []) if field in VISIBLE]
    target = io.StringIO(newline='')
    writer = csv.DictWriter(target,fieldnames=fields,lineterminator='\r\n')
    writer.writeheader()
    for row in rows:
        # Preserve Core's own formula neutralization and IDs byte for byte.
        writer.writerow({key:row.get(key,'') for key in fields})
    return b'\xef\xbb\xbf' + target.getvalue().encode('utf-8')


class BindingAdminGuard:
    """Apply only to AliceBind's generic APIs; other Core plugins are untouched."""
    def __init__(self, app, *, table):
        self.app, self.prefix = app, '/api/database/table/' + table.casefold()

    async def __call__(self, scope, receive, send):
        path = scope.get('path','').casefold()
        if scope['type'] != 'http' or not (path == self.prefix or path.startswith(self.prefix+'/')):
            return await self.app(scope,receive,send)
        from starlette.responses import JSONResponse
        if scope['method'] not in ('GET','HEAD'):
            return await JSONResponse(dict(status=1,msg=f'绑定管理禁止通用新增、编辑、导入和删除；更新凭据请使用 {command_prefix()}重新登录，解绑请使用专用解绑接口。'),status_code=409)(scope,receive,send)
        start, chunks, size = None, [], 0
        async def capture(message):
            nonlocal start,size
            if message['type'] == 'http.response.start':
                start = message
            elif message['type'] == 'http.response.body':
                body = message.get('body',b'')
                size += len(body)
                if size <= MAX_RESPONSE:
                    chunks.append(body)
        # Do not parse compressed bytes if Core has an inner GZipMiddleware.
        # An outer compressor may still compress the already-sanitized result.
        inner_scope = dict(scope,headers=[(key,value) for key,value in scope.get('headers',[])
                                         if key.lower() != b'accept-encoding'])
        await self.app(inner_scope,receive,capture)
        if start is None:
            return
        if size > MAX_RESPONSE:
            return await JSONResponse(dict(status=1,msg='绑定导出过大，请按用户筛选后重试。'),status_code=413)(scope,receive,send)
        raw = b''.join(chunks)
        content_type = dict(start['headers']).get(b'content-type',b'').lower()
        if start['status'] == 200 and scope['method'] != 'HEAD':
            try:
                if b'json' in content_type:
                    raw = json.dumps(filter_json(json.loads(raw)),ensure_ascii=False).encode('utf-8')
                elif b'text/csv' in content_type:
                    raw = filter_csv(raw)
                else:
                    return await JSONResponse(dict(status=1,msg='不支持的绑定管理响应类型，已停止返回。'),status_code=502)(scope,receive,send)
            except (ValueError,UnicodeError,csv.Error,TypeError,AttributeError):
                return await JSONResponse(dict(status=1,msg='绑定管理响应结构变化，已停止返回。'),status_code=502)(scope,receive,send)
        headers = [(key,value) for key,value in start['headers'] if key.lower() not in (b'content-length',b'cache-control')]
        headers.extend([(b'content-length',str(len(raw)).encode()),(b'cache-control',b'no-store')])
        await send(dict(start,headers=headers))
        await send(dict(type='http.response.body',body=raw))


async def admin_unbind(record_id, payload):
    from .models import AliceBind
    record = await AliceBind.admin_record(record_id)
    if record is None:
        return dict(status=1,msg='绑定不存在，请刷新列表。')
    expected = payload.get('binding_version')
    if (not isinstance(expected,str) or expected != hashlib.sha256(record.cookie_enc.encode()).hexdigest()
            or str(payload.get('user_id')) != str(record.user_id)
            or str(payload.get('bot_id')) != str(record.bot_id)):
        return dict(status=1,msg='确认信息与当前绑定不一致，请刷新后重试。')
    try:
        result = await AliceBind.delete_bind(record.user_id,record.bot_id,expected_revision=expected)
        if result != 0:
            return dict(status=1,msg='解绑未确认完成，请检查日志。')
    except ValueError:
        return dict(status=1,msg='绑定已变化，请刷新后重新确认。')
    from ..nikke_login.session import sessions
    from .service import _invalidate_replaced
    sessions.clear_owner(record.user_id,record.bot_id)
    await _invalidate_replaced(record)
    return dict(status=0,msg='已解绑，旧登录链接、自动任务授权及账号缓存已失效。')


def setup_admin():
    from gsuid_core.logger import logger
    try:
        from gsuid_core.webconsole.mount_app import GsAdminModel,PageSchema,site
        from gsuid_core.webconsole.app_app import app
        from gsuid_core.webconsole.web_api import require_admin
        # Old AMIS-only cores do not share this read/export API contract.
        from gsuid_core.utils.database import admin_api  # noqa: F401
    except ImportError:
        logger.warning('[AliceUID] 当前Core未提供兼容的数据库管理接口；登录绑定功能保持可用')
        return False
    if getattr(app.state,'aliceuid_binding_admin',False):
        return True
    from .models import AliceBind
    from fastapi import Body,Depends

    class AliceBindAdmin(GsAdminModel):
        pk_name = 'id'
        page_schema = PageSchema(label='用户绑定管理（脱敏只读）',icon='fa fa-users')
        model = AliceBind

    # Install backend restrictions BEFORE publishing a model to Core discovery.
    app.add_middleware(BindingAdminGuard,table=AliceBind.__tablename__)

    @app.post('/api/aliceuid/bindings/{record_id}/unbind',dependencies=[Depends(require_admin)])
    async def unbind(record_id: int, payload: dict = Body(...)):
        return await admin_unbind(record_id,payload)

    site.register_admin(AliceBindAdmin)
    app.state.aliceuid_binding_admin = True
    logger.info('[AliceUID] GsCore数据库管理已注册；绑定摘要/导出脱敏，解绑使用专用接口')
    return True
