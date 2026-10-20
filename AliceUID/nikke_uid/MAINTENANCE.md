# UID 身份登记维护说明

本模块只保存发送者主动提供的身份标识。登记不等于登录、账号归属验证或数据已公开，不参与本人练度查询的私有认证。分享URL/Base64只在本地解析，不发送任何网络请求；用户的标识不会自动变成用于查询别人的目标。

## 文件与注册

- [store.py](<store.py>)：stdlib SQLite 独立存储、本地分享解析与摘要；不导入登录模型或游戏客户端。
- [commands.py](<commands.py>)：`SV("妮姬UID登记", pm=6, priority=3)`。提供 `nk绑定UID`、`nk我的UID`、`nk解绑UID`，注册均为 `block=True`。旧账号解绑目前使用 `on_fullmatch`，因此不会匹配UID解绑，不依赖SV优先级。真实Trigger回归会组合当前旧命令与UID命令验证这一点。所有归属均只取 `ev.user_id + ev.bot_id`，不读取提及对象作为owner。
- [模块入口](<__init__.py>)：导出纯存储接口，不自动注册命令。由插件根初始化显式导入 `nikke_uid.commands`；根初始化、帮助和旧账号命令衔接由主代理负责。
- [离线测试](<../../../tests/test_uid.py>)：禁用网络连接，验证精度、namespace并发合并、事务失败回滚、跨owner隔离、恶意URL、命令权限和无Cookie占位。

## 命令契约

```text
nk绑定UID
nk绑定UID 社区 <1至30位半角数字字符串>
nk绑定UID 游戏 日服 <1至30位半角数字字符串>
nk绑定UID 分享 <官网分享URL或Base64完整标识>
nk我的UID
nk解绑UID
```

- 无参显示三个类型的用法；禁止按位数猜测社区或游戏UID。数字字符串长度边界只用于输入限制，不代表上游已接受该ID。
- 游戏区服登记目前与已支持登录区服一致：日服、北美服、韩服、国际服、东南亚服。区服表有改动时核对[客户端区域定义](<../nikke_api/client.py>)和 `GAME_REGIONS`；登记本身不触发登录或区服探测。
- 分享只接受HTTPS，精确主机名为 `www.blablalink.com` 或 `blablalink.com`，无用户信息、无fragment，端口为空或443；路径限定 `/shiftyspad`、`/user` 及其子路径，不允许编码路径或点段。
- URL只接受唯一非空 `uid` 或 `openid` 参数。`uid`值须Base64；`openid`可为Base64或完整原始格式。裸输入须Base64。解码结果严格为 `29080-` 或 `29157-` 加9至30位半角数字。
- 游戏ID为29157的分享可以解析，但不据此推断游戏区服，也不意味着港澳台登录已支持。解析后不保存原始URL，不跟随重定向。
- 分享的openid后缀与用户输入的社区标识分别保存，不声称两者恒等。关于原始证据及匿名边界，见[UID研究](<../../../docs/15_UID与公开查询边界.md>)。

## 存储与可调用接口

`get_uid_store()` 首次调用时才导入配置并初始化 `MAIN_PATH / "uid_bindings.sqlite3"`。不要在导入阶段调用它。数据库为独立文件，不改AliceBind，不写空Cookie行，不建立凭据、密码或授权字段。

以下都是**同步方法**，调用方不使用 `await`。每次操作建立并关闭独立连接；写操作是短本地事务，SQLite等待锁上限5秒。若未来批量查询需要放入工作线程，应直接使用这些可重入的独立连接方法，不能复用跨线程连接。

```python
from .nikke_uid.store import get_uid_store, format_summary

store = get_uid_store()
record = store.get(ev.user_id, ev.bot_id)  # dict | None
text = format_summary(record)
removed = store.clear(ev.user_id, ev.bot_id)  # bool
```

- `UIDStore(path)`：适用于隔离测试或指定运行数据目录。
- `bind_community(user_id, bot_id, value) -> dict`：更新社区namespace。
- `bind_game(user_id, bot_id, region, value) -> dict`：更新游戏namespace。
- `bind_share(user_id, bot_id, value) -> dict`：本地解析后更新分享namespace。
- `get(user_id, bot_id) -> dict | None`：只读取这一owner，未知记录返回None。
- `clear(user_id, bot_id) -> bool`：删除这一owner的全部UID登记，不操作登录/社区授权；不存在返回False。
- `format_summary(record) -> str`：None也能处理；始终说明未验证归属、登记不等于登录/公开查询权限。

记录字段：

| namespace | 字段 | 约束 |
|---|---|---|
| owner | user_id、bot_id | 联合主键，两个字段均必须是非空字符串 |
| 社区 | community_uid | TEXT；只表示用户输入的社区标识 |
| 游戏 | game_uid、game_region、game_area_id、game_game_id | UID用TEXT，区服ID可用INTEGER；更换游戏登记仅替换本namespace |
| 分享 | share_intl_openid、share_game_id、share_openid_suffix | 均TEXT；不派生/覆盖community_uid或game_uid |
| 元数据 | updated_at | UTC Unix秒数，仅表示本地更新时刻 |

每次upsert使用 `BEGIN IMMEDIATE` 和参数化 `INSERT ... ON CONFLICT ... DO UPDATE`，只更新对应namespace列，不做“先读全行再写回”的竞争更新。返回记录前事务已提交；异常时回滚，不回复保存成功。主键保证每owner一行，允许不同owner登记相同公开标识，且不能因此互相读取/清除记录。

## 与旧账号命令的衔接边界

- `nk我的账号` 可读取 `get()` 并追加 `format_summary()`，但不得因UID记录存在就显示“已登录”，也不得替代原加密凭据加载逻辑。
- `nk解绑UID` 仅清UID登记。主代理如使旧 `nk解绑` 同时清理登记，应在原登录解绑成功后再调用 `clear()`，并确保失败反馈不会声称未完成的部分已成功；本模块不修改旧命令行为。
- 不把UID记录加入社区定时任务名单，不从分享标识推断本人，不能自动使用Bot主/群友Cookie代查。
- 展示、导出或网页参数中的长ID不得经JavaScript Number、浮点或数字型JSON中转；使用字符串保持精度和前导零。

## 发布与后续修改

- 运行数据库及SQLite临时文件应排除在分发包之外：`uid_bindings.sqlite3`、`uid_bindings.sqlite3-journal`、`uid_bindings.sqlite3-wal`、`uid_bindings.sqlite3-shm`。打包规则由主代理统一处理。
- 未来若增加公开查询，先逐项证实源、匿名/登录条件、隐私拒绝与缓存范围，不能因为有登记表就默认已有可用查询API。
- 未来若调整schema，应新增明确迁移并覆盖旧库读取；不能靠删除用户运行数据库升级。
- 错误日志只写阶段与异常类型，不写原始标识、完整URL、异常message或任何凭据；用户输入不进入HTML模板或文件路径。
