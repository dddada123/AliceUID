"""Bulk notification operations and independent, owner-administered group switches."""
from pathlib import Path
from ..nikke_commands import command_prefix
from .notify_state import NotificationPolicy

ENABLED='AliceUID_SignGroupNotify'
WHITE='AliceUID_SignNotifyWhitelist'
BLACK='AliceUID_SignNotifyBlacklist'
KEYS=(ENABLED,WHITE,BLACK)


def valid_groups(value):
    return isinstance(value,list) and all(isinstance(x,str) and 0<len(x)<=32 and x.isascii() and x.isdecimal() for x in value)


def policy_for(config):
    path=getattr(config,'CONFIG_PATH',None)
    if path is None:return None
    path=Path(path[-1] if isinstance(path,list) else path)
    def groups(key):
        try:value=config.get_config(key).data
        except (KeyError,AttributeError):return []
        return value if valid_groups(value) else []
    policy=NotificationPolicy(path.with_name('community.sqlite3'),config.get_config(ENABLED).data,groups(WHITE),groups(BLACK))
    policy.sync(config.get_config(ENABLED).data)
    return policy


def notify_allowed(config,group,bot=None,own=None):
    try:
        from ..nikke_permissions.config import _CONFIG_LOCK
        with _CONFIG_LOCK:
            value=config.get_config(ENABLED).data
            if type(value) is not bool:return False
            policy=policy_for(config)
            if policy is not None:return policy.state(bot,own,str(group))['enabled']
            # Lightweight legacy fixtures have no persistence path.
            white=config.get_config(WHITE).data;black=config.get_config(BLACK).data
            if not valid_groups(white) or not valid_groups(black):return False
            return value and (str(group) in white if white else str(group) not in black)
    except Exception:
        return False


class NotifyCommands:
    def __init__(self,config):self.config=config

    def handle(self,kind,text,permission,route=None):
        if type(permission) is not int or permission!=0:
            return '仅Bot主可修改或查看签到群通知设置。'
        if kind in ('white','black'):
            return f'旧签到通知名单已迁移，请在目标群使用{command_prefix()}开启签到群通知或关闭签到群通知。'
        parts=(text or '状态').strip().split()
        if parts not in (['开启'],['关闭'],['状态']):
            return f'用法：{command_prefix()}{"全群签到通知" if kind=="global" else "签到群通知"} 开启/关闭/状态。'
        from ..nikke_permissions.config import _CONFIG_LOCK
        try:
            with _CONFIG_LOCK:
                policy=policy_for(self.config)
                if policy is None:return '签到通知持久化配置不可用，未修改。'
                if kind=='global':
                    if parts!=['状态']:
                        target=parts==['开启']
                        if self.config.get_config(ENABLED).data!=target:
                            if not self.config.set_config(ENABLED,target):return '保存全群通知设置失败，未确认修改。'
                            policy.sync(target)
                        else:
                            policy.bulk(target)
                    state=policy.state()
                    return ('最近全群设置：'+('开启' if state['default'] else '关闭')+
                            f'；当前有{state["overrides"]}个群单独设置。\n全群操作只应用一次，之后仍可单独修改各群。')
                if not route or not all(route.get(k) for k in ('bot','self_id','group')):
                    return f'请在目标群使用{command_prefix()}开启签到群通知或关闭签到群通知；私聊不会修改全部群。'
                if parts!=['状态']:
                    policy.set_group(route['bot'],route['self_id'],route['group'],parts==['开启'])
                state=policy.state(route['bot'],route['self_id'],route['group'])
                return ('本群签到通知：'+('开启' if state['enabled'] else '关闭')+'；'+
                        ('本群单独设置' if state['individual'] else '沿用全群/迁移设置')+'。\n仅影响本群通知，其他群与签到执行不变。')
        except Exception:
            return '签到群通知设置保存或读取失败，请检查后台；未确认修改。'


def register(config):
    from gsuid_core.sv import SV
    sv=SV('妮姬签到群通知管理',pm=0,priority=3)
    commands=NotifyCommands(config)
    def bind(name,kind,option=None):
        @sv.on_command(name)
        async def handler(bot,ev):
            route=dict(bot=str(ev.bot_id),self_id=str(getattr(ev,'bot_self_id','') or ''),group=str(getattr(ev,'group_id','') or ''))
            if option and (ev.text or '').strip():
                await bot.send(f'用法：{command_prefix()}{name}',at_sender=True);return
            await bot.send(commands.handle(kind,option or ev.text or '状态',getattr(ev,'user_pm',6),route),at_sender=True)
    bind('签到群通知','switch')
    bind('开启签到群通知','switch','开启')
    bind('关闭签到群通知','switch','关闭')
    bind('全群签到通知','global')
    bind('签到通知白名单','white')
    bind('签到通知黑名单','black')
    return sv
