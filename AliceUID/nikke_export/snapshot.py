"""Additive export schema: old panel JSON stays readable for character cards."""
from ..nikke_character.attributes import FORMULA_VERSION
import math

DATA_REVISION = 4
ATTRIBUTE_SCHEMA = 3

def mark_current(snapshot):
    snapshot.update(data_revision=DATA_REVISION, attribute_schema=ATTRIBUTE_SCHEMA,
                    attribute_formula_version=FORMULA_VERSION)
    return snapshot

def ready(snapshot):
    if (not isinstance(snapshot, dict) or snapshot.get('complete') is not True or
            snapshot.get('data_revision') != DATA_REVISION or
            snapshot.get('attribute_schema') != ATTRIBUTE_SCHEMA or
            snapshot.get('attribute_formula_version') != FORMULA_VERSION):
        return False
    rows, details, attrs, profile = (snapshot.get(k) for k in ('roster','details','attributes','profile'))
    if (not isinstance(rows,list) or not rows or not all(isinstance(r,dict) for r in rows)
            or not isinstance(details,dict) or not isinstance(attrs,dict) or not isinstance(profile,dict)):
        return False
    codes=[str(r.get('name_code')) for r in rows]
    from ..nikke_character.service import CharacterQueryService
    try:
        CharacterQueryService.roster_codes(rows)
    except ValueError:
        return False
    stamp=snapshot.get('saved_at')
    if type(stamp) not in (int,float) or not math.isfinite(stamp) or stamp <= 0:
        return False
    if len(codes)!=len(set(codes)) or set(codes)!=set(details) or set(codes)!=set(attrs):
        return False
    if profile.get('chars') != rows or not all(isinstance(profile.get(k),dict) for k in ('basic','saved','player','outpost')):
        return False
    # Unavailable attributes are valid schema: private/hidden fields must not
    # force a full refresh on every export or fabricate a successful number.
    def valid_values(attr):
        if attr.get('status')=='unavailable':
            return all(attr.get(k) is None for k in ('attack','defense','hp'))
        return all(type(attr.get(k)) in (int,float) and math.isfinite(attr[k]) and attr[k]>=0
                   for k in ('attack','defense','hp'))
    return all(isinstance(details[c],dict) and isinstance(details[c].get('detail'),dict)
               and str(details[c]['detail'].get('name_code'))==c
               and isinstance(details[c].get('effects'),list)
               and isinstance(attrs[c],dict) and attrs[c].get('status') in ('complete','unavailable')
               and attrs[c].get('formula_version')==FORMULA_VERSION and valid_values(attrs[c]) for c in codes)
