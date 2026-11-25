"""Bot-owner read-only self-check (nk自检) and safe regenerable cache cleanup (nk清理缓存)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from time import monotonic
from urllib.parse import urlparse


def _pkg_version(name: str, dist_name: str | None = None) -> str:
    if importlib.util.find_spec(name) is None:
        return '未安装'
    try:
        from importlib.metadata import version
        return f'已就绪（{version(dist_name or name)}）'
    except Exception:
        return '已就绪'


def _dir_stats(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    files, total_bytes = 0, 0
    for item in path.rglob('*'):
        if item.is_file():
            files += 1
            try:
                total_bytes += item.stat().st_size
            except OSError:
                pass
    return files, total_bytes


def _format_mb(total_bytes: int) -> str:
    return f'{total_bytes / (1024 * 1024):.2f} MB'


def _check_login_url(url: str) -> str:
    raw = str(url or '').strip()
    if not raw:
        return '⚠️ 未填写（留空将使用 Core HOST:PORT，群友外网可能无法访问）'
    parsed = urlparse(raw if '://' in raw else f'http://{raw}')
    host = (parsed.hostname or '').lower()
    if host in ('127.0.0.1', 'localhost', '0.0.0.0', '::1') or host.startswith(('10.', '192.168.', '172.16.', '172.17.', '172.18.', '172.19.', '172.2', '172.30.', '172.31.')):
        return '⚠️ 当前为本地/内网地址，公网群友可能无法打开'
    return f'✅ 已配置（{parsed.scheme or "http"}://{host}）'


async def run_self_check() -> str:
    from ..version import VERSION, BUILD
    from ..nikke_config.config import MAIN_PATH, AliceUIDConfig
    from ..nikke_commands import command_prefix

    lines = [f'[AliceUID·插件自检] 版本 {VERSION}（构建 {BUILD}）']

    # 1. Runtime & dependencies
    py_ver = f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'
    deps = [
        f'Python {py_ver}',
        f'GsCore {_pkg_version("gsuid_core")}',
        f'PyTakumi {_pkg_version("pytakumi")}',
        f'Playwright {_pkg_version("playwright")}',
        f'XlsxWriter {_pkg_version("xlsxwriter", "XlsxWriter")}',
        f'OpenCC {_pkg_version("opencc", "opencc-python-reimplemented")}',
        f'QRCode {_pkg_version("qrcode")}',
    ]
    lines.append('• 运行环境：' + ' ｜ '.join(deps))

    # 2. Key configuration health
    login_url = AliceUIDConfig.get_config('AliceUID_LoginUrl').data
    require_https = bool(AliceUIDConfig.get_config('AliceUID_LoginRequireHTTPS').data)
    write_ops = bool(AliceUIDConfig.get_config('AliceUID_EnableWriteOps').data)
    auto_cdk = bool(AliceUIDConfig.get_config('AliceUID_AutoCDKEnabled').data)
    comm_paused = bool(AliceUIDConfig.get_config('AliceUID_CommunityPaused').data)

    lines.append(f'• 登录外网地址：{_check_login_url(login_url)}（HTTPS要求：{"开" if require_https else "关"}）')
    if write_ops and auto_cdk:
        cdk_status = '✅ 允许兑换 + 自动兑换总开关均已开启'
    elif not write_ops:
        cdk_status = '⚠️ 「允许本人CDK兑换」（AliceUID_EnableWriteOps）未开启，无法执行兑换'
    else:
        cdk_status = '⚠️ 自动兑换总开关已关闭（手动兑换可用）'
    lines.append(f'• 兑换码权限：{cdk_status}')
    lines.append(f'• 社区任务状态：{"⚠️ 全局已暂停" if comm_paused else "✅ 正常运行中"}')

    # 3. Forward circuit breakers
    try:
        from ..nikke_message import _paused, _image_paused, _login_paused
        now = monotonic()
        tripped = []
        for label, store in (('文本', _paused), ('含图', _image_paused), ('登录', _login_paused)):
            active = [int(exp - now) for exp in store.values() if exp > now]
            if active:
                tripped.append(f'{label}通道冷却中({max(active)}s)')
        lines.append('• 合并转发通道：' + ('⚠️ ' + '、'.join(tripped) if tripped else '✅ 全部正常（无熔断）'))
    except Exception:
        pass

    # 4. Data & cache stats
    try:
        from ..nikke_user.models import AliceBind
        binds = await AliceBind.get_all_binds()
        bind_count = len(binds)
    except Exception:
        bind_count = -1
    try:
        from ..nikke_resource.service import get_resources
        static_count = len(get_resources().load_static().characters)
    except Exception:
        static_count = -1
    try:
        from ..nikke_guide.service import get_guide_service
        guide_count = get_guide_service().store.count_posts()
    except Exception:
        guide_count = -1

    cache_root = MAIN_PATH / 'cache'
    cache_files, cache_bytes = _dir_stats(cache_root)
    lines.append(
        f'• 本地数据：绑定账号 {bind_count if bind_count >= 0 else "未知"} 个'
        f' ｜ 角色库 {static_count if static_count >= 0 else "未知"} 名'
        f' ｜ 攻略索引 {guide_count if guide_count >= 0 else "未知"} 篇'
    )
    lines.append(f'• 可再生缓存总计：{cache_files} 个文件，共 {_format_mb(cache_bytes)}（可用 {command_prefix()}清理缓存 查看分项）')
    return '\n'.join(lines)


CACHE_TARGETS: dict[str, tuple[str, ...]] = {
    '攻略': ('guide', 'raid_guide'),
    '日历': ('calendar',),
    '突袭': ('solo',),
    '帮助': ('help',),
    '图鉴': ('roster', 'resource_images'),
    '卡片': ('roster', 'resource_images', 'panels_renders'),
}


def cache_overview(prefix: str) -> str:
    from ..nikke_config.config import MAIN_PATH
    cache_root = MAIN_PATH / 'cache'
    lines = ['[AliceUID·缓存概览]（清理不影响账号绑定、密钥或数据库账本）']
    for name in ('卡片', '攻略', '日历', '突袭', '帮助'):
        files, total = _target_stats(cache_root, CACHE_TARGETS[name])
        lines.append(f'• {name}：{files} 个文件（{_format_mb(total)}）')
    lines.append(f'用法：{prefix}清理缓存 [卡片/攻略/日历/突袭/帮助/全部]')
    return '\n'.join(lines)


def _target_stats(cache_root: Path, buckets: tuple[str, ...]) -> tuple[int, int]:
    files, total = 0, 0
    for bucket in buckets:
        if bucket == 'panels_renders':
            p_root = cache_root / 'panels'
            if p_root.exists():
                for item in p_root.rglob('render-*'):
                    if item.is_file():
                        files += 1
                        try:
                            total += item.stat().st_size
                        except OSError:
                            pass
        else:
            f, b = _dir_stats(cache_root / bucket)
            files += f
            total += b
    return files, total


def clean_cache(target: str) -> str:
    from ..nikke_config.config import MAIN_PATH
    from ..nikke_commands import command_prefix
    key = str(target or '').strip()
    if not key:
        return cache_overview(command_prefix())
    if key == '全部':
        buckets = tuple(dict.fromkeys(b for grp in CACHE_TARGETS.values() for b in grp))
    elif key in CACHE_TARGETS:
        buckets = CACHE_TARGETS[key]
    else:
        return f'未知缓存分类「{key}」。可用：{command_prefix()}清理缓存 [卡片/攻略/日历/突袭/帮助/全部]'

    cache_root = MAIN_PATH / 'cache'
    removed_files = 0
    removed_bytes = 0
    for bucket in buckets:
        if bucket == 'panels_renders':
            p_root = cache_root / 'panels'
            if p_root.exists():
                for item in list(p_root.rglob('render-*')):
                    if item.is_file():
                        try:
                            sz = item.stat().st_size
                            item.unlink()
                            removed_files += 1
                            removed_bytes += sz
                        except OSError:
                            pass
        else:
            b_root = cache_root / bucket
            if b_root.exists():
                for item in list(b_root.rglob('*')):
                    if item.is_file():
                        try:
                            sz = item.stat().st_size
                            item.unlink()
                            removed_files += 1
                            removed_bytes += sz
                        except OSError:
                            pass
    return f'[AliceUID·缓存清理完成]\n已清理「{key}」可再生缓存：{removed_files} 个文件，释放 {_format_mb(removed_bytes)}。'
