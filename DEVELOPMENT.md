# AliceUID 开发文档（1.4.02）

本文档为 **AliceUID 1.4.02** 的完整技术架构、协议契约与工程维护参考，按模块整合了 `1.0.x`～`1.4.02` 全部仍在生效的设计约束、参数口径与安全边界。已被后续版本替代的早期试错记录及逐版变更细节均已完整归档至 [`assets/doc_backup/`](assets/doc_backup/)。

> 社区 HTTP 端点与字段口径基于当前已核验的适配实现，不代表上游提供永久稳定承诺。

---

## 1. 插件结构、生命周期与命令路由

### 1.1 目录结构与启动顺序
插件采用 GsCore 嵌套外壳结构（`plugins/AliceUID/AliceUID/`），核心入口加载顺序如下：

1. **原生前缀配置与旧配置迁移**：`nikke_commands.configure(plugin, config_path)` 必须在所有 `SV` 注册与 `StringConfig` 读取前执行。通过 Core 公开接口 `plugin_config_store` 与 `plugin.set(prefix=..., disable_force_prefix=..., allow_empty_prefix=...)` 同步前缀（Core 已有配置优先，迁移记录写入 `prefix_migration_v112.json`），随后调用 `get_plugin_available_prefix(plugin.name)` 生成启动期 `command_prefix()` 快照。**修改前缀后须完整重启 Core**。
2. **配置与权限策略**：初始化 `ValidatedStringConfig`（按 `CONFIG_DEFAULT` 稳定字典顺序输出 WebUI），合并旧 `group_policy.json` 并加载字体选项。
3. **数据模型与后台管理**：导入 `AliceBind` 并尝试挂载 Core 后台绑定摘要及受控解绑接口（不兼容时不阻塞正常加载）。
4. **模块命令、Web 路由与调度器**：注册全部 `SV` 指令、登录 HTTP 路由，并将定时任务挂载至 **Core 共享 scheduler**（禁止插件另建第二个调度器）。
5. **全局权限守卫与命令日志**：调用 `guard_plugin_triggers()` 统一包装普通命令的群/用户四名单守卫与去重匿名命令日志。

> **重要约定**：
> - `ALICEUID_STANDALONE=1` 仅供离线测试与预览渲染使用（跳过 Core 注册），生产严禁设置。
> - Core `SV` 装饰器返回仅接受 `(bot, ev)` 的包装器，共享业务逻辑必须抽离为未装饰普通函数；AI 入口必须保持 `@sv.on_*(..., to_ai=...)` 在外、`@ai_query(sv)` 在内。

### 1.2 核心模块一览

| 目录 / 文件 | 核心职责 |
|---|---|
| `AliceUID/version.py` | 运行期唯一版本号 `VERSION`、`BUILD` 与 Issue 地址（日志与帮助共用） |
| `AliceUID/nikke_config/` | `config_default.py`（后台 UI 顺序与默认值）、路径解析与配置校验 |
| `AliceUID/nikke_commands/` | Core 原生前缀同步、旧前缀迁移与 `command_prefix()` 快照 |
| `AliceUID/nikke_permissions/` | 四名单校验、Core Trigger 包装、群管理指令与按 `msg_id` 去重的匿名命令日志 |
| `AliceUID/nikke_user/` | `AliceBind`、加密凭据读写、绑定锁/CAS 重登、失效标记 `auth_state`、全量/轻量刷新与受控后台解绑 |
| `AliceUID/nikke_login/` | 显式五区选服、内存 `SessionStore`、账密/Cookie 网页导入、验证码会话与登录链接发送 |
| `AliceUID/nikke_api/` | `Credentials`、`CookieCipher`、`NikkeClient`、`cookie_import`、`StaticData` 解析与 CDN 路径混淆 |
| `AliceUID/nikke_resource/` | 7 张静态表、`ImageCache`、`display_assets`、皮肤解析、徽章/基础图标、SIFT 头像锚定与成长表 |
| `AliceUID/nikke_profile/` | Bento v3 指挥官名片（保留 `profile_classic.html`）、`slot=1..5` 排序与 `slot=3` 主推选择 |
| `AliceUID/nikke_character/` | 角色匹配、持有校验、横/纵版练度卡、装备超载词条、本地等级公式、内置/自定义别名与注销黑名单 |
| `AliceUID/nikke_roster/` | `nk卡片`（主力，任一技能 ≥ 7）与 `nk图鉴`（全量 + 灰阶未解锁）双模式独立缓存 |
| `AliceUID/nikke_export/` | 本人与公开链接的原始练度 / 1400 级内模拟导出（Excel 联动筛选 / JSON `schema_version=3`） |
| `AliceUID/nikke_guide/` | Blablalink 多作者攻略索引（SQLite）、精准/别名匹配、四档自适应并发配图、GIF 首帧截断与长图渲染 |
| `AliceUID/nikke_raid_guide/` | 联盟会战攻略（官方赛季校验、组队首图抽取与 `pytakumi` 长图保序转发） |
| `AliceUID/nikke_calendar/` | 官网活动日历（`GetCalendarDetail` + CDN 14 天素材缓存 + `pytakumi` Bento 品牌顶栏） |
| `AliceUID/nikke_union/` | 本人联盟核验、两日出刀阶段、同联盟 180s 快照、按排名查刀、历史结算归档与缓存突破角标补齐 |
| `AliceUID/nikke_status/` | 8 类资源与保管箱进度卡（固定 300s 成功图窗口）、BOSS 血量状态卡 |
| `AliceUID/nikke_harvest/` | 按会话独立订阅的 90% / 99% / 睡前收菜提醒、免打扰补检与连续两晚 100% 自动停查 |
| `AliceUID/nikke_cdk/` | 官方/GameWith/成员三源归一与跨源去重、48h 补录、自动兑换、爱丽丝已兑提醒与 `cdk.sqlite3` 账本 |
| `AliceUID/nikke_community/` | 本人授权签到/浏览/点赞、08:00 周期与随机节拍、重试/跨界保护与异常合并转发 |
| `AliceUID/nikke_solo/` | DILDORO 个人突袭（Playwright FIFO 排队、3 轮 20s 静默重试、自动套用推荐配置与韩语/降级出图） |
| `AliceUID/nikke_privacy/` | 官网妮姬资料隐私读取、个人突袭临时公开与后台 60s 持久化恢复 |
| `AliceUID/nikke_browser/` | 统一 Playwright 启动器，复用宿主包并按需补装配套 Chromium（与 AI 开关无关） |
| `AliceUID/nikke_render/` | 外置/原生 `pytakumi` 渲染适配、全局主题随机策略、字体、独立 Alpha 图标阴影与成图缓存 |
| `AliceUID/nikke_message/` | 分通道熔断合并转发、NapCat 回执超时覆盖、`preserve_order` 保序转发与爱丽丝/说明文双文风 |
| `AliceUID/nikke_help/` | 角色感知帮助（`public`/`owner` 双槽 30 天共享缓存，不含个人身份） |
| `AliceUID/nikke_database/` | 首次启动角色表更新、招募日历驱动更新与每周五 02:33 公开图库增量维护 |
| `AliceUID/nikke_logs/` | 有界脱敏诊断日志采集与 `nk日志导出`（含 `GsCore`/`Playwright`/`PyTakumi` 版本） |
| `AliceUID/nikke_uid/` | 本地 UID / 分享标识登记（不替代登录，不授权匿名查他人私人数据） |
| `AliceUID/nikke_time/` | 北京时间展示格式化与 `time_metadata`（不用于日界/过期比较） |
| `AliceUID/nikke_proxy/` | 登录浏览器代理适配（预留代理池接口，当前无每用户独立 IP） |
| `AliceUID/nikke_ai/` | 可选 GsCore AI 只读工具注册（帮助、本人资料、角色练度、别名查询四入口） |
| `AliceUID/templates/` | Jinja2 模板与 Bento v2/v3 CSS（共享 `alice_v2_tokens.css`） |
| `assets/` / `card_bg/` / `formts/` | 图标、登录图、亮/暗 6 张背景、默认字体 `AaZongYiYuan-2.ttf` 与 `assets/doc_backup/` |
| `integrations/` | 可选实验性 NapCat 原生转发配套（非默认安装前提） |

---

## 2. 身份、区服、角色/皮肤与字段口径

### 2.1 标识严格隔离（严禁混用）

| 标识 | 来源与含义 | 使用约束 |
|---|---|---|
| `user_id + bot_id` | Core 认证的消息发送者 | 绑定、权限与个人缓存唯一归属；**严禁用 `@` 对象或用户输入 UID 替代** |
| `game_id` | 游戏产品编号 | 五区统一 `29080`；港澳台 `29157` 不在登录 `REGIONS` 内 |
| `area_id` | 区服代码 | 日 `81(japan)` / 北美 `82(na)` / 韩 `83(korea)` / 国际 `84(global)` / 东南亚 `85(sea)`；港澳台 `91` 未开放登录 |
| `intl_open_id` | Cookie 对应的社区身份 | 仅用于本人私人接口；登录选服只探测所选单区，不跨区猜测 |
| `uid / role_id` | 游戏角色 UID | 来自 `GetSavedRoleInfo.role_info.role_id`（核对 `game_id`/`area_id`） |
| `name_code` | 角色逻辑主键 | 静态表、持有列表与详情匹配主键；不可直接当作美术文件编号 |
| `resource_id` | 美术资源编号 | 经 `StaticData` 由 `name_code` 映射得到 |
| `costume_id / costume_tid` | 皮肤报告 ID | 仅接受本人接口报告，经当前角色 `costumes` 映射 `costume_index` |
| `binding revision` | `sha256(cookie_enc)` | 用于会话、缓存、失效标记与后台任务版本隔离，禁止输出密文本体 |

### 2.2 角色、皮肤与核心字段映射
- **角色与皮肤解析**：`StaticData` 加载静态表；普通角色查询歧义时返回候选，不凭持有列表猜选。`resolve_skin` 优先取角色列表 `costume_id`，缺失时才回退详情 `costume_tid`（冲突以列表优先，详情 `name_code` 不匹配拒绝借用）；图库/静态清单中存在皮肤绝不证明账号拥有。
- **主页队伍与主推选择**：`profile_team` 含 `slot=1..5`（过滤 `name_code=0`/`slot=0`），按有效 `slot` 升序稳定排序。大立绘优先选 `slot=3`（无 `3` 则选首位有效角色；完全无槽位时回退战力前五第 3 名，不足 3 人用第 1 名），右侧 4 队员按 `slot=1,2,4,5` 从左到右排列。
- **主线与循环室**：`StaticData.stage_name()` 将 `48-36 HARD BOSS` 归一化为 `48-36`。循环室研究取自 `outpost_info.recycle_room_researches`：职业 `Attacker/Defender/Supporter` 对应 `1101/1102/1103`，企业 `Elysion/Missilis/Tetra/Pilgrim/Abnormal` 对应 `1201~1205`；隐藏哨兵 `-9999`/缺失/重复均显示未知，真实 `0` 保留 `Lv.0`。
- **突破与装备词条**：SSR 最多 3 星 / SR 最多 2 星 / R 无星，核心 `01~06` 与 `MAX`；武器映射 `AR/MG/SG/RL/SMG/SR`（`roledata.shot_id` 为数字外键，须由 `nikke_list` 展开）。装备词条保留原始值、类型与符号（蓄速/命中正向展示），普通装备和未知等阶不伪造 T10 词条。
- **8 类核心货币 ID**：钻石 `98+99`、信用点 `2000`、黄金积分券 `12000`、白银积分券 `11000`、战斗数据 `1000`、芯尘 `3000`、招募券 `5100`、高级招募券 `5200`；需合计项任一缺失显示未知，不补 0。保管箱占比 `outpost_battle_storage_fullness`（`0~1`），按 24 小时回满线性估算。
- **成长与模拟战力公式**：`blablalink-slider-combat-20261110-v2`（本地纯 Python，不运行第三方 JS），覆盖 1400 级查表不外推；基础暴击 `1500→15%`、暴伤 `15000→150%`，魔方按 `Lv-1`、收藏品按原始 `Lv` 索引（SSR 珍藏品面板显示 `+1`），负有效系数计 0，缺失字段标注原因且不补 0。
- **时间语义**：`nikke_time.beijing_text` 仅用于显示（北京时间）；`time_metadata` 记录 epoch、UTC/北京时间与已核对区服时间（当前仅日服 `81 → Asia/Tokyo`），**严禁将显示函数用于日界/过期比较**；`generated_at`（成图）、`checked_at`（核对）、`fetched_at`（快照）互不替代。

---

## 3. HTTP 接口、公共 CDN 与安全边界

### 3.1 私人社区客户端（`nikke_api/client.py`）
- 基地址 `https://api.blablalink.com`，数据请求默认 `zh-TW`，实例内串行且禁止重定向。
- 错误分类：`HTTP 401` 与业务 `401/300001` → `NikkeLoginRequired`（写入 `cache/auth_invalid/` 失效标记，按 owner+revision 隔离；`403/429` 不写失效标记）；业务 `code=0` 解包，其他归为 `NikkeApiError`；`212000` 立即停止且不自动重试。
- 核心代理端点（前缀 `G = /api/game/proxy/Game/`，账号体 `A = {intl_open_id, nikke_area_id}`）：
  - **账号与面板**：`GET /api/user/CheckLogin`；`POST G+GetUserCharacters` / `GetUserCharacterDetails` / `GetUserProfileBasicInfo` / `GetUserProfileOutpostInfo` / `GetUserDailyContentsProgress` / `GetSavedRoleInfo`；`POST /api/ugc/direct/standalonesite/User/GetUserGamePlayerInfo`。
  - **联盟会战**：`POST G+GetMyGuildInfo` / `GetGuildMembers` / `GetUnionRaidData` / `GetUnionRaidLevelInfo` / `GetUnionRaidDataOfGuildSeason` / `GetUnionRaidLevelDataOfGuildSeason`；公开赛季表 `/raid/raid_list.json`。
  - **社区日常**：`GET /api/lip/proxy/lipass/Points/GetTaskListWithStatusV2` / `GetUserTotalPoints`；`POST .../DailyCheckIn`；`POST /api/ugc/direct/standalonesite/Dynamics/GetPostList`（`plate_id=38`）/ `GetPost`；`POST /api/ugc/proxy/standalonesite/Dynamics/PostStar`。
  - **官网隐私（`nikke_privacy`）**：读取 `GetUserPrivacySetting`，写入 `SetUserShiftyspadPrivacy`（提交官网 6 字段完整表单，写前重读合并，仅临时改 `show_nikke_info` 并读回核验）。

### 3.2 公共资源与 CDN 映射（无凭据）
- 所有公共下载均独立于私人客户端，**绝不携带 Cookie/Authorization**。
- `obfuscate_path()` 对逻辑路径去前导斜杠后用受控 `PRIMES` + 32 位 `djb2` 计算中间目录，最终文件名为完整逻辑路径 `MD5` + 扩展名，拼至 `https://sg-tools-cdn.blablalink.com`。
- **角色三类美术**（本地名 `cNNN_SS.png` + 同名来源/SHA256 侧车 JSON，嵌入上限仅限渲染嵌入，原图不降质）：
  - `icons`：`/character/si/si_c{rid:03}_{skin:02}_s.png` → `resource/characters/icons`（嵌入上限 `256×256`）
  - `portraits`：`/character/mi/mi_c{rid:03}_{skin:02}_s.png` → `resource/characters/portraits`（`600×900`）
  - `full`：`/character/full/c{rid:03}_{skin:02}.png` → `resource/characters/full`（`1200×1800`）
- **7 张静态表**（`nikke_resource.service.TABLES`，随包兜底合并外部 `static/`）：`nikke_list_zh-TW_v2.json`、`stage_list.json`、`equip_option_table_v2-zh-tw.json`、`ItemEquipTable-zh-tw.json`、`character_skill_map.json`、`character_id_map.json`、`character_avatar_map.json`。
- **基础图标与徽章**：`base_icons.py` 登记 23 项基础图标 + 4 徽章基底（`star_active`/`star_inactive`/`core`/`power`）；URL 白名单仅限 6 武器 + 4 徽章确切地址；单图限 10MiB / 24M 像素，支持 ETag/304 与 403/429 持久冷却。

### 3.3 登录 Web、Cookie 导入与权限边界
- **登录路由（`nikke_login/routes.py`）**：`GET /nikke/assets/{filename}`（防路径穿越）、`GET /nikke/i/{token}`、`POST /nikke/api/{login,mode,email/send,email/verify,status,captcha,captcha/refresh,cookie}`。响应附 `no-store`/`no-referrer`，422 返回通用提示不回显输入。
- **会话与安全**：`SessionStore` 纯内存保存（TTL `600s`、登录流程上限 `360s`、结果保留 `300s`），全程校验 `generation` 与 `challenge_id`；`EMAIL_LOGIN_AVAILABLE = False` 发布级禁用邮箱验证码（路由返回 503）；`LoginRequireHTTPS=True` 时严格校验 ASGI `https` scheme，不盲信 `X-Forwarded-Proto`。
- **Cookie 导入**：`nikke_api/cookie_import.py` 解析请求头与 Netscape 7 列（≤256KiB），仅保留 `api.blablalink.com` 有效 `game_*` 白名单字段；前端默认 `-webkit-text-security: disc` 打码（不支持时回退星号层）；入库前验证 `CheckLogin` 与 `selected_role`、35 秒页面心跳及原绑定版本。
- **绑定生命周期与后台管理**：`save_login()` 在绑定锁内执行 CAS 更新（同账号同区服重登不删行重建、撤销旧缓存/会话、有条件移交社区授权），写后回读确认，随即触发 `schedule_login_prefetch` 自动采集并在等待登录通知就绪（≤60s）后自动回发名片；Core 后台禁用通用数据库写接口，仅开放带 Core 管理员鉴权的 `POST /api/aliceuid/bindings/{record_id}/unbind`。
- **访问控制**：群/用户四名单（白名单非空先限范围再判黑名单，同 ID 冲突拒绝保存）；`AliceUID_MasterQQ` 仅标记，管理操作须 Core 认证 `ev.user_pm == 0`；全部出图/文件/写操作发送前复核绑定 revision、epoch 与权限。

---

## 4. 渲染引擎、Bento 视觉体系与卡片契约

### 4.1 渲染管线与浏览器职责
- **默认原生引擎（`pytakumi`）**：名片、横/纵版角色练度、主力卡片、全量图鉴、资源与血量、联盟出刀、活动日历、会战攻略、通用攻略、帮助与别名卡均默认通过 `nikke_render/render.py` 走 GsCore 原生渲染接口（外置渲染开启时优先 `POST JSON {"html": "..."}`，失败回退原生）。
- **Playwright 仅限两处**：网页账密登录（`nikke_login`）与 DILDORO 个人突袭（`nikke_solo`）。统一由 `nikke_browser/runtime.py` 复用宿主 Playwright 并在缺少配套 Chromium 时通过 `sys.executable -m playwright install chromium` 自动补装（不依赖 AI、不改宿主 Python 包；公共安装上限 `900s`、单次等待 `120s`、失败冷却 `300s`）。

### 4.2 Bento 战术玻璃 v2/v3 CSS 约束
全量卡片共享 `templates/alice_v2_tokens.css`（暗版琥珀金 `#F6C15C` / 亮版珊瑚红 `#D43D51`）：
- 严禁关键视觉依赖 `::before`/`::after`、`backdrop-filter`、`transform` 偏移或在 flex 容器内放置绝对定位 1px 装饰子元素（头像外框与高光均使用真实 `.avatar-glass-edge` / `.glass-highlight` DOM）。
- 全部状态/角标小胶囊使用 `.ui-pill` 固定高度与 `AaZongYiYuan-2.ttf` 光学居中规则。
- 图标与立绘阴影由 `nikke_render/icon_effects.py` 独立从 Alpha 派生阴影 PNG 叠放，源图前景不二次模糊或预合成。
- 任何可见排版、字段或主题变更必须同步递增对应 `render_version` / `STYLE_VERSION` / `CACHE_VERSION`。

### 4.3 全局主题随机策略（`AliceUID_ThemeRandomStrategy`）
- 仅在主题处于随机模式时生效，固定亮/暗设置不受影响：
  - `纯随机`（默认）：兼容旧版随机亮暗。
  - `交替`：任务内亮/暗轮替发出，双槽缓存互不串色。
  - `昼夜`：按北京时间 `06:00~17:59` 亮色、`18:00~05:59` 暗色。
- 完整兼容角色练度卡的 `关闭随机` / `横版随机` / `纵版随机` / `全部随机`（宽/窄版式与明暗策略协同）及个人突袭独立开关（`AliceUID_SoloCardTheme`）。

### 4.4 生产卡片规格与缓存指纹汇总

| 卡片类型 | 尺寸 / DPI | 核心布局与渲染要点 | 关键缓存版本 / 周期 |
|---|---|---|---|
| **角色练度（横版）** | `1280×820` · `144 DPI` | SIFT+RANSAC 头部锚定（`portrait-anchor-sift-3`，单进程锁、12s 超时、结果落盘复用）+ `WIDE_ART_BASE_SCALE=0.825` + `WideArtScaleOffset(-100%~+100%)`；顶栏自适应别名胶囊、3 行词条占位、全画布渐变背景 | `alice-v1303-bento-2`（随数据/指纹复用） |
| **角色练度（纵版）** | `570×1048` · `144 DPI` | MI 半身像（不走 SIFT）、含循环室与 `GlassStrength` 毛玻璃调节 | 同上 |
| **指挥官名片** | `1280×740` · `144 DPI` | Bento v3（保留 `profile_classic.html`）：档案+5 KPI 融合、四大企业图标、前哨 `1宽+2窄`、主推 `slot=3` 透底等级/战力胶囊 | `alice-profile-v1304-bento-3`（7 天 PNG 缓存） |
| **主力卡片 / 全量图鉴** | 宽 `1400` · 强制 `96 DPI` | `nk卡片`（任一技能 ≥ 7，≤49 人 7 列 / ≤96 人 8 列 / >96 人 10 列）；`nk图鉴`（10 列 + 灰阶未解锁）；`display_assets` 本地优先（前台 2 worker/12s 预算，后台每 2s 补图，临时缺图 60s 重查）；不截断末行 | `alice-icons-v1300-main-codex`（双模式独立，发送后滑动 7 天） |
| **资源 / BOSS 血量** | `730px` / `800px` · `144 DPI` | 8 色顶部条纹 + 保管箱 90% 刻度线与充能纹；`prepare_image()` 成功出图后记录 300s 固定窗口 | `alice-v1218-bento-status-1`（300s 不滑动） |
| **活动日历** | 双主题 · `pytakumi` | Bento 品牌顶栏（`84×84px` 头像、`28/14/14px` 同心圆角、`NIKKE · AliceUID`）、`3:1` Banner、模拟室双倒计时、竞技场双赛程表 | `v1307-hero`（亮/暗双槽，1800s 缓存） |
| **通用攻略长图** | `pytakumi` | 顶栏 `112×112px` 头像（`36/18/18px` 同心圆角）+ 右下角 `96×96px` 原帖二维码；60s 渲染硬超时降级纯文字 | `v1307-header-concentric`（30 天媒体 TTL） |
| **帮助卡片** | 双列/通栏 · `pytakumi` | 仅 `public`/`owner` 双槽（无个人身份，`ev.user_pm == 0` 才为 Bot 主），独立随机主题 | `CACHE_VERSION = '1.4.0'`（30 天） |
| **联盟出刀** | `1000px` · `pytakumi` | 左 `438px` 身份时间 + 右自适应赛季状态，按出刀阶段配色，缺失突破参考同成员本地 `PanelCache` | 7 天 PNG 缓存（仍先校验 180s/结算数据） |

---

## 5. 核心业务子系统契约

### 5.1 Blablalink 通用攻略系统（`nikke_guide`）
- **索引生命周期与旧库兼容**：持久化于 `guide_index.sqlite3` + 30 天长图/单图缓存。启动自动检查 `INDEX_RULES_VERSION = 'v1308-exact-alias'`，规则升级时执行零网络 `reindex_local()`（100% 兼容旧库无需删库，保留已渲染长图）；每日北京时间 `04:15` / `14:15` 增量扫新（遇已知旧帖即停）；`nk攻略查询` 同步执行轻量新帖检查；帖子临时失效记录 `missing_since`，仅连续超 **24 小时** 仍失效才移出索引；Bot 主支持 `nk攻略重索引 [清空]`。
- **精准匹配、别名联动与原皮/异格区分**：结合 `AliasStore`（`get_alias_store()`）先将别名映射为官方名称，再执行跨简繁、忽略全/半角冒号（`：`/`:`）、空格、连字符及双词词序的精确检索。带冒号副标题的新异格在入库与查询阶段均与原皮严格隔离；精确目标未收录但存在同系异格/相关攻略时，返回 `'suggest'` 提示并写入 60 秒 `nk查询1~N` 会话。
- **四档自适应并发配图（`GuideImagePacer`）与 GIF 处理**：
  - 全插件共享并发池与连接复用，四档阶梯 `5 → 3 → 2 → 1`（默认 5 并发）；遇 `HTTP 429/403/503` 强风控立即降至 2（连续触发降至 1 串行加间隔），冷静 **10 分钟** 且连续 **8 张图** 零异常逐级恢复。
  - 区分「连续 `10s` 无字节流入假死」与「正常下载中」（首次单图 `25s` / 重试 `20s` / 整批 `60s`）；瞬时错误自动重试 1 次，403/404/超限立即跳过。
  - GIF 流式探测在 `asyncio.to_thread` 中解出第 1 帧并补齐 `;` 结束符后中止 HTTP 传输（`8MB` 上限），避免截断丢图。
  - 单图独立落盘缓存：若当次存在失败配图，标记 `complete: false`，过 `60s` 冷却后下次查询仅增量重下缺失配图并重绘完整长图。外语原帖经匿名 `GetPost` 获取官方中文译文；合并转发启用 `preserve_order=True` 严格按序发送（来源说明 → 完整长图 → 纯文字正文）。

### 5.2 官网活动日历（`nikke_calendar`）与会战攻略（`nikke_raid_guide`）
- **活动日历**：匿名调用 `GetCalendarDetail`，经 `nikke_calendar/assets.py` 解析官方 CDN 混淆素材（14 天缓存，优先复用本地角色头像），默认经 `AliceUID_CalendarForward` 合并转发（标题 `[AliceUID·活动日历]`）。
- **会战攻略**：匿名读取固定作者公开帖，全阶段严格按官方赛季起止校验（战斗期 3 天缓存 / 休赛期长期保留，新赛季清除旧期；未发布或缺组队图 5 分钟冷却，不拿上期冒充本期）；`pytakumi` 渲染正文长图，严格三段转发（标题与作者来源 → `組隊示例` 首图 → 完整长图）。

### 5.3 查询风控、面板缓存、别名与全量导出
- **串行风控节流**：`AliceUID_PanelRiskStrategy` 提供三档串行——高速（`1s`）/ 中速（推荐默认 `2s`）/ 缓速（`5s`），旧极速自动归一化为中速。`AccountReads.transaction()` 保持同账号串行、全局最多 2 个在途槽、首批/瞬态重试 `5s` 门槛、前台优先让位；全量详情 `DETAIL_BATCH_SIZE=30`（公开导出 `20`）。资源查询固定 `basic`+`daily` 双接口 `1s` 节拍，最多 3 轮只补失败接口（1302127/5xx/传输超时重试，鉴权/403/429 不重试）。
- **面板缓存与时间戳仲裁**：`PanelCache` 容器 `schema=1`（`data_revision=4`, `attribute_schema=3`）。轻量 `profile.json`（`nk刷新信息` 仅 5 接口）与全量 `snapshot.json` 独立维护 `profile_checked_at` / `roster_checked_at` / `saved_at`，晚到的旧任务不能覆盖更新的轻量资料；单角色查询缺缓存先拉单体详情出图，再触发无通知的静默全量同步（`complete=False` + `full_refresh_pending`）。
- **内置别名与黑名单**：随包提供 `nikke_character/AliceUID_nk_alias.md`（32 角色、48 别名），启动与用户 `character_aliases.json` 合并（用户优先）；`nk注销别名` 写入 `character_aliases_disabled.json` 屏蔽指定别名（含内置默认，重启不复活，重新新增可恢复）；支持 `nk别名导出`。
- **练度导出（`nikke_export`）**：支持本人离线缓存或公开链接（`uid` 优先 `openid`，无标识按本人）；公开目标 `show_nikke_info` 接受 `1/2/3`，`show_outpost_info` 仅 `1301002` 拒绝时降级部分导出（不补 0）。Excel 由 `XlsxWriter` 生成（无宏、冻结前 5 行 `114pt`、4 维联动筛选 + 编号/战力排序，上限 `500` 人 / `12MB`、最多 2 并发线程）；JSON 采用 `schema_version=3`（原始属性 + 独立 `simulation` + 去重元数据）。

### 5.4 联盟会战（`nikke_union`）与收菜提醒（`nikke_harvest`）
- **联盟会战**：区分官方区间与两日出刀阶段（`combat_end_ts = min(start_ts+48h, end_ts+1)`）；同联盟共享进行中 `180s` 快照（按 `_cached_at` 判定不顺延），出刀截止后共享至 `end_ts`，正式结算后缓存 5 天并沉淀轻量历史（保留最近两期完整快照）。按排名查刀仅在本人联盟快照内定位（不访问他人私有接口），缺失的 `grade/core` 仅按严格身份匹配参考同成员本地 `PanelCache`。
- **收菜提醒**：`harvest.sqlite3` 分离账号共享进度与会话订阅，共享 scheduler 每 `30s` 扫描到期账号。通知按 `会话:轮次:normal/bed/full` 独立去重（90% `normal` / 99% `full`，满仓后 `+60s` 复核）；免打扰前 1 小时窗口内执行 `nk收菜免打扰` 立即补检睡前提醒（含 `WAIT_MAX`）；`23:00~24:00` 连续两晚原始 `100%` 触发 `AUTO_STOPPED`；手动新鲜查询通过 `on_snapshot` 回调同步刷新预测。

### 5.5 兑换码（`nikke_cdk`）与社区任务（`nikke_community`）
- **兑换码**：`cdk.sqlite3` 维护 `official_code_times`、`code_details`、`inventory_codes`、`member_codes`、`receipts`、`redemption_audits` 与 `auto_public_*`。官方/GW/成员三源按 ASCII 大小写归一与跨源去重；官方 Unix 秒精确退库（`expires_at+300`），GW 退库 `+86400`；仅 `1302003/1302015/1302009` 触发共享即时停用；`00/08/16` 点刷新与成员贡献（含 48h 近期成功/直接 `1302016` 补录）触发新码派发，新绑定仅核对本人；单码重兑命中本地回执直接返回爱丽丝已兑时间提醒。
- **社区任务**：`community.sqlite3` 以北京时间 `08:00` 为周期边界（跨界中止并写入 `carry_boundary_guard`）。每日定时执行（默认 `08:33`）+ `60s` 重试检查（只读/未发出的连接失败最多 3 轮，延迟 `120/600s`；写操作结果不明保留预占禁止重投）。随机节拍默认单请求 `5-15s`、换号 `10-120s`、日上限 `30` 次；`signin_confirmations` 独立于 `last_day`；异常名单按报错原因归类每批 10 人默认合并转发（`AliceUID_SignNoticeForward`），支持全群批量设置与单群独立覆盖。

### 5.6 DILDORO 个人突袭（`nikke_solo`）与官网隐私（`nikke_privacy`）
- **队列与容错**：`BrowserQueue` 按完整计算 FIFO 排队（缓存快路径不占队），3 轮总预算 + 连续 `20s` 无响应静默重试（仅有效响应与 `/api/fetch|sim|sim-heavy/events` SSE 续命；遵守网站 CSP 无 `unsafe-eval`，改用宿主 `wait_until` 轮询；`add_locator_handler` 关闭延迟公告）。
- **赛季、推荐配置与降级**：五属性独立缓存 5 天，`site-v1.json` 共享公开赛季状态（活跃 1h / 非活跃 6h）；自动解析并套用同属性最新公开推荐配置（无入口时回退默认模拟）；中文翻译异常自动切换韩语原文（`lang=ko`）重跑；图片/字体最多等 `4s`，异常时占位并用 CDP 截取校验区域。
- **官网隐私自动恢复**：若本人 `show_nikke_info` 为 `0/2/3`，轮到同步时先持久化原状态至 `MAIN_PATH/privacy_restore/<hash>.json`，临时公开并在发送截图后由后台每 `60s` 巡检恢复原设置。

### 5.7 合并转发、双文风、脱敏日志与 AI
- **合并转发（`nikke_message`）**：默认走标准 `MessageSegment.node`（无外层 `@`），按「普通文本 / 登录指引 / 含图长卡」三条通道独立熔断。NapCat 启用 `wait_recall=True`，`receipt.py` 通过 `ContextVar` 局部覆盖等待超时（默认 `30s`，可配 `5~300s`，不改 Core 全局常量），未确认普通回退 1 次并暂停该通道 `60s`。**移除被动压缩**：后台关闭 `AliceUID_ForwardReencode` 时原样发送；开启后合规 JPEG 直通，非透明非 JPG 按 `ForwardJpegQuality`（默认 95）单次编码（输入 `32MiB/64MP`、输出 `8MiB` 保护上限）。
- **双文风与脱敏日志**：`nikke_message/persona.py` 统一管理 `爱丽丝风格` / `默认说明文`；`nikke_logs` 内存有界（10000 条 / 2MB / 24h），全局按 `(bot_id, group_id, user_id, msg_id)` 去重记录匿名命令（剥离姓名/QQ，仅标 `[bot主]`/`[普通成员]`），保留相对接口路径并脱敏 Cookie/Token/密码/登录令牌。
- **AI 只读查询（`nikke_ai`）**：`AliceUID_AIQueryEnabled` 默认关闭，仅向 Core AI 注册帮助、本人资料、角色练度与别名四项只读工具，仅输出脱敏摘要且每次复核 Core 与四名单权限。

---

## 6. 存储目录、调度任务与配置索引

### 6.1 运行期数据目录（`get_res_path() / "AliceUID"`）
```text
Core资源根/AliceUID/
├─ config.json / group_policy.json     # 当前配置与旧策略兼容
├─ secret.key                          # Cookie 加密密钥（须与 Core AliceBind 数据库同步备份）
├─ character_aliases.json              # 用户自定义角色别名
├─ character_aliases_disabled.json     # 已注销别名黑名单（含内置默认屏蔽）
├─ uid_bindings.sqlite3                # 本地 UID / 分享标识登记
├─ community.sqlite3                   # 社区授权、预算、签到确认与群通知状态
├─ harvest.sqlite3                     # 收菜共享预测、订阅与夜间采样账本
├─ cdk.sqlite3                         # 兑换码来源、官方有效期、成员池与个人回执
├─ guide_index.sqlite3                 # Blablalink 通用攻略索引与 24h 失效追踪
├─ privacy_restore/                    # 官网隐私待恢复记录（不含 Cookie）
├─ static/                             # 公开静态表与元数据
├─ resource/                           # 公开美术缓存与来源侧车 JSON
├─ database/                           # 公共图库 manifest、startup_catalog、calendar_update
└─ cache/                              # auth_invalid / panels / roster / resource_images /
                                       # union_history / calendar / guide / raid_guide / solo / help / forward_outbox
```

### 6.2 Core 共享调度器任务汇总

| 调度任务 | 触发策略（Asia/Shanghai） | 说明 |
|---|---|---|
| `aliceuid-database-startup-catalog` | 启动立即检查（60s 间隔直至就绪） | 匿名刷新 `nikke_list_zh-TW_v2.json`，成功后持久落盘 |
| `aliceuid-database-calendar` | 60s 巡检（闲时 6h / 招募期 1h） | 依官网招募日历静默补齐新角色资料与 1h 稳定复查 |
| `aliceuid-database-weekly` | 每周五 `02:33` | 增量检查公开静态表与基础图库（受批次/流量/磁盘预算控制） |
| `aliceuid-guide-sync` | 启动初始化 + 每日 `04:15` / `14:15` | 规则升级本地重算 + 增量扫描新攻略 + 24h 死链清理 |
| `aliceuid-community` + 重试巡检 | 每日 `AliceUID_CommunitySignTime`（默认 `08:33`）+ 60s | 已授权账号自动签到/浏览/点赞与失败重试/群汇总 |
| `aliceuid-harvest` | 30s 本地扫描 | 仅到期且已订阅账号请求上游并触发 90%/99%/睡前提醒 |
| CDK 库存定时刷新 | 每日 `00:00` / `08:00` / `16:00` | 同步官方与 GameWith 码池并向开启自动兑换者派发新码 |
| 官网隐私恢复巡检 | 60s 本地扫描 | 恢复因个人突袭临时公开的官网妮姬隐私设置 |

### 6.3 后台配置完整索引（`config_default.py` 稳定顺序）

| 分组 | 配置键 | 类型 | 默认值 | 说明 |
|---|---|---|---|---|
| **查询与缓存** | `AliceUID_PanelRiskStrategy` | Str | `中速（推荐）` | 高速 1s / 中速 2s / 缓速 5s（均串行） |
| | `AliceUID_CacheTTL` | Int | `600` | 兼容旧键（持久面板快照不依此过期） |
| | `AliceUID_ResourceCacheSeconds` | Int | `300` | 资源成功出图固定复用窗口（秒） |
| | `AliceUID_UnionCacheSeconds` | Int | `180` | 进行中联盟快照共享秒数 |
| **登录与浏览器** | `AliceUID_LoginUrl` | Str | `""` | 登录页反代 / 外网地址（secret） |
| | `AliceUID_LoginRequireHTTPS` | Bool | `False` | 强制登录页/API 具备真实 HTTPS scheme |
| | `AliceUID_LoginMode` | Str | `browser` | `browser`（账密+Cookie）/ `cookie`（仅导入） |
| | `AliceUID_LoginTTL` | Int | `600` | 一次性登录链接有效期（秒） |
| | `AliceUID_LoginQRCode` | Bool | `False` | 登录链接附带二维码图片 |
| | `AliceUID_LoginForward` | Bool | `True` | 登录链接使用合并转发 |
| | `AliceUID_DefaultArea` | Int | `81` | 旧版兼容键（新登录须显式选服） |
| | `AliceUID_BrowserAutoInstall` | Bool | `True` | 自动补装 Playwright 配套 Chromium |
| | `AliceUID_BrowserChannel` | Str | `auto` | `auto` / `chromium` / `msedge` |
| | `AliceUID_Headless` | Bool | `True` | 无头浏览器运行 |
| | `AliceUID_Proxy` | Str | `""` | 登录浏览器代理（secret） |
| **权限名单** | `AliceUID_MasterQQ` | ListStr | `[]` | 主人 QQ 标记名单（不提升 Core pm） |
| | `AliceUID_GroupWhitelist` / `Blacklist` | ListStr | `[]` | 群黑白名单（冲突拒绝保存） |
| | `AliceUID_UserWhitelist` / `Blacklist` | ListStr | `[]` | 用户黑白名单（Bot 主亦受限） |
| **卡片外观** | `AliceUID_CardTheme` | Str | `random` | 全局卡片主题（`random` / `dark` / `light`） |
| | `AliceUID_ThemeRandomStrategy` | Str | `纯随机` | `纯随机` / `交替` / `昼夜`（06–18 亮） |
| | `AliceUID_CharacterCardStyle` | Str | `横版亮色` | 横/纵版 × 亮/暗（兼容旧英文值迁移） |
| | `AliceUID_CharacterRandomTheme` | Str | `关闭随机` | `关闭随机` / `横版随机` / `纵版随机` / `全部随机` |
| | `AliceUID_WideArtScaleOffset` | Str | `"0"` | 横版大立绘缩放微调（`-100%`～`+100%`） |
| | `AliceUID_NoticeStyle` | Str | `爱丽丝风格` | `爱丽丝风格` / `默认说明文` |
| | `AliceUID_SoloCardTheme` | Str | `dark` | 个人突袭独立主题（`dark` / `light` / `random`） |
| | `AliceUID_CardLanguage` | Str | `zh-CN` | 卡片文字语言（`zh-CN` / `zh-TW`） |
| | `AliceUID_CardFont` | Str | `AaZongYiYuan-2.ttf` | 读取 `formts/` 目录字体 |
| | `AliceUID_GlassStrength` | Int | `20` | 仅作用于竖版/窄版毛玻璃卡片（0–100） |
| | `AliceUID_RenderDpi` | Int | `144` | 渲染 DPI（96=1x / 144=1.5x / 192=2x） |
| **消息转发** | `AliceUID_HelpForward` / `RosterForward` / `UnionForward` / `RaidGuideForward` / `GuideForward` / `CalendarForward` / `AccountListForward` / `SignNoticeForward` / `CDKForward` | Bool | `True` | 各业务独立合并转发开关 |
| | `AliceUID_CDKResultForward` | Bool | `False` | 超 600 字/12 行兑换结果合并转发 |
| | `AliceUID_ForwardReceiptSeconds` | Int | `30` | NapCat 转发回执等待秒数（5–300） |
| | `AliceUID_ForwardReencode` | Bool | `False` | 转发非透明非 JPG 图转 JPG（默认原图） |
| | `AliceUID_ForwardJpegQuality` | Int | `95` | 新编码转发 JPG 质量（0–100） |
| **社区与兑换码** | `AliceUID_CommunityPaused` | Bool | `False` | 紧急暂停全部社区任务 |
| | `AliceUID_CommunitySignTime` | Str | `08:33` | 每日签到时间（北京时间 `HH:MM`，保存即重排） |
| | `AliceUID_CommunityRequestRange` | Str | `5-15` | 社区单次请求随机间隔秒数（重启生效） |
| | `AliceUID_CommunityAccountRange` | Str | `10-120` | 社区换号随机等待秒数（重启生效） |
| | `AliceUID_CommunityDailyRequests` | Int | `30` | 每账号每 08:00 周期请求上限 |
| | `AliceUID_SignGroupNotify` | Bool | `True` | 签到群通知全群批量默认值 |
| | `AliceUID_EnableWriteOps` | Bool | `False` | 允许本人 CDK 兑换总权限开关 |
| | `AliceUID_AutoCDKEnabled` | Bool | `True` | 自动兑换码系统总开关 |
| **公开数据库** | `DatabaseWeeklyUpdate` / `DatabaseCalendarUpdate` / `DatabaseIncludeSkins` | Bool | `True` | 周检、日历驱动更新与皮肤变体开关 |
| | `DatabaseMaxTasks` / `MaxDownloadMB` / `MaxDiskMB` | Int | `40` / `128` / `2048` | 单批任务、下载流量与总图库存储预算 |
| | `DatabaseRequestInterval` / `FailureCooldown` / `MaxRunMinutes` | Int | `2` / `3600` / `30` | 请求间隔（下限 2s）、冷却与单次时长上限 |
| **高级渲染与 AI** | `AliceUID_RemoteRenderEnable` / `Url` / `Token` / `RenderTimeout` | Mixed | `False` / `60s` | 外置渲染服务配置（失败回退原生） |
| | `AliceUID_AIQueryEnabled` | Bool | `False` | 允许 Core AI 只读查询（须重启生效） |

---

## 7. 测试、版本同步与发布门禁

### 7.1 离线测试与开发约定
测试位于版本目录 `tests_alice/`，全程使用 MockTransport、离线夹具与隔离 SQLite（严禁在自动化回归中执行真实账号登录、社区写操作或发群）。

```powershell
# 使用工作区共享 Python 解释器运行核心回归
.\DevelopmentEnvironment\python\python.exe -I -B -X utf8 -m pytest `
  AliceUID_1.4.0\tests_alice\test_v1309_image_pacer.py `
  AliceUID_1.4.0\tests_alice\test_v1308_guide_matching.py `
  AliceUID_1.4.0\tests_alice\test_v1307_release.py `
  AliceUID_1.4.0\tests_alice\test_v1306_fix1.py `
  AliceUID_1.4.0\tests_alice\test_v1306_calendar_and_guide.py `
  AliceUID_1.4.0\tests_alice\test_v1305_guide.py `
  AliceUID_1.4.0\tests_alice\test_v1121_raid_guide.py `
  AliceUID_1.4.0\tests_alice\test_v1122_raid_guide.py `
  AliceUID_1.4.0\tests_alice\test_release_pipeline.py
```

### 7.2 版本同步清单
每次发版必须核对并统一更新：
1. `AliceUID/AliceUID/version.py`（`VERSION`、`BUILD`）
2. `AliceUID/pyproject.toml`（`version`）
3. `AliceUID/README.md`（徽章与当前版本）
4. `AliceUID/CHANGELOG.md`（顶部版本号与首节）
5. `AliceUID/AliceUID/templates/calendar.html`（`app_version` 回退值）
6. `AliceUID/AliceUID/nikke_help/cache.py`（`CACHE_VERSION`）

### 7.3 双产物封包与校验
1. **GitHub Release 完整包**：执行 `tools_alice/build_release.py --plugin-only`，强制通过 **隐私标识符零泄露扫描**、**清洁目录解包与逐文件 SHA256 核验**、**全 Jinja2 模板编译检查** 及 **旧模板覆盖验证**，生成 `AliceUID_plugin_v<ver>_<date>.zip` 与 manifest 放入根 `dist/`（根 `dist/` 仅保留最新两代，更旧包移入本地 `回收站/`）。
2. **纯源码归档**：剔除图片、字体与可再生缓存后通过 7-Zip 打包至 `HistoryVersion/AliceUID_source_v<ver>_<date>.7z` 并执行 `7z t` 完整性校验。
3. 发布包构建完成不代表已部署，禁止自动操作目标 NAS/Docker 或执行真实社区/群聊发送。
