"""Notification-only controls. Whitelist wins; existing business policies are untouched."""
from ..nikke_commands import command_prefix

ENABLED = 'AliceUID_SignGroupNotify'
WHITE = 'AliceUID_SignNotifyWhitelist'
BLACK = 'AliceUID_SignNotifyBlacklist'
KEYS = (ENABLED,WHITE,BLACK)

def valid_groups(value):
    return isinstance(value,list) and all(isinstance(x,str) and 0<len(x)<=32 and x.isascii() and x.isdecimal() for x in value)

def notify_allowed(config,group):
    try:
        enabled=config.get_config(ENABLED).data
        white=config.get_config(WHITE).data
        black=config.get_config(BLACK).data
        if type(enabled) is not bool or not enabled or not valid_groups(white) or not valid_groups(black):
            return False
        group=str(group)
        # Nonempty whitelist defines the intended recipients, including overlap.
        return group in white if white else group not in black
    except (AttributeError,KeyError,TypeError,ValueError,RuntimeError):
        return False

class NotifyCommands:
    def __init__(self,config):self.config=config

    def handle(self,kind,text,permission):
        if type(permission) is not int or permission!=0:
            return '仅Bot主可修改或查看全局签到群通知设置。'
        parts=(text or '状态').strip().split()
        if kind=='switch':
            if parts not in (['开启'],['关闭'],['状态']):
                return f'用法：{command_prefix()}签到群通知 开启/关闭/状态（全局，只影响签到群通知）。'
            if parts!=['状态'] and not self.config.set_config(ENABLED,parts==['开启']):
                return '保存签到群通知设置失败，原设置保持不变。'
            on=self.config.get_config(ENABLED).data
            return ('全局签到群通知：'+('开启' if on else '关闭')+'。\n'
                    '仅影响签到完成通知，不影响签到执行和其他业务。\n'
                    '白名单非空时只通知白名单群；白黑名单重叠时白名单优先；全局关闭优先于两表。')
        key=WHITE if kind=='white' else BLACK
        label='签到通知白名单' if kind=='white' else '签到通知黑名单'
        if parts==['状态']:
            values=self.config.get_config(key).data
            return label+'：'+('、'.join(values) if values else '空')+'。白名单优先，仅影响签到群通知。'
        if len(parts)!=2 or parts[0] not in ('添加','移除') or not valid_groups([parts[1]]):
            return f'用法：{command_prefix()}{label} 添加/移除 群号；或 状态。'
        values=self.config.get_config(key).data
        if not valid_groups(values):return '签到通知名单格式异常，请在后台修复。'
        updated=set(values)
        if parts[0]=='添加':updated.add(parts[1])
        else:updated.discard(parts[1])
        if not self.config.set_config(key,sorted(updated)):
            return '保存签到通知名单失败，原设置保持不变。'
        return f'已{parts[0]}{label}：{parts[1]}。白名单优先，仅影响签到群通知。'


def register(config):
    from gsuid_core.sv import SV
    sv=SV('妮姬签到群通知管理',pm=0,priority=3)
    commands=NotifyCommands(config)
    def bind(name,kind):
        @sv.on_command(name)
        async def handler(bot,ev):
            await bot.send(commands.handle(kind,ev.text or '状态',getattr(ev,'user_pm',6)),at_sender=True)
    bind('签到群通知','switch')
    bind('签到通知白名单','white')
    bind('签到通知黑名单','black')
    return sv
