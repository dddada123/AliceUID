"""登录区服必须由用户明确选择，绝不跨区探测或替换。"""
from __future__ import annotations
from ..nikke_commands import command_prefix
from ..nikke_api.client import NikkeClient, REGIONS, Region

REGION_ALIASES = {r.label: r.area_id for r in REGIONS.values()}
REGION_ALIASES.update({"日本": 81, "日": 81, "北美": 82, "韩": 83, "韩国": 83, "国际": 84, "全球": 84, "全球服": 84, "东南亚": 85})
REGION_HELP = "请选择游戏角色所在区服：\n" + "\n".join(f"{command_prefix()}登录{r.label}" for r in REGIONS.values()) + f"\n以上命令中的「登录」均可写成「登陆」，例如{command_prefix()}登陆日服；{command_prefix()}重新登录/{command_prefix()}重新登陆同样可用。\n绑定严格使用所选区服，查不到角色会提示失败，不会自动换区。港澳台服暂未支持此登录流程。"

def saved_role_matches(role: dict, region: Region) -> bool:
    """社区保存角色只有区服与游戏均一致时才能提供 UID。"""
    return str(role.get("area_id")) == str(region.area_id) and str(role.get("game_id")) == region.game_id


async def selected_role(credentials, area_id: int) -> tuple[Region, dict]:
    region = REGIONS.get(area_id)
    if region is None:
        raise ValueError("请选择受支持的区服后重新获取登录链接")
    if credentials.game_id != region.game_id:
        raise ValueError("凭证所属游戏与所选区服不一致，请重新登录所选区服")
    try:
        await NikkeClient.detect_region(credentials, candidates=(region,))
    except Exception:
        raise ValueError(f"未能验证{region.label}角色，请检查区服或稍后重试；不会自动改绑其他区服") from None
    async with NikkeClient(credentials, region) as client:
        basic = await client.get_basic_info()
        if str(basic.get("area_id", area_id)) != str(area_id):
            raise ValueError("角色资料区服与所选区服不一致，已停止绑定")
        role = await client.get_saved_role_info()
    matches = saved_role_matches(role, region)
    return region, {"role_name": basic.get("nickname") or basic.get("role_name") or (role.get("role_name") if matches else "") or "", "role_id": str(role.get("role_id") or "") if matches else ""}
