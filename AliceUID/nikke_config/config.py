"""插件配置。"""
from pathlib import Path

from gsuid_core.data_store import get_res_path
from ..nikke_permissions.config import ValidatedStringConfig

from ..nikke_api.resource import RESOURCE_TYPES
from .config_default import CONFIG_DEFAULT

# 目录层级（XWUID 式外壳 + 内层包）：
# <plugin_root>/AliceUID/nikke_config/config.py
PACKAGE_ROOT = Path(__file__).parent.parent
PLUGIN_ROOT = PACKAGE_ROOT.parent

MAIN_PATH = get_res_path() / "AliceUID"
MAIN_PATH.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = MAIN_PATH / "config.json"
DATA_PATH = MAIN_PATH / "static"
DATA_PATH.mkdir(parents=True, exist_ok=True)
RESOURCE_PATH = MAIN_PATH / "resource"
CACHE_PATH = MAIN_PATH / "cache"
PLAYER_PATH = MAIN_PATH / "players"
for directory in (*(RESOURCE_PATH / item.directory for item in RESOURCE_TYPES.values()), CACHE_PATH, PLAYER_PATH):
    directory.mkdir(parents=True, exist_ok=True)

# 随插件分发的静态表（角色/词条/关卡）与登录页素材
PACKAGE_DATA_PATH = PACKAGE_ROOT / "data"
ASSETS_PATH = PLUGIN_ROOT / "assets"

AliceUIDConfig = ValidatedStringConfig(
    "AliceUID", CONFIG_PATH, CONFIG_DEFAULT,
    legacy_path=MAIN_PATH / "group_policy.json",
)

from ..nikke_render.fonts import install_font_options
install_font_options(AliceUIDConfig)
