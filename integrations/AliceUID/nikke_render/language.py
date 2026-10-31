"""Presentation language is independent from the community's zh-TW data."""
from functools import lru_cache
from html import escape
from html.parser import HTMLParser


def get_card_language():
    from .theme import _configured
    return _configured('AliceUID_CardLanguage', ('zh-CN', 'zh-TW'), 'zh-CN')


@lru_cache(maxsize=2)
def _convert(language):
    from opencc import OpenCC
    return OpenCC('s2t' if language == 'zh-TW' else 't2s').convert


def localize_html(source, language=None):
    language = language or get_card_language()
    convert = _convert(language)

    class Localizer(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.parts, self.raw = [], []
        def handle_starttag(self, tag, attrs):
            self.parts.append(self.get_starttag_text())
            if tag in ('style', 'script'):
                self.raw.append(tag)
        def handle_startendtag(self, tag, attrs):
            self.parts.append(self.get_starttag_text())
        def handle_endtag(self, tag):
            self.parts.append('</'+tag+'>')
            if self.raw and self.raw[-1] == tag:
                self.raw.pop()
        def handle_data(self, data):
            self.parts.append(data if self.raw else escape(convert(data), quote=False))
        def handle_entityref(self, name): self.parts.append('&'+name+';')
        def handle_charref(self, name): self.parts.append('&#'+name+';')
        def handle_comment(self, data): self.parts.append('<!--'+data+'-->')
        def handle_decl(self, decl): self.parts.append('<!'+decl+'>')
    parser = Localizer()
    parser.feed(source)
    return ''.join(parser.parts)
