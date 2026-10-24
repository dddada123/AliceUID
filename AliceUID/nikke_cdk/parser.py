"""Parse only visible, classified GameWith CDK tables, not article scripts."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta

from lxml import html
from .models import TOKYO, PRODUCT, PARSER_VERSION, code_text, clean


class ParseError(ValueError):
    pass


def official_window(row):
    """Official availability fields are Unix seconds, independent of browser timezone."""
    dates = {}
    for source, target in [('valid_time_start', 'valid_from'), ('valid_time_end', 'expires_at')]:
        value = row.get(source)
        if value is None or value == '' or type(value) is int and value == 0 or value == '0':
            continue
        if (type(value) not in (int, str) or not str(value).isascii()
                or not str(value).isdigit()):
            raise ParseError('官方期限格式变化')
        value = int(value)
        if not 946684800 <= value < 4133980800:
            raise ParseError('官方期限超出支持范围')
        dates[target] = value
    if dates.get('valid_from') and dates.get('expires_at') and dates['valid_from'] > dates['expires_at']:
        raise ParseError('官方起止期限异常')
    return dates


def parse_official(data, now):
    if not isinstance(data, dict):
        raise ParseError('官方目录结构变化')
    rows = data.get('cdk_redemption_list')
    if not isinstance(rows, list) or len(rows) > 200 or data.get('is_last_page', True) is not True:
        raise ParseError('官方目录结构或分页变化')
    if 'total' in data and (type(data['total']) is not int or data['total'] != len(rows)):
        raise ParseError('官方目录数量不完整')
    items = []
    for row in rows:
        if not isinstance(row, dict):
            raise ParseError('官方条目结构变化')
        product = row.get('intl_game_id')
        if product is None or product == '':
            product = PRODUCT
        if type(product) not in (str, int):
            raise ParseError('官方产品标识变化')
        products = {p.strip() for p in str(product).split(',')}
        if not products or products - {PRODUCT, '29157', 'GLOBAL', 'HMT'}:
            raise ParseError('官方产品标识变化')
        if not products & {PRODUCT, 'GLOBAL'}:
            continue
        items.append(dict(code=code_text(row.get('cdk')), state='candidate', reward='',
                          expiry_source='official', **official_window(row)))
    return dict(items=items, title='官方推荐', checked_at=now, parser_version=PARSER_VERSION)


def norm(text):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text or ''))


def text_of(element):
    def pieces(node):
        if node.text:
            yield node.text
        for child in node:
            if child.tag in ('p', 'div', 'li'):
                yield '\n'
            if child.tag == 'br':
                yield '\n'
            else:
                yield from pieces(child)
            if child.tail:
                yield child.tail
            if child.tag in ('p', 'div', 'li'):
                yield '\n'
    return clean(''.join(pieces(element)))


def deadline(note, section, modified, now):
    """Return exclusive end timestamp; ambiguous date evidence never grants validity."""
    note = unicodedata.normalize('NFKC', note)
    if not re.search(r'まで|期限|終了|開始|から', note):
        return {}, None
    match = re.search(r'(?:(20\d{2})[年/.-])?(\d{1,2})[月/]\s*(\d{1,2})(?:日)?(?:\(([月火水木金土日])\))?\s*(\d{1,2}):(\d{2})', note)
    if not match:
        return {}, '期限を確認できません'
    year, month, day, weekday, hour, minute = match.groups()
    month, day, hour, minute = map(int, (month, day, hour, minute))
    anchor = datetime.fromtimestamp(now, TOKYO)
    if modified:
        try:
            parsed = datetime.fromisoformat(modified).astimezone(TOKYO)
            if abs(parsed.timestamp() - now) < 370 * 86400:
                anchor = parsed
        except (ValueError, TypeError):
            pass
    years = [int(year)] if year else list(range(anchor.year - 1, anchor.year + 2))
    candidates = []
    section_date = re.search(r'(\d{1,2})/(\d{1,2})', section)
    for y in years:
        try:
            dt = datetime(y, month, day, hour, minute, tzinfo=TOKYO)
            if weekday and '月火水木金土日'[dt.weekday()] != weekday:
                continue
            if not year and not weekday:
                # A date without a year or weekday has no unique year evidence.
                continue
            if section_date:
                added = datetime(y, int(section_date[1]), int(section_date[2]), tzinfo=TOKYO)
                if dt < added:
                    added = added.replace(year=y - 1)
                if not 0 <= (dt - added).days <= 180:
                    continue
            candidates.append(dt)
        except ValueError:
            continue
    if len(candidates) != 1:
        return {}, '期限年份或星期无法唯一确认'
    dt = candidates[0]
    if re.search(r'開始|から', note) and not re.search(r'まで|期限|終了', note):
        return {'valid_from': dt.timestamp()}, None
    return {'expires_at': (dt + timedelta(minutes=1)).timestamp()}, None


def table_columns(table):
    rows = table.xpath('./tr|./thead/tr|./tbody/tr|./tfoot/tr')
    if not rows:
        return None, []
    headers = rows[0].xpath('./th|./td')
    labels = [norm(text_of(c)) for c in headers]
    if 'コード' not in labels or '報酬内容' not in labels:
        return None, []
    # Reject ambiguous grids rather than shift a code into a reward column.
    if any(c.get('rowspan', '1') != '1' or c.get('colspan', '1') != '1' for c in table.xpath('.//th|.//td')):
        raise ParseError('CDK表格合并单元格需适配')
    if labels.count('コード') != 1 or labels.count('報酬内容') != 1:
        raise ParseError('CDK表头重复')
    return (labels.index('コード'), labels.index('報酬内容'), len(labels)), rows[1:]


def parse_gamewith(content, now):
    if len(content) > 2_000_000:
        raise ParseError('来源页面过大')
    try:
        tree = html.fromstring(content, parser=html.HTMLParser(remove_comments=True))
    except (ValueError, TypeError) as exc:
        raise ParseError('来源HTML无法解析') from exc
    bodies = tree.xpath('//*[@id="article-body"]')
    if len(bodies) != 1:
        raise ParseError('缺少唯一文章主体')
    body = bodies[0]
    for node in body.xpath('.//script|.//style|.//noscript'):
        node.drop_tree()
    title = clean(''.join(tree.xpath('//h1//text()')))
    if not re.search(r'CDK|コード', title, re.I):
        raise ParseError('不是CDK文章')
    modified = next(iter(tree.xpath('//time/@datetime')), '')
    active, section, levels = False, '', {}
    items, matched, row_count = [], 0, 0
    for node in body.iter():
        if node.tag in ('h2', 'h3', 'h4'):
            level = int(node.tag[1])
            heading = norm(text_of(node))
            levels = {k: v for k, v in levels.items() if k < level}
            levels[level] = heading
            if level == 2:
                active = bool(re.search(r'コード.*(?:CDK|一覧)|CDK.*一覧', heading, re.I)) and '入力方法' not in heading
            section = ' / '.join(levels.values())
        if node.tag != 'table' or not active:
            continue
        columns, rows = table_columns(node)
        if columns is None:
            continue
        matched += 1
        negative = bool(re.search(r'過去|以前|履歴|期限切れ|失効|終了済', section))
        positive = bool(re.search(r'(?:追加|反映|新着|最新|有効|使用可能|利用可能).*コード|コード.*(?:有効|使用可能|利用可能)', section))
        # Only the owning section supplies membership; no generic table-header fallback.
        membership = 'archived' if negative else 'candidate' if positive else 'unclassified'
        ci, ri, width = columns
        for row in rows:
            cells = row.xpath('./th|./td')
            if not cells:
                continue
            if len(cells) != width:
                raise ParseError('CDK表格列数变化')
            row_count += 1
            if row_count > 1000:
                raise ParseError('CDK行数异常')
            cell = cells[ci]
            copies = cell.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," w-clipboard-copy-ui ")]')
            if len(copies) > 1:
                raise ParseError('同一行含多个兑换码')
            if copies:
                raw = text_of(copies[0])
            else:
                attributes = cell.xpath('.//@data-clipboard-text')
                code_nodes = cell.xpath('.//code')
                if len(attributes) > 1 or len(code_nodes) > 1:
                    raise ParseError('代码列存在多个复制值')
                raw = attributes[0] if attributes else text_of(code_nodes[0]) if code_nodes else ''.join(cell.xpath('./text()')).strip()
            try:
                code = code_text(raw)
            except ValueError as exc:
                raise ParseError('代码行结构变化，已保留原缓存') from exc
            note = text_of(cell).replace(raw, '', 1)
            # Extra columns can hold a deadline; code/reward positions remain mapped by headers.
            note += ' ' + ' '.join(text_of(c) for index, c in enumerate(cells) if index not in (ci, ri))
            dates, error = deadline(note, section, modified, now)
            state = membership
            if re.search(r'期限切れ|失効|終了済', note):
                state = 'expired'
            elif error and membership == 'candidate':
                state = 'uncertain'
            # Keep expired/future candidate membership so it can be filtered at read time.
            item = dict(code=code, reward=text_of(cells[ri]), state=state,
                        section=section, deadline_raw=clean(note), **dates)
            if error:
                item['reason'] = error
            items.append(item)
    if not matched:
        raise ParseError('未找到代码和报酬表头')
    if any(i['state'] == 'unclassified' for i in items):
        raise ParseError('发现无法分类的CDK板块')
    return dict(title=title, modified=modified, items=items, tables=matched)
