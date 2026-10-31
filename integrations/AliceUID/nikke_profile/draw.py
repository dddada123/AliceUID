"""个人名片 HTML 渲染。"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from ..nikke_render.theme import apply_theme


TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_profile_html(context: dict) -> str:
    from datetime import datetime,timedelta,timezone
    from ..nikke_render.card_background import wide_backdrop
    from ..nikke_character.draw import upper_body_placement,portrait_placement
    from ..nikke_render.icon_effects import portrait_shadow,icon_effect
    from ..nikke_resource.cache import PLACEHOLDER
    result=apply_theme(context,context.get('card_theme'),with_wallpaper=False)
    result.update(wide_backdrop(result['card_theme'],background_name=context.get('wide_background_name')))
    defaults=[('作战人员','—'),('部队战斗力','—'),('时装','—'),('苏醒日','—'),('同步等级','—'),('超频模式','—')]
    stats=list(result.get('stats') or [])
    for label,value in defaults[len(stats):]:stats.append(dict(label=label,value=value))
    result['stats']=stats
    for key,labels in [('progress',['主线 Normal','主线 Hard','无限之塔']),('outpost',['前哨等级','基础设施核心','循环室研究'])]:
        rows=list(result.get(key) or [])
        rows.extend(dict(label=label,value='—') for label in labels[len(rows):])
        result[key]=rows
    result.setdefault('corp_towers',[])
    team=[dict(row) for row in (result.get('top_nikke') or [])[:5]]
    lead=dict(team[0]) if team else dict(name='暂无展示角色',level='—',combat_text='—',rarity='—',role_icons=[],star_states=[],core_display='')
    lead['role_icons']=[dict(icon,icon_shadow_url=icon_effect(icon.get('icon_url'),result['card_theme'])) for icon in lead.get('role_icons') or []]
    result.update(top_nikke=team,lead=lead)
    result['avatar_url']=result.get('avatar_url') or PLACEHOLDER
    source=result.get('hero_art_url') or (lead.get('portrait_url') if not lead.get('portrait_missing',True) else lead.get('icon_url'))
    result['hero_art_url']=source
    if source:
        if result.get('hero_art_kind')=='full':
            anchor=result.get('hero_anchor') or {}
            placement=upper_body_placement(source,width=388,height=640,full_bounds=result.get('hero_full_bounds'),anchor_x=anchor.get('x'),anchor_y=anchor.get('y'),head_top=anchor.get('head_top'))
        else:
            placement=portrait_placement(source,'portraits',388,640)
        result['hero_art_style']=placement or 'width:388px;height:640px;left:0px;top:0px'
        result['hero_shadow_url'],result['hero_shadow_style']=portrait_shadow(source,result['hero_art_style'],glow=result['card_theme']=='dark')
    else:
        result.update(hero_art_style='',hero_shadow_url='',hero_shadow_style='')
    try:
        stamp=datetime.fromisoformat(str(result.get('generated_at') or ''))
        if stamp.tzinfo:stamp=stamp.astimezone(timezone(timedelta(hours=8)))
    except (ValueError,TypeError):stamp=datetime.now(timezone(timedelta(hours=8)))
    result['credit_timestamp']=stamp.strftime('%Y-%m-%d·%H:%M')
    return _env.get_template('profile.html').render(**result)


async def draw_profile(context: dict) -> bytes:
    from ..nikke_render.render import render_html
    from ..nikke_resource.service import get_resources
    from ..nikke_render.cache import get_card_cache, fingerprint, card_key
    resources = get_resources()
    cache = get_card_cache() if context.get('_cache_scope') else None
    slot = fingerprint(['profile', context.get('_cache_scope')])
    dependencies = cache.dependencies(slot) if cache else []
    key = lambda: card_key(context, resources, dependencies=dependencies)
    async def build():
        from ..nikke_resource.cache import track_assets
        with track_assets() as paths:
            prepared = await resources.prepare_profile(context)
            from .presentation import prepare_profile_art
            prepared = await prepare_profile_art(prepared,resources)
        dependencies[:] = sorted(paths)
        dependency = key()
        image = await render_html(render_profile_html(prepared), root_width=1228)
        return image, dependency
    if not context.get('_cache_scope'):
        return (await build())[0]
    return await cache.get(slot, key, build, current=context.get('_current'), dependencies=dependencies)
