"""Optional nk卡片 avatar decoration, without a full player data fetch."""
from .service import SoloAccount

async def prepare_identity(account=None, bind=None):
    try:
        from ..nikke_resource.service import get_resources
        from ..nikke_resource.commander import prepare_commander, avatar_is_clear
        resources = get_resources()
        profile = None
        if bind is not None:
            from ..nikke_user.panel_refresh import cached_profile
            profile = cached_profile(bind)
        icon = account.icon_id if isinstance(account, SoloAccount) else None
        if icon is None and profile:
            icon = profile.get('saved', {}).get('icon')
        result = await prepare_commander(resources, {'commander_icon_id': icon})
        source = result.get('commander_avatar_url')
        if avatar_is_clear(source):
            return {'avatar_url': source, 'avatar_hint': '指挥官游戏头像'}
        if profile:
            from ..nikke_profile.builder import build_profile_context
            context = build_profile_context(profile['basic'], profile['outpost'], profile['chars'], resources.load_static(),
                                            saved_role=profile['saved'], player_info=profile['player'])
            team = context.get('top_nikke') or []
            if team:
                row = team[0]
                image = await resources.images.resolved_source('icons', row.get('resource_id', 0), resources._selected_skin(row))
                if not image.missing:
                    return {'avatar_url': image.source, 'avatar_hint': '展示队伍首位角色头像'}
    except Exception:
        # Decoration must not make a valid recommendation unavailable.
        pass
    return {}
