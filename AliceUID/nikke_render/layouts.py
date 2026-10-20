"""Extensible character layout registry; only compact ships after retirement."""
from dataclasses import dataclass
import re

@dataclass(frozen=True)
class CharacterLayout:
    key: str
    template: str
    width: int=660

_LAYOUTS={'compact':CharacterLayout('compact','character_compact.html',660)}


def character_layout_keys():return tuple(_LAYOUTS)


def resolve_character_layout(key=None):return _LAYOUTS.get(key,_LAYOUTS['compact'])


def register_character_layout(key,template,*,width=660):
    """Future trusted-code layout extension. Selection/UI interfaces stay intact."""
    if not isinstance(key,str) or not re.fullmatch('[a-z][a-z0-9_-]{0,31}',key):raise ValueError('invalid layout key')
    if not isinstance(template,str) or not re.fullmatch('[A-Za-z0-9_-]+[.]html',template):raise ValueError('invalid template name')
    if type(width) is not int or not 320<=width<=2000:raise ValueError('unsupported layout width')
    if key in _LAYOUTS:raise ValueError('layout already registered')
    _LAYOUTS[key]=CharacterLayout(key,template,width)
