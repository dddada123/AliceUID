"""Collect only plugin events; never retain Core chat Event objects."""
import logging
import platform
import re
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from importlib.metadata import PackageNotFoundError, version
from ..version import VERSION, BUILD, ISSUES

TZ = timezone(timedelta(hours=8))
STARTED = time.time()
_rows = deque(maxlen=10000)
_lock = threading.Lock()
_chars = 0


def redact(text):
    text = re.sub(r'https?://[^\s<>]+', '[链接已脱敏]', str(text))
    text = re.sub(r'(?i)(cookie|authorization|password|passwd|token|secret|email|account|openid|nickname|user_id|group_id|验证码|密码|昵称)[\s\x22\x27]*[:=][^\n]*', r'\1=[已脱敏]', text)
    text = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[邮箱已脱敏]', text)
    text = re.sub(r'\b\d{5,}\b', '[编号已脱敏]', text)
    text = re.sub(r'\b[A-Za-z0-9_-]{28,}\b', '[标识已脱敏]', text)
    return text.replace('```', '[代码围栏]').replace('\x1b', '')[:4096]


def append(stamp, level, text):
    global _chars
    text = redact(text)
    with _lock:
        if not _rows:
            _chars = 0
        if len(_rows) == _rows.maxlen:
            _chars -= len(_rows.popleft()[2])
        _rows.append((stamp, level, text))
        _chars += len(text)
        while _rows and (_rows[0][0] < stamp - 86400 or _chars > 2_000_000):
            _chars -= len(_rows.popleft()[2])


class PluginHandler(logging.Handler):
    def emit(self, record):
        value = record.msg
        if isinstance(value, dict):
            text = str(value.get('event', ''))
            plugin = value.get('plugin', '')
        else:
            text, plugin = record.getMessage(), ''
        if not (text.lstrip().startswith('[AliceUID]') or plugin == 'AliceUID'):
            return
        append(record.created, record.levelname, text)


def setup():
    host = logging.getLogger('GsCore')
    for handler in list(host.handlers):
        if handler.name == 'AliceUIDDiagnostics':
            host.removeHandler(handler)
            handler.close()
    handler = PluginHandler(level=logging.DEBUG)
    handler.name = 'AliceUIDDiagnostics'
    host.addHandler(handler)


def export_markdown(minutes, core_rows=(), now=None):
    if not 1 <= minutes <= 1440:
        raise ValueError('分钟数必须为1～1440的整数。')
    now = time.time() if now is None else now
    since = now - minutes * 60
    with _lock:
        rows = list(_rows)
    # Core supplies an additional bounded history for events before setup.
    for row in core_rows:
        if row.plugin != 'AliceUID':
            continue
        try:
            stamp = datetime.fromisoformat(row.timestamp.replace('Z', '+00:00'))
        except ValueError:
            continue
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=TZ)
        rows.append((stamp.timestamp(), row.level, redact(row.gevent.splitlines()[0] if row.gevent else '')))
    rows = sorted(set((stamp, level, text) for stamp, level, text in rows if since <= stamp <= now))
    try:
        playwright_version = version('playwright')
    except PackageNotFoundError:
        playwright_version = '未安装'
    try:
        core_version = version('gsuid-core')
    except PackageNotFoundError:
        try:
            from gsuid_core.version import __version__ as core_version
        except ImportError:
            core_version = '未知（当前环境未提供版本元数据）'
    def clock(stamp):
        return datetime.fromtimestamp(stamp, TZ).isoformat(timespec='seconds')
    lines = ['# AliceUID 插件诊断日志', '', f'- 插件版本：{VERSION}；构建：{BUILD}',
             f'- GsCore：{core_version}；Playwright：{playwright_version}',
             f'- Python：{platform.python_version()}；平台：{platform.system()} {platform.machine()}',
             f'- 请求范围：{clock(since)} ～ {clock(now)}（最近{minutes}分钟，Asia/Shanghai）',
             f'- 采集器启动：{clock(STARTED)}；导出条数：{len(rows)}',
             '- 仅插件日志。内存最多10000条/约2MB/24小时，重启会清空；Core补充历史也有容量限制，范围内记录可能不完整。',
             '- 标识、凭据和链接已脱敏；无原始聊天、账号数据或完整请求正文。',
             '- stage表示失败阶段；TIMEOUT为等待超时，ERR_*为网络类别，MISSING_BINARY为缺配套浏览器。', '', '```text']
    lines.extend(f'{clock(stamp)} [{level}] {text}' for stamp, level, text in rows)
    if not rows:
        lines.append('该时间范围没有可用的插件日志；不代表期间没有错误。请复现后再次导出。')
    lines.extend(['```', ''])
    lines.extend(['## 提交Issue', '', f'问题反馈：{ISSUES}', '',
                  '- 触发命令（请脱敏）：', '- 预期结果：', '- 实际结果与发生时间：',
                  '- Core、QQ接入端分别部署在宿主机还是容器：',
                  '- 复现步骤及已尝试操作：', '',
                  '附件前请再次检查是否包含私人信息；日志容量限制或重启可能导致历史不完整。', ''])
    return '\n'.join(lines).encode('utf-8')
