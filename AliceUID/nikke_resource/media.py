"""Development media lives outside version trees; installed media keeps its paths."""
from pathlib import Path
import json

PLUGIN_ROOT = Path(__file__).resolve().parents[2]


def media_root():
    mapping = PLUGIN_ROOT.parent / 'workspace_paths.json'
    if mapping.is_file():
        value = json.loads(mapping.read_text('utf-8')).get('media_root')
        if value:
            return Path(value) / 'AliceUID'
    return PLUGIN_ROOT


def media_path(relative):
    return media_root() / relative
