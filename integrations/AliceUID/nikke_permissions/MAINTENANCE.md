# AliceUID 权限维护边界

## 最终规则

- 群和用户分别拥有白名单、黑名单。每一对均为空时默认允许；白名单非空先限定允许范围，再排除黑名单。旧 `mode=whitelist` 空表不再全禁，mode 仅兼容记录。
- 同一个字符串 ID 出现在同类白黑两表时拒绝保存，保留该次修改前的值。群 ID 与用户 ID 是不同命名空间。
- 所有名单聊天写操作只认 core 核实后的 `type(ev.user_pm) is int and ev.user_pm == 0`。`AliceUID_MasterQQ`、群主、群管理员、字符串 `"0"` 与布尔值均不能提升权限。
- 用户策略统一限制群聊、私聊中的所有 AliceUID Trigger，包括登录、帮助、UID 维护和权限管理。Bot 主也不能绕过非空用户白名单或用户黑名单；无 `maintenance=True` 白名单豁免，也无聊天恢复后门。被排除的 Bot 主使用受认证的 core 后台修复名单。
- 群查询策略由查询入口调用 `await policy.query_allowed(ev.group_id)`；私聊无群 ID 时不受群名单限制。用户策略仍然生效。群管理员只能查看本群状态，不能用旧本群开关移除 Bot 主名单；Bot 主“开启本群”仅移除群黑名单，不覆盖非空群白名单。
- 不清理、不改写用户已有 core 插件/SV 原生黑白名单、开关或 pm。原生分发权限额外生效，可能在插件 guard 之前拒绝事件；本插件不能绕过。禁止直接修改 core 源码来实现本策略。

## 接口与集成

`GroupPolicy(path, *, config=None)` 提供同步 `user_allowed(user_id)`、异步 `query_allowed(group_id)`、`snapshot()`、`update_list(list_name, id, *, add)`。`setup(path, *, config=None, permission_of=None, register=True)` 返回同一策略对象并注册权限 SV；`register=False` 适合离线测试。默认认证权限来源是 `ev.user_pm`。

四项默认值须使用 core 的 `GsListStrConfig`，均默认 `[]`：

| 配置 key | 策略 list_name |
| --- | --- |
| `AliceUID_GroupWhitelist` | `whitelist` |
| `AliceUID_GroupBlacklist` | `blacklist` |
| `AliceUID_UserWhitelist` | `user_whitelist` |
| `AliceUID_UserBlacklist` | `user_blacklist` |

配置模块首次构造必须使用工厂，不能先让原生 `StringConfig` 用同名配置进入 core 缓存：

```python
from ..nikke_permissions.config import ValidatedStringConfig

AliceUIDConfig = ValidatedStringConfig(
    "AliceUID", CONFIG_PATH, CONFIG_DEFAULT,
    legacy_path=MAIN_PATH / "group_policy.json",
)
```

工厂返回真正的 core `StringConfig` 子类实例，保留 core 类型、配置注册、原子文件写入及后台保存链。初始化前检查四名单原始 JSON，`set_config` 校验候选名单后再交给 core 保存，`write_config` 再校验一次。旧 JSON 仅在源配置尚无任何四名单 key 时迁移，旧文件保留；只出现部分 key 视为损坏，拒绝补空开放。四 key 已存在后以 Source config 为权威，不再读旧 JSON。旧 `groups` 中关闭项迁为群黑名单；若与旧白名单冲突则明确报错，不选边覆盖。

root 的最小集成如下（所有其他 SV 导入与 setup 必须在最后 guard 之前完成）：

```python
from gsuid_core.sv import SL
from .nikke_config.config import MAIN_PATH, AliceUIDConfig
from .nikke_permissions.commands import setup
from .nikke_permissions.access import guard_plugin_triggers

policy = setup(MAIN_PATH / "group_policy.json", config=AliceUIDConfig)

# 所有其他命令模块导入、setup(...)，并向查询/HTTP/后台任务注入同一个 policy。
# 查询入口按需检查：await policy.query_allowed(ev.group_id)
# HTTP/后台用户行为按认证后的实际用户检查：policy.user_allowed(user_id)

guard_plugin_triggers(SL.plugins["AliceUID"], policy)
```

`guard_plugin_triggers(plugin_or_name, policy)` 返回本次新增包装数；同一策略重复调用返回 0。它动态扫描 `SL.detail_lst[plugin] -> SV.TL[type][key] -> Trigger.func`，不维护命令名清单。使用真实 core `modify_func` 的包装形态，把检查放在其 try/finally 内，保留拒绝和发送失败时的 Bot 实例清理。运行期再新增 Trigger 后须再次调用 guard。它覆盖已注册聊天 Trigger，不自动拦截 HTTP、定时任务、AI 工具直接调用、模块内部函数直接调用；这些入口由主代理注入同一策略分别检查。

## 保存、损坏与批量边界

固定参考 core 提交为 `1ce50ba381e0d9f48dc42385e35a7310dc5ed0f4`。已核对 `sv.py`、`trigger.py`、`utils/plugins_config/{gs_config,models}.py` 与 `webconsole/plugins_api.py`；参考代码仅读取/AST 检查，不执行。

真实后台链为 `_write_config_item -> config_obj.set_config -> self.write_config`。单项名单输入错误或与对表交叉时返回 False，保留内存和磁盘旧值。插件内部四名单更新先统一验证，再调用一次 core 写入；IO 异常时恢复内存并抛错。

**core 后台批量保存逐项执行，不是全框架事务。** 先成功的项目不会因后项失败而回滚；`POST /api/plugins/{plugin_name}` 只要有任一项成功就可能返回 status=0。因此界面显示“已保存”不能证明本批每项均成功，保存后应回读四项。白→黑移动 ID 时先从白名单删除再加黑；反序会拒绝冲突项。本模块不改 core 路由的部分成功语义。

策略文件缺失使用默认值；已存在但为空、null、空对象、格式错误、非法 ID 或名单冲突时，策略读取拒绝访问，管理操作明确报错并保留原文件。Source config 初始化/刷新前同样校验；若 core 自动修复可能重置已有权限条目，则报错请 Bot 主修复原文件，防止静默恢复空名单。正常 core 配置对象从内存读取；人工编辑源 JSON 后需正常刷新配置或重启，不能假定每条命令会重新加载配置文件。

独立旧 JSON 模式用同目录临时文件、flush/fsync、os.replace 保存；同一进程同规范化路径共用 asyncio.Lock。Source config 模式用进程内 RLock 协调四名单读取/保存。均不承诺跨进程并发事务；部署须统一写入者。直接改内存 `.data` 不受 `set_config` 回滚保护，但 `write_config` 仍会拒绝无效名单，策略校验亦拒绝访问。

## 离线验证

```powershell
$env:PYTHONPATH='.runtime/packages'
& 'C:\Program Files\DSH Desktop\resources\office-runtime\primary-runtime\dependencies\python\python.exe' -m pytest tests/test_permissions.py tests/test_access_policy.py -q
```

套件覆盖最终空表/非空白名单规则、双向冲突拒存、严格 Bot 主权限、群管理员无旧开关绕过、用户群私聊全 Trigger 拦截且无 Bot 主维护豁免、动态注册后补 guard、幂等与其他插件隔离、Core finally 清理、Source config 真子类工厂、单项/逐项保存边界、失败回滚、旧 JSON 迁移、损坏拒绝及固定版本 AST 契约。测试使用本地轻量 harness 与固定源 AST；没有导入执行下载的 core，也不代表已完成真实机器人/HTTP 端到端部署测试。root、默认配置、HTTP 和 community 集成属于主代理工作范围。
