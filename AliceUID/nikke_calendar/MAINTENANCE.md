# 官网活动日历截图维护说明

本模块只截取 https://www.blablalink.com/activity-calendar 的当前默认活动日历。输出为**裁剪日历内容的完整长图**，不是整站页面截图；展开网页原有内部滚动容器，隐藏导航、侧栏及 Cookie 横幅，不修改、补写或虚构活动文本。当前不支持历史月份、指定日期或区服切换，也不要求绑定游戏账号。

截图**不会按账号绑定区服自动筛选**，不保证覆盖全区服。多皮肤/招募活动标签只展示网页默认当前选中项，不逐个点击所有标签，不代表已展开所有卡池或皮肤详情。图片中的 Raid/单人突袭只证明官网日历存在该活动及其时间，**不代表已提供阵容、分数或Raid业务API**。caption 与命令帮助均提示这些边界。

## 集成及调用

根包由集成方调用一次（函数自身幂等）：

```python
from .nikke_calendar.commands import setup as setup_calendar
setup_calendar()
```

仅注册一个 `SV('妮姬活动日历', pm=6, priority=3)` 和一个 `日历` 命令。`nk日历` 发图，`nk日历 帮助` 或任何非空参数返回用法，避免多个前缀处理器重复响应。回调先使用 `GroupPolicy(MAIN_PATH / 'group_policy.json').query_allowed(ev.group_id)`；禁用群在服务创建、浏览器及网络访问前返回。不读取绑定、他人资料或凭据。

```python
from .nikke_calendar.service import get_calendar
result = await get_calendar().get()
# result.png: bytes
# result.captured_at: Unix seconds
# result.stale / result.from_cache: bool
caption = result.caption()  # 固定来源URL、实际拍摄时间UTC+8、旧图提醒
```

测试及工具可独立构造 `CalendarService(root, capture=async_callable, clock=callable, channel='msedge')`；`capture` 返回 PNG 字节。默认 `get_calendar()` 懒加载 `MAIN_PATH` 和现有 `AliceUID_BrowserChannel`，无新增配置。`auto` 依次尝试 Playwright Chromium、Edge，`chromium/msedge` 使用指定通道。

## 截图校验

每次真正拍摄均启动独立 headless 浏览器与全新匿名 `new_context`，不使用 persistent profile、storage state、Cookie、登录浏览器或用户凭据。固定 viewport 1440×1000、缩放1、语言 zh-TW、时区 Asia/Shanghai。

固定 URL 导航必须返回 200，且最终 URL 不得跳转到登录或其他路径。DOM 必须唯一匹配 `[class*="bg-calendar-line"]`，可见且出现至少三个 `calendar-title.png` 分类、至少两个实际活动日期时间、至少100字可见文本，没有可见 loading/skeleton/aria-busy 标志或密码登录输入框。等待真实图片 `complete && naturalWidth > 0`、字体就绪以及两次绘制帧后裁剪截图，不以任意固定 sleep 判定成功。

长图布局宽960px，展开日历的滚动祖先。注入仅影响可见性的样式，确保晚插入的 Cookie 横幅不会盖住内容。PNG 必须≤12MiB、≤1600万像素、宽300—2000px、高200—12000px；超过上限整体拒绝，保留旧图，不悄悄裁掉尾部。不保存或发送错误页/空骨架作为日历。

官网可能调整类名、日期格式、分类布局或登录要求。若校验失败，应重新匿名实测并审阅真实 DOM，再更新显式校验；不得删除校验后直接截错误页。

## 缓存及冷却

正式缓存位于 `MAIN_PATH/cache/calendar/current.png` 和 `current.json`，通过临时文件加 `os.replace` 原子替换。元数据字段：

- `version`: 1
- `url`: 固定官网日历 URL
- `captured_at`: PNG 实际拍摄完成时间，Unix seconds
- `last_attempt`: 最近拍摄尝试开始时间
- `retry_after`: 下次允许尝试的最早时间
- `sha256`: PNG 字节 SHA-256

有效缓存30分钟；模块独立全局 `asyncio.Lock` 串行化所有实例和群请求，排队者重新检查落盘缓存，避免同一进程多群同时打开浏览器。开始截图前持久化至少5分钟冷却，失败后从失败完成时再次延长至少5分钟；重启同样读取冷却。截图总超时150秒。此实现针对一个 Bot 进程，多进程共享同一路径需要额外跨进程协调。

校验旧图的 URL、时间、真实 PNG、大小和 SHA-256 后才可复用。过期图更新失败时保留并返回旧图，caption 明确“官网暂不可用”“旧缓存”、原拍摄时间和活动可能变化；没有可用旧图时只返回文字失败消息。查询命令不提供强刷参数，群用户不能绕过缓存/冷却。

## 验证状态

**Live verified（官网匿名实测）**：2026-10-17 18:52:33 UTC+8，正式 `CalendarService` 通过新匿名 Edge context 获取官方页面，响应200，无登录墙；人工 `read_image` 核验完整长图包含队员招募、最新时装、版本活动、Raid、模拟室和竞技场直到决赛，且无 Cookie 横幅/侧栏遮挡。代表图为工作区 `.runtime/calendar-live-verified.png`，960×2911，1,447,532字节，SHA-256 `debec01388699bb0e8a6212968de30f0154be234b12fa8702055c831de7facbb`。对应实测缓存元数据在 `.runtime/calendar-live-cache-v2/current.json`。这些是开发验收产物，不应当作永远最新的官网活动图发布。

**Mock tested（离线测试）**：最终 `tests/test_calendar.py` 为 **32 passed**；与资源类型测试合跑为 **77 passed**。日历测试通过注入截图函数、时钟、模拟页面和群策略，覆盖并发去重、重启缓存、失败降级/冷却、哈希及尺寸限制、错误状态/跳转/登录/骨架拒绝、权限先于网络、无需绑定、帮助无网络和单次pm6命令注册。模拟测试不代表实时官网可用性，也不等同于已在真实群适配器发图验收。

本模块不修改根包、帮助图或配置；集成和群适配器发送验收由主代理负责。
