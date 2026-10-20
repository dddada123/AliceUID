"""One CSS-pixel background blur setting, shared by all card renderers."""
KEY='AliceUID_GlassStrength'
DEFAULT=10
VERSION='glass-v101-1'


def valid_strength(value):
    return type(value) is int and 0<=value<=100


def get_glass_strength():
    try:
        from ..nikke_config.config import AliceUIDConfig
        value=AliceUIDConfig.get_config(KEY).data
    except (ImportError,AttributeError,KeyError,RuntimeError,TypeError):
        return DEFAULT
    return value if valid_strength(value) else DEFAULT


def capture_glass(context):
    value=context.get('glass_strength')
    if not valid_strength(value):value=get_glass_strength()
    return dict(context,glass_strength=value,glass_fingerprint=f'{VERSION}:{value}')


def blur_radius(strength):
    return (strength if valid_strength(strength) else DEFAULT)*0.8
