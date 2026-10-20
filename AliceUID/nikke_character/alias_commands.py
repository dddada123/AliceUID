"""Bot-owner-only alias writes, also covered by the root four-list guard."""
from ..nikke_commands import command_prefix
from gsuid_core.sv import SV
from ..nikke_resource.service import get_resources
from .aliases import get_alias_store
from .builder import CharacterLookupError

sv_alias=SV('妮姬角色别名管理',pm=0,priority=3)
sv_alias_query=SV('妮姬角色别名查询',pm=6,priority=3)


@sv_alias.on_regex(r'^(?P<character>.+?)(?:新增|注册)别名(?P<alias>.+)$')
async def add_alias(bot,ev):
    if type(getattr(ev,'user_pm',None)) is not int or ev.user_pm!=0:
        await bot.send('仅Bot主可维护角色别名。',at_sender=True)
        return
    args=ev.regex_dict
    static=get_resources().load_static()
    try:
        code=get_alias_store().add(args['character'],args['alias'],static)
        await bot.send(f"已添加：{static.name(code)} → {args['alias'].strip()}",at_sender=True)
    except (CharacterLookupError,ValueError,OSError):
        await bot.send('添加失败：请核对完整角色名、别名冲突或本地别名文件。',at_sender=True)


async def query_alias(bot, ev, name):
    from ..nikke_permissions.runtime import get_policy
    if not await get_policy().query_allowed(ev.group_id):
        await bot.send('本群未开放妮姬查询，请联系管理员。',at_sender=True)
        return
    if not name.strip():
        await bot.send(f'用法：{command_prefix()}红莲暗影别名查询 / {command_prefix()}黑莲别名查询 / {command_prefix()}角色别名查询 红莲：暗影。',at_sender=True)
        return
    try:
        resources = get_resources()
        static = resources.load_static()
        context = get_alias_store().lookup(name,static)
        info = static.character(context['name_code'])
        resource_id = info.get('resource_id')
        if type(resource_id) is not int or resource_id <= 0:
            raise ValueError('角色头像编码缺失')
        icon = await resources.images.resolved_source('icons',resource_id,0)
        context['icon_url'] = icon.source
        from .alias_draw import draw_alias
        from gsuid_core.segment import MessageSegment
        result = MessageSegment.image(await draw_alias(context))
        if get_policy().user_allowed(ev.user_id) and await get_policy().query_allowed(ev.group_id):
            await bot.send(result,at_sender=True)
    except CharacterLookupError as exc:
        await bot.send(str(exc),at_sender=True)
    except (ValueError,OSError):
        await bot.send('别名查询失败，请检查角色资料与别名文件。',at_sender=True)


@sv_alias_query.on_suffix('别名查询')
async def alias_query_suffix(bot,ev):
    # The explicit prefix command owns this form; do not send a second reply.
    text = (ev.text or '').strip()
    if text == '角色' or text.startswith('角色别名查询'):
        return
    await query_alias(bot,ev,text)


@sv_alias_query.on_command('角色别名查询')
async def alias_query_command(bot,ev):
    await query_alias(bot,ev,ev.text or '')
