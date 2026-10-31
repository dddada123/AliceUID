"""Official game-binding avatar mapping. Never use a team member as user identity."""
from .cache import PLACEHOLDER


def avatar_mapping(icon, rows):
    if isinstance(icon, bool) or not isinstance(icon, (str,int)) or not str(icon).isascii() or not str(icon).isdigit():
        return None
    matches = [r for r in rows if str(r.get('id')) == str(icon)]
    if len(matches) != 1:
        return None
    row = matches[0]
    rid, skin = row.get('resource_id'), row.get('costume_index')
    if type(rid) is not int or rid <= 0 or type(skin) is not int or not 0 <= skin <= 999:
        return None
    return rid, skin


async def prepare_commander(resources, context):
    mapping = avatar_mapping(context.get('commander_icon_id'), resources._load_rows('character_avatar_map.json'))
    result = dict(commander_avatar_url='', commander_avatar_missing=True)
    if mapping is None:
        return result
    image = await resources.images.resolved_source('icons', *mapping)
    # Another skin/base fallback is not this user's actual avatar.
    if image.missing or image.fallback or image.source == PLACEHOLDER:
        return result
    return dict(commander_avatar_url=image.source, commander_avatar_missing=False,
                commander_avatar_resource_id=mapping[0], commander_avatar_skin_index=mapping[1])


def avatar_is_clear(source, minimum=128):
    """The official SI is normally 128px; reject undersized profile avatars."""
    import base64, io
    from PIL import Image
    if not isinstance(source, str) or not source.startswith('data:image/png;base64,'):
        return False
    try:
        with Image.open(io.BytesIO(base64.b64decode(source.split(',',1)[1],validate=True))) as image:
            return min(image.size) >= minimum and image.width*image.height <= 8_000_000
    except (ValueError,OSError):
        return False
