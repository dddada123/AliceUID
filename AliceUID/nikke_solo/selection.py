"""Canonical weakness selection and strict command argument parsing."""
from dataclasses import dataclass
import re

# Values are the site's native boss-weakness option values, not enemy elements.
ELEMENTS = {'fire': ('燃烧', '火', '작열'), 'water': ('水冷', '水', '수냉'),
            'wind': ('风压', '风', '풍압'), 'electric': ('电击', '电', '전격'),
            'iron': ('铁甲', '铁', '철갑')}
ALIASES = {alias: key for key, names in ELEMENTS.items() for alias in names[:2]}
BY_CODE = {names[2]: key for key, names in ELEMENTS.items()}

@dataclass(frozen=True)
class Selection:
    mode: str = 'default'
    refresh: bool = False
    theme: str | None = None

    @property
    def code(self):
        return ELEMENTS[self.mode][2] if self.mode != 'default' else None

    @property
    def suffix(self):
        return ELEMENTS[self.mode][1] if self.mode != 'default' else ''

def parse_selection(text):
    text = re.sub(r'\s+', '', text or '')
    tokens = re.findall(r'燃烧|水冷|风压|电击|铁甲|刷新|亮色|暗色|随机|[火水风电铁]', text)
    if ''.join(tokens) != text:
        raise ValueError('未知参数')
    modes = [ALIASES[t] for t in tokens if t in ALIASES]
    themes = [{'亮色': 'light', '暗色': 'dark', '随机': 'random'}[t]
              for t in tokens if t in ('亮色', '暗色', '随机')]
    if len(modes) > 1 or len(themes) > 1 or tokens.count('刷新') > 1:
        raise ValueError('参数重复')
    return Selection(modes[0] if modes else 'default', '刷新' in tokens,
                     themes[0] if themes else None)

def label(code):
    key = BY_CODE.get(code)
    return f'{ELEMENTS[key][0]}（{ELEMENTS[key][1]}）' if key else '未知'
