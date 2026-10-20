"""Development-only external data mount. Production keeps get_res_path()."""
from pathlib import Path
import json


def data_root(project_root):
    root=Path(project_root).resolve()
    config=root/'workspace_paths.json'
    if config.is_file():
        raw=json.loads(config.read_text(encoding='utf-8'))
        configured=raw.get('data_root')
        if configured:
            value=Path(configured)
            if not value.is_absolute():value=root/value
            return value.resolve()
    return root/'data'


def nikke_data(project_root):return data_root(project_root)/'AliceUID'


def archive_data_name(path,project_root):
    return 'data/'+Path(path).resolve().relative_to(data_root(project_root)).as_posix()
