# 邮箱验证码登录维护说明

1.0.25状态：发布级EMAIL_LOGIN_AVAILABLE=False，接口与代码保留，页面置灰并显示“暂时不开放邮箱验证码登录接口，故障排查中。”。以下原流程说明供排查维护，不能视为当前生产已开放。确认根因并通过对应测试后再调整发布开关。

适用模块：AliceUID 网页绑定。实现日期与公开页面核对日期：2026-10-17。

## 行为与验收边界

页面默认「账号密码」。切换「邮箱验证码」并点击「发送邮箱验证码」后才启动官方 Playwright 邮件流程；打开页面、轮询状态、切换模式都不会自动发邮件。同页「账号密码」支持邮箱（账号）+密码。两种模式都沿用原有五区服选择、人工滑块、Cookie 校验、所选区服角色检查和加密 Cookie 持久化。成功后弹窗提供「留在本页」，不会强制跳转。

已检查真实公开官网的登录弹层与邮箱表单（live UI inspected）。已通过真实 Edge + Playwright 的本地网络模拟验证发送、等待、提交、验证码无效、Cookie 无效、热切换取消与成功留页。**本次没有使用真实用户邮箱、密码或邮件验证码，没有向真实邮件服务发送或验证 OTP；真实邮件送达与真实 OTP 登录未验收。** 模拟成功不代表真实 OTP 已验收。

## 官方流程证据

公开来源：

- 社区入口：https://www.blablalink.com/
- 官方登录 UI SDK：https://common-web.intlgame.com/sdk-cdn/infinite-pass/latest/index.umd.js
- UI 加载的语言资源（当次版本 1.32.0）：https://common-web.intlgame.com/li-pass/static/locale/zh-TW/common.json?version=1.32.0

无凭据打开首页登录弹层，默认密码表单提供「電郵登入」；切换后实际 DOM 为：

| 用途 | 实际选择器 / 标签 |
| --- | --- |
| 切换邮箱 | `get_by_text('電郵登入', exact=True)` |
| 邮箱表单 | `#loginCodeForm` |
| 邮箱地址 | `#loginCodeForm_account` |
| 验证码 | `#loginCodeForm input[placeholder="電郵驗證碼"]` |
| 发码按钮 | 表单内 `get_by_role('button', name='獲取', exact=True)` |
| 提交按钮 | `#loginCodeForm button[type="submit"]`，标签「註冊/登入」 |

官方提示「自動註冊新電郵地址」，本插件也提醒用户使用已有游戏账号邮箱。

SDK 调用 `requestVerifyCode`，参数包含 `account`、`account_type`、`code_type`（login）、`support_captcha`；需要时先运行腾讯滑块。成功 `ret === 0`，机器验证分支为 2170。提交调用 `verifyCodeSignIn`，参数包含 `account`、`account_type`、`verify_code`、`only_login_type`。

为确认实际端点，调研中以 `offline@example.invalid` / `00000` 作为纯模拟输入，在填写前启用 Playwright 路由拦截所有非 GET/HEAD 请求，并本地模拟腾讯验证码回调。以下请求仅被浏览器生成并在本地拦截，没有发送到认证服务：

| 操作 | 已观察端点 | 观察到的字段键 |
| --- | --- | --- |
| 发码 | `POST https://li-sg.intlgame.com/account/sendcode` | `account`, `account_type`, `code_type`, `device_info`, `machine_check_type`, `support_captcha`, `tencent_response` |
| 提交 | `POST https://li-sg.intlgame.com/account/loginwithcode` | `account`, `account_type`, `device_info`, `only_login_type`, `verify_code` |

生产实现只操作官方 UI、监听这些已核实端点的响应；不自行拼装或签名认证 HTTP 请求。官方倒计时在请求完成前已经开始，**不能作为发码成功证据**。只有 `/account/sendcode` 的 HTTP 200 且整数 `ret=0` 才进入 `awaiting_code`。登录 `ret=0` 也不直接绑定，仍必须读取 `logined_account_cache_key`、取得 openid/token、通过 CheckLogin 和所选区服角色检查。无效验证码页不会被判定为成功。

## 状态与取消

状态链：`created -> sending_code -> [captcha] -> awaiting_code -> logging_in -> [captcha] -> success/failed`；密码沿用 `created -> logging_in -> [captcha] -> success/failed`。

- `SessionStore.active()` 将 `sending_code`、`awaiting_code`、`logging_in`、`captcha` 全部视为活动；同一用户 / Bot 不允许另开区服任务。
- 活动操作以 `operation_started_at` 为准，不因原链接 TTL 到期而中断，存储硬上限仍为 360 秒。浏览器 OTP 操作上限 330 秒；密码仍 180 秒。
- 官方确认发码后，本地最多等待验证码 240 秒，且不会超出本次操作第 330 秒。这是本插件等待上限，不冒充官方验证码真实有效期。
- 每次启动或切换递增 `generation`。切换 / 取消 / 过期 / `clear_owner` 均取消活动 task，清除验证码与滑块。回调、成功回填和 `save_login(still_current=...)` 同时检查会话身份与代次，旧任务即使忽略取消而返回也不能保存。
- HTML 使用 `viewEpoch` 丢弃旧轮询、图片加载、滑块请求及延迟回调。启动请求短暂锁定切换按钮，收到代次后即可在活动任务中切换。
- 页面关闭尝试 `sendBeacon` 明确取消，切模式也立即取消。进程内每 5 秒检查心跳，非 `awaiting_code` 状态超过 35 秒未收到状态轮询即终止浏览器；`awaiting_code` 在当前 `code_deadline` 前保留任务，允许手机切到邮箱 App 后页面 JS 冻结 60–120 秒再返回。宽限只覆盖既有最多 240 秒取码窗口，浏览器 330 秒 / 会话 360 秒总上限不变。接受当前验证码提交时刷新心跳，用户无需先轮询即可直接提交；此后恢复 35 秒规则。明确关闭不使用取码宽限，未能送达关闭信号时最多等待至取码截止。
- `clear_owner(user_id, bot_id)` 取消该用户该 Bot 的任务，不影响其他 Bot。保留成功会话 300 秒展示宽限期。

## 冷却与秘密数据

每次显式发码动作先预留 60 秒冷却；官方确认实际发码成功后再保证完整 60 秒间隔，避免滑块耗时较长时刚发出即可重发。即使浏览器启动或官方发码失败也不会立即再次发送。限制同时作用于 `(bot_id, user_id)` 和归一化邮箱 SHA-256 两个独立桶；换链接、换模式、换用户都不能绕过同一进程中的邮箱冷却。邮箱原文不进入冷却桶。不自动重发、不自动提交 OTP；冷却结束只恢复用户按钮。

冷却与登录会话均为**进程内状态**，当前适用于单进程部署。重启会清空；多 worker 需要将会话和限流迁移至共享存储，不能单独开启多个 worker 后假定全局限流。

密码和验证码仅在请求、协程和浏览器内存中使用。验证码提交等待官方请求发出后立即清空官方输入；本地网页、Payload 和 Session 中的验证码用后清除，取消与失败也清除。未记录账号、密码、验证码、Cookie 或官方响应原文。监听器只保留 `ret` 判定和固定中文提示。Cookie 仍只交给既有加密 `save_login`；成功会话不保留 LoginResult。`BindingPersistenceError` 显示「保存未确认」，不会显示绑定成功。

Cookie-only 配置下，两种账密表单均隐藏并禁用；密码登录、发码和验证码提交接口均返回 403。原 Cookie 导入仍可用，并增加代次守卫，避免模式切换后旧请求回填。

## 接口集成

不需要修改 `commands.py`。现有 `sessions.active` 与解绑后的 `sessions.clear_owner` 自动涵盖新状态与取消行为。保留原密码 `login(account, password, ..., on_captcha=...)` 接口；邮箱仅新增可选 `on_code` 回调。

新增路由：

- `POST /nikke/api/mode`：`token`, `mode=email|password|cancel`, `generation`；响应新代次。
- `POST /nikke/api/email/send`：`token`, `account`, `generation`；只启动一次官方发送。
- `POST /nikke/api/email/verify`：`token`, `code`（5位数字）, `generation`；只接受当前 `awaiting_code`。
- 原 status 新增 `mode`, `generation`, `retry_after`, `code_expires_in`；不返回邮箱、密码、验证码或 Cookie。

`tests/test_login.py` 未修改，也未修改其他代理负责的 `commands.py`。

## 离线验证与升级

在工作区根目录运行：

```powershell
$env:PYTHONPATH='.runtime/packages'
& 'C:\Program Files\DSH Desktop\resources\office-runtime\primary-runtime\dependencies\python\python.exe' -m pytest tests/test_email_login.py tests/test_login.py -q
```

最终运行结果：**56 passed in 30.91s**（2026-10-17；56项包含参数化用例，含手机邮箱 App 后台取码宽限修复）。

测试包含：原五区服 / 滑块 / Cookie-only / 成功留页回归；显式发码；用户和邮箱冷却；重复与过期验证码；双并发发送；旧任务忽略取消仍不得保存；跨 Bot 清理隔离；原链接 TTL 到期后可完成；360 秒存储上限；手机取码后台 60 / 120 秒后直接提交仍可完成、同样后台条件下明确关闭 / 切模式仍取消、其他阶段 35 秒断联停止；验证码等待上限；持久化失败；真实 Edge 中的官方表单模拟、完整 browser.login 的 Cookie 校验、HTML 默认 OTP、OTP 成功和切换密码成功。所有认证、Cookie 校验与角色请求均使用本地 fixture / AsyncMock，禁止将测试替换为真实用户资料。

官方更新后先无凭据检查上述选择器与 SDK 分支；如需观察请求，必须先拦截发码和验证请求，再填写 `example.invalid` 模拟输入。检查 `sendcode` 成功判定与 `loginwithcode` 错误分支，运行回归；端点或选择器改变时更新 `email_flow.py` 与对应测试。若无法确认官方流程，应明确报告证据缺口并保持失败关闭，不添加猜测接口或用倒计时 / 无效验证码提示代替成功。
