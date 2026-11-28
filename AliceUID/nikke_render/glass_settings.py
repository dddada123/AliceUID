"""Shared card blur and panel opacity settings across all card renderers."""
KEY = 'AliceUID_GlassStrength'
DEFAULT = 0
OPACITY_KEY = 'AliceUID_CardOpacity'
OPACITY_DEFAULT = 64
RESOURCE_LAYOUT_KEY = 'AliceUID_ResourceCardLayout'
RESOURCE_LAYOUT_DEFAULT = '紧凑'
RESOURCE_LAYOUT_OPTIONS = ('紧凑', '详细')
VERSION = 'glass-v1403-1'


def valid_strength(value):
    return type(value) is int and 0 <= value <= 100


def valid_opacity(value):
    return type(value) is int and 0 <= value <= 100


def get_glass_strength():
    try:
        from ..nikke_config.config import AliceUIDConfig
        value = AliceUIDConfig.get_config(KEY).data
    except (ImportError, AttributeError, KeyError, RuntimeError, TypeError):
        return DEFAULT
    return value if valid_strength(value) else DEFAULT


def get_card_opacity():
    try:
        from ..nikke_config.config import AliceUIDConfig
        value = AliceUIDConfig.get_config(OPACITY_KEY).data
    except (ImportError, AttributeError, KeyError, RuntimeError, TypeError):
        return OPACITY_DEFAULT
    return value if valid_opacity(value) else OPACITY_DEFAULT


def get_resource_card_layout(override=None):
    if override in RESOURCE_LAYOUT_OPTIONS:
        return override
    try:
        from ..nikke_config.config import AliceUIDConfig
        value = AliceUIDConfig.get_config(RESOURCE_LAYOUT_KEY).data
    except (ImportError, AttributeError, KeyError, RuntimeError, TypeError):
        return RESOURCE_LAYOUT_DEFAULT
    return value if value in RESOURCE_LAYOUT_OPTIONS else RESOURCE_LAYOUT_DEFAULT


def capture_glass(context):
    value = context.get('glass_strength')
    if not valid_strength(value):
        value = get_glass_strength()
    opacity = context.get('card_opacity')
    if not valid_opacity(opacity):
        opacity = get_card_opacity()
    return dict(
        context,
        glass_strength=value,
        card_opacity=opacity,
        glass_fingerprint=f'{VERSION}:{value}:{opacity}',
    )


def blur_radius(strength):
    return (strength if valid_strength(strength) else DEFAULT) * 0.8
