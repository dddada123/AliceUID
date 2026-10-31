"""Chat management: reads pm<=3, writes only exact framework Bot owner pm=0."""
from __future__ import annotations
from ..nikke_commands import command_prefix

from .policy import GroupPolicy, GroupPolicyError, LIST_NAMES, group_key


def permitted(permission, maximum: int) -> bool:
    return type(permission) is int and 0 <= permission <= maximum


class PermissionCommands:
    def __init__(self, policy):
        self.policy = policy

    async def group_query(self, group_id, argument, *, permission=6):
        if not permitted(permission, 3):
            return "仅Bot主或当前群管理员可查看本群查询状态。"
        if not group_id:
            return f"请在群内使用 {command_prefix()}群查询 开启/关闭/状态。"
        option = argument.strip() or "状态"
        if option not in {"开启", "关闭", "状态"}:
            return f"命令：{command_prefix()}群查询 开启/关闭/状态（仅当前群）。"
        if option != "状态" and not permitted(permission, 0):
            return "仅Bot主可修改名单；群管理员只能查看状态。"
        try:
            if option != "状态":
                await self.policy.set_group_enabled(group_id, option == "开启")
            state = await self.policy.group_status(group_id)
            return (f"本群有效查询权限：{'允许' if state['allowed'] else '禁止'}\n"
                    "开启仅移除群黑名单；白名单非空时仍须在白名单内。名单为空默认允许。")
        except GroupPolicyError as exc:
            return str(exc)

    async def group_mode(self, argument, *, permission=6):
        if not permitted(permission, 0):
            return "仅Bot主可管理群查询策略。"
        option = argument.strip() or "状态"
        mapping = {"黑名单": "blacklist", "白名单": "whitelist"}
        if option not in {"状态", *mapping}:
            return f"命令：{command_prefix()}群策略 黑名单/白名单/状态。模式仅兼容记录，实际按四名单判断。"
        try:
            if option != "状态":
                await self.policy.set_mode(mapping[option])
            data = await self.policy.snapshot()
            return (f"群黑名单：{len(data['blacklist'])}；群白名单：{len(data['whitelist'])}\n"
                    "两表空默认允许；白名单非空先限定，再判黑；交叉冲突拒绝保存。旧模式不改变规则。")
        except GroupPolicyError as exc:
            return str(exc)

    async def group_list(self, list_name, argument, *, permission=6):
        return await self.manage_list(list_name, argument, permission=permission)

    async def user_list(self, list_name, argument, *, permission=6):
        return await self.manage_list("user_" + list_name, argument, permission=permission)

    async def manage_list(self, list_name, argument, *, permission=6):
        if not permitted(permission, 0):
            return "仅Bot主可修改权限名单。"
        if list_name not in LIST_NAMES:
            return "名单类型不正确。"
        label = ("用户" if list_name.startswith("user_") else "群") + ("白名单" if list_name.endswith("whitelist") else "黑名单")
        parts = argument.strip().split()
        try:
            if not parts or parts == ["状态"]:
                values = (await self.policy.snapshot())[list_name]
                return label + "：" + ("、".join(values) if values else "空")
            if len(parts) != 2 or parts[0] not in {"添加", "移除"}:
                return f"命令：{command_prefix()}{label} 添加/移除 号码；号码须为ASCII数字。"
            try:
                group_key(parts[1])
            except GroupPolicyError:
                return f"命令：{command_prefix()}{label} 添加/移除 号码；号码须为ASCII数字。"
            await self.policy.update_list(list_name, parts[1], add=parts[0] == "添加")
            return f"已{parts[0]}{label}：{parts[1]}。"
        except GroupPolicyError as exc:
            return str(exc)


def register_commands(commands, *, permission_of=None):
    from gsuid_core.sv import SV
    permission_of = permission_of or (lambda ev: getattr(ev, "user_pm", 6))
    group_sv = SV("妮姬本群查询管理", pm=3, priority=3)
    owner_sv = SV("妮姬群名单管理", pm=0, priority=3)

    @group_sv.on_command("群查询")
    async def group_query(bot, ev):
        await bot.send(await commands.group_query(ev.group_id, ev.text or "状态", permission=permission_of(ev)), at_sender=True)

    @owner_sv.on_command("群策略")
    async def group_mode(bot, ev):
        await bot.send(await commands.group_mode(ev.text or "状态", permission=permission_of(ev)), at_sender=True)

    def register(name, list_name):
        @owner_sv.on_command(name)
        async def manage(bot, ev):
            await bot.send(await commands.manage_list(list_name, ev.text or "状态", permission=permission_of(ev)), at_sender=True)
    for name, list_name in (("群黑名单", "blacklist"), ("群白名单", "whitelist"),
                            ("用户黑名单", "user_blacklist"), ("用户白名单", "user_whitelist")):
        register(name, list_name)
    return group_sv, owner_sv


def setup(state_path, *, config=None, permission_of=None, register=True):
    policy = GroupPolicy(state_path, config=config)
    if register:
        register_commands(PermissionCommands(policy), permission_of=permission_of)
    return policy
