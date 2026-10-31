"""Recycling-room levels from the bound account's outpost response."""
RESEARCH = {
    'attacker': (1101, '火力型'), 'defender': (1102, '防御型'), 'supporter': (1103, '辅助型'),
    'elysion': (1201, '极乐净土'), 'missilis': (1202, '米西利斯'), 'tetra': (1203, '泰特拉'),
    'pilgrim': (1204, '朝圣者'), 'abnormal': (1205, '反常'),
}


def _nonnegative(value):
    if isinstance(value, bool) or not isinstance(value, (int,str)):
        return None
    if not str(value).isascii() or not str(value).isdigit():
        return None
    return int(value)


def recycling_levels(context, icons):
    """No row/hidden sentinel/duplicates => unknown, never a fabricated Lv.0."""
    rows = context.get('recycle_room_researches')
    rows = rows if isinstance(rows,list) else []
    by_kind = {r.get('kind'):r for r in icons if isinstance(r,dict)}
    result = []
    for kind, key, default in [('class',context.get('char_class'),'职业'),
                                ('corporation',context.get('corporation'),'企业')]:
        tid, name = RESEARCH.get(str(key or '').lower(), (None,default))
        matches = [r for r in rows if isinstance(r,dict) and _nonnegative(r.get('tid'))==tid] if tid else []
        lv = _nonnegative(matches[0].get('lv')) if len(matches)==1 else None
        icon = by_kind.get(kind,{})
        result.append(dict(kind=kind,tid=tid,label=name,level=lv,
                           icon_url=icon.get('icon_url') if not icon.get('missing') else None))
    return result
