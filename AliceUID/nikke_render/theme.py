"""Lazy GsCore configuration and shared renderer-safe card theme tokens."""
from __future__ import annotations

from functools import lru_cache
import base64
import io


def _configured(key: str, allowed: tuple[str, ...], default: str) -> str:
    try:
        from ..nikke_config.config import AliceUIDConfig
        value = AliceUIDConfig.get_config(key).data
    except (ImportError, AttributeError, KeyError, RuntimeError):
        value = default
    return value if value in allowed else default


def get_card_theme(theme: str | None = None, default: str = 'random') -> str:
    if theme in ('light', 'dark'):
        return theme
    selected = theme if theme == 'random' else get_card_theme_mode(default)
    if selected == 'random':
        import random
        return random.choice(('light', 'dark'))
    return selected


def get_card_theme_mode(default='random'):
    """Stable cache identity; choose a random concrete palette only on render."""
    return _configured('AliceUID_CardTheme', ('light', 'dark', 'random'), default if default in ('light','dark','random') else 'random')


def get_card_style(style: str | None = None) -> str:
    from .layouts import character_layout_keys
    if style in character_layout_keys():
        return style
    return get_character_style()


def card_theme(theme: str | None = None) -> dict:
    resolved = apply_theme({}, theme, with_wallpaper=False)
    return dict(resolved['theme'], card_theme=resolved['card_theme'])


CHARACTER_THEMES=('compact_light','compact_dark','wide_light','wide_dark')


def character_presentation_mode():
    return dict(fixed=_configured('AliceUID_CharacterCardStyle',CHARACTER_THEMES,'wide_light'),
                random=_configured('AliceUID_CharacterRandomTheme',('off','wide','compact','all'),'off'))


def get_character_style(default='wide'):
    return character_presentation_mode()['fixed'].split('_')[0]


def resolve_character_presentation(style=None,theme=None):
    """Choose once per new paint; the image cache keys the stable mode, not a random draw."""
    import random
    from .layouts import character_layout_keys
    mode=character_presentation_mode()
    if style in CHARACTER_THEMES:
        layout,color=style.split('_')
    elif style in character_layout_keys():
        layout,color=style,mode['fixed'].split('_')[1]
    elif style:
        layout,color='compact',mode['fixed'].split('_')[1]
    else:
        choices=CHARACTER_THEMES
        if mode['random']=='wide':choices=tuple(x for x in choices if x.startswith('wide_'))
        elif mode['random']=='compact':choices=tuple(x for x in choices if x.startswith('compact_'))
        selected=mode['fixed'] if mode['random']=='off' else random.choice(choices)
        layout,color=selected.split('_')
    if theme in ('light','dark'):color=theme
    elif theme=='random':color=random.choice(('light','dark'))
    return layout,color


@lru_cache(maxsize=1)
def light_texture_uri() -> str:
    """Tiny deterministic abstract texture; no downloaded material."""
    from PIL import Image
    image = Image.new('RGBA', (96, 96))
    image.putdata([(80, 102, 130, 5 if (x * 17 + y * 29) % 11 == 0 else 0)
                   for y in range(96) for x in range(96)])
    output = io.BytesIO()
    image.save(output, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii')


def apply_theme(context: dict, theme: str | None = None, *, scene_width=1000, scene_height=1400, with_wallpaper=True) -> dict:
    """Return a context copy with card_theme name, theme tokens and texture URI."""
    from .glass_settings import capture_glass,blur_radius
    from ..nikke_commands import command_prefix
    context=capture_glass(context)
    theme = theme if theme in ('light', 'dark') else get_card_theme()
    dark = theme == 'dark'
    tokens = dict(page='#141c28' if dark else '#e9eef4',
                  ink='#f1f5fc' if dark else '#182536',
                  muted='#bdcce0' if dark else '#35475d',
                  accent='#81c8ff' if dark else '#124c77',
                  line='#4b5e76' if dark else '#ced8e3',
                  panel='#263448' if dark else '#f6f8fb',
                  glass='rgba(31,44,62,.91)' if dark else 'rgba(250,253,255,.88)',
                  surface_glass='rgba(20,32,50,.80)' if dark else 'rgba(248,251,255,.80)',
                  container_glass='rgba(20,32,50,.30)' if dark else 'rgba(248,251,255,.30)',
                  soft='#334359' if dark else '#e6edf5',
                  texture_uri=light_texture_uri())
    from .glass import image_uri
    if with_wallpaper:
        from .wallpaper import wallpaper_scene
        scene=wallpaper_scene(scene_width,scene_height,theme)
        from PIL import ImageFilter
        photo_uri=image_uri(scene.filter(ImageFilter.GaussianBlur(blur_radius(context['glass_strength']))))

    else:
        photo_uri=''
    return dict(context, command_prefix=command_prefix(), card_theme=theme, theme=tokens, texture_uri=tokens['texture_uri'],
                frost_scene_uri=photo_uri, frost_panel_uri='',
                background_source='local-card-bg',background_scene_width=scene_width,background_scene_height=scene_height)
