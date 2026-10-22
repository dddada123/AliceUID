<p align="center">
  <a href="https://github.com/dddada123/AliceUID">
    <img src="https://raw.githubusercontent.com/dddada123/AliceUID/main/ICON.png" width="256" alt="AliceUID">
  </a>
</p>

<h1 align="center">AliceUID</h1>

<p align="center">
  <a href="https://github.com/Genshin-bots/gsuid_core"><img src="https://img.shields.io/badge/Framework-GsCore-8A2BE2?style=flat-square" alt="Framework: GsCore"></a>
  <a href="https://github.com/dddada123/AliceUID/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License: MIT"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/Version-1.0.17-ff69b4?style=flat-square" alt="Version: 1.0.17"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-%E2%89%A53.10-3776AB?style=flat-square&amp;logo=python&amp;logoColor=white" alt="Python: ≥3.10"></a>
  <a href="https://github.com/dddada123/AliceUID/stargazers"><img src="https://img.shields.io/github/stars/dddada123/AliceUID?style=flat-square" alt="GitHub Stars"></a>
</p>

适用于 GsCore 的《胜利女神：NIKKE》插件，提供会战血量与联盟出刀查询、资源与满仓时间预估、社区签到，以及 **DILDORO** 个人突袭编队推荐，同时支持本人账号绑定、个人资料、角色练度与皮肤图鉴查询。当前版本 **1.0.17**，默认使用 `nk` 前缀，前缀由Core插件管理统一配置。

[亮点功能](#亮点功能) · [功能说明](#功能说明) · [效果预览](#效果预览) · [版本记录](CHANGELOG.md) · [开发文档与接口映射](DEVELOPMENT.md) · [问题反馈](https://github.com/dddada123/AliceUID/issues)

<p align="center">
  <img src="https://count.getloli.com/@AliceUID?theme=nixietube-1&amp;padding=7&amp;offset=0&amp;align=top&amp;scale=1&amp;pixelated=1&amp;darkmode=auto" alt="AliceUID 访问计数">
</p>

## 亮点功能

### 本人练度全量导出

`nk练度全量导出` 将本人全部妮姬练度导出为 Excel，双角色并排展示，支持爆裂阶段、定位、企业和角色属性联合筛选。属性下拉位于H5，可选燃烧、水冷、铁甲、电击、风压等。包含T10装备词条与同类汇总，高阶数字标蓝，15阶黑底亮蓝；词条数据行采用淡灰／白交替底色。总览保留5行紧凑表头，I2说明、I3导出人数、I4匹配人数。

导出使用本地缓存，注明账号与更新时间；需要最新数据时先发送 `nk刷新面板`。

### ⚔️ 会战血量、联盟出刀总览与个人出刀详情

`nk会战血量` 查看BOSS进度，`nk出刀` 查看联盟伤害、击杀排行与未完成名单。支持指定会战日期，并用 `nk出刀详情` 查看本人队伍和战斗记录。

### 📦 资源查询与满仓时间预估

`nk资源查询` 展示八类资源、保管箱容量，以及预计达到90%和满仓的北京时间，方便安排上线收菜。

### ⏰ 本人收菜提醒

在群聊或私聊发送 `nk开启收菜提醒`，接收容量与睡前收菜提醒；用 `nk关闭收菜提醒` 关闭。各会话独立设置，开启时发送一次资源卡，后续只发文字。

默认北京时间00:00～08:00免打扰，可自行调整，仅影响收菜提醒。

### 🗓️ 社区签到

`nk签到` 完成本人社区签到，也可主动授权自动签到、浏览和点赞。支持执行状态查询与群内汇总通知，自动任务默认关闭。

### 🧮 **DILDORO** 个人突袭编队推荐（实验性）

`nk个人突袭推荐` 将本人养成数据导入 **DILDORO**，生成编队推荐与模拟伤害卡片。结果缓存5天，练度变化后用 `nk个人突袭推荐刷新` 重新计算。

需公开blablalink个人档案与妮姬列表，Cookie不会传给DILDORO；推荐结果仅供模拟参考。

## 功能说明

除上述亮点外，AliceUID还提供账号绑定、个人资料与角色养成查询、通用帮助、可选AI查询和消息转发等功能。

### 🔐 账号绑定与区服支持

支持本人账号登录、查看绑定、重新登录和解绑；支持日服、北美服、韩服、国际服、东南亚服，登录时需明确选服。港澳台网页登录暂未支持。具体步骤见[快速开始](#快速开始)。

### 🎨 个人名片、角色练度与统一刷新

`nk信息` 展示指挥官资料、战役爬塔与主页队伍；角色面板展示本人的装备、技能、词条、魔方、收藏品与好感。完整图鉴以十列头像展示已持有角色和皮肤。卡片支持亮色、暗色、随机主题，以及自定义字体和毛玻璃强度。

登录后自动缓存本人资料、全部角色练度与皮肤，普通查询优先复用持久数据。养成变化后，用 `nk刷新信息` / `nk刷新面板` 全量刷新并获取最新信息图，或用 `nk刷新爱丽丝面板` 只更新指定角色。账号数据不自动到期；刷新失败保留旧完整数据，解绑清除、重新登录重建。数据已刷新但出图失败时，可发送 `nk信息` 重试出图。

### 🧭 通用帮助与长效缓存

`nk帮助` 提供普通用户、Bot主两类通用指南，不展示昵称、UID或区服等个人信息。两张图分别缓存30天，重启可复用，到期首次访问随机主题重建；帮助内容或相关配置变化会提前重建。需要复制命令时使用 `nk帮助 文字`，图片渲染失败也会回退文字。

### 🤖 AI自然语言查询

开启插件「允许AI调用只读查询」及Core AI并完整重启后，可用自然语言查询本人资料、角色练度、角色别名和插件帮助，例如“看看我的妮姬资料”“查爱丽丝练度”“黑莲有哪些别名”。复用原有查询与缓存，仍受Core权限、群聊范围以及AliceUID四名单约束，不接受替他人查询。

后台「允许AI调用只读查询」默认关闭，不注册AI工具；按需开启并重启后生效。关闭后立即停止AI查询，普通指令照常使用。AI帮助返回文字，资料类返回必要数据摘要和图片资源，由Core AI决定最终回复。登录、解绑、社区操作、强制刷新及DILDORO计算未开放AI调用。

### 📨 转发与可调等待

登录链接、帮助、图鉴和出刀各有独立转发开关，默认开启。完整图片配文字标题展示，支持自定义消息回执等待；未确认时普通回退一次，短暂暂停后恢复尝试。配置和兼容说明见[转发设置](#转发设置)。

命令速查见[常用命令](#常用命令)，六张示例图见[效果预览](#效果预览)。

## 安装与升级

插件依赖 GsCore 的命令、数据库、WebUI、调度器和原生渲染服务，不能作为独立 Bot 运行。项目声明 Python ≥3.10，具体依赖见 [requirements.txt](requirements.txt) 和 [pyproject.toml](pyproject.toml)。

1. 首次安装或升级前备份原插件及其运行数据。解压安装包，把整个外壳放入 `plugins/AliceUID/`。
2. 保留以下嵌套结构，不要只拷内层包，也不要将开发工作区的版本目录 当成插件目录。
3. 在运行 GsCore 的 Python 环境安装插件依赖。使用网页登录、官网日历或DILDORO个人突袭推荐时，准备 Playwright Chromium。
4. 完整重启 GsCore，在 WebUI 的 AliceUID 配置中检查登录地址、访问名单和主题，再发送 `nk帮助`。

```text
plugins/
└─ AliceUID/
   ├─ __init__.py
   ├─ __nest__.py
   ├─ AliceUID/             # 内层 Python 包、模板与静态表
   ├─ assets/              # 登录与资源图标
   ├─ card_bg/             # 卡片背景
   ├─ formts/              # 字体，目录名称保留该拼写
   ├─ README.md
   ├─ CHANGELOG.md
   └─ DEVELOPMENT.md
```

依赖安装示例（使用 GsCore 实际使用的 Python）：

```bash
python -m pip install -r plugins/AliceUID/requirements.txt
python -m playwright install chromium
```

常规卡片使用Core的 `render_html_to_bytes` 原生渲染。DILDORO需要执行网站JavaScript、导入本人资料、操作推荐界面并截取真实结果；pytakumi不能替代浏览器自动化，因此保留Playwright。官网日历截图与网页登录同样保留浏览器。

从其他 AliceUID 版本升级，继续使用原 `data/AliceUID` 和 `AliceBind`，无须因版本更新重新绑定。不要同时启用多份 AliceUID。

从旧 NikkeUID 首次迁移时，将旧插件移出扫描目录留作备份；只复用公开 `static/` 和 `resource/`，用户在 AliceUID 中重新登录。旧账号、Cookie、密钥与私人缓存不自动迁移。

## 快速开始

```text
nk登陆日服
nk我的账号
nk信息
nk爱丽丝练度
nk卡片
nk资源查询
```

`登录` / `登陆` 均可使用；不带区服会给出选服提示。打开本人命令返回的链接完成验证，Cookie失效用 `nk重新登录` 更新同账号同区服凭据；换号或换服先 `nk解绑`。已知失效凭据不会继续读取旧图，网络异常、403和429分别提示。

## 常用命令

| 命令 | 用途 |
|---|---|
| `nk帮助` / `nk帮助 文字` | 普通用户/Bot主两类通用指南，图片缓存30天；文字可复制 |
| `nk登录日服` | 五区登录；日服可替换为国际服/北美服/韩服/东南亚服 |
| `nk重新登录` | 更新原账号同区服 Cookie，失败保留原绑定 |
| `nk我的账号` / `nk解绑` | 查看或解除登录绑定 |
| `nk信息` / `nk名片` | 本人个人资料与展示队伍 |
| `nk刷新信息` / `nk刷新面板` | 刷新并缓存本人资料、全部角色练度及皮肤，完成后发送最新信息图 |
| `nk爱丽丝练度` / `nk爱丽丝面板` | 查询指定角色练度 |
| `nk刷新爱丽丝面板` | 更新指定角色练度与皮肤数据，并渲染角色卡片 |
| `nk卡片` | 完整已持有角色图鉴 |
| `nk出刀` | 联盟出刀速查与排行 |
| `nk出刀 Day1` / `nk出刀速查 Day2` | 选择会战阶段 |
| `nk出刀详情` / `nk出刀缺刀` / `nk出刀尾刀` | 本人队伍、未完成名单、尾刀统计 |
| `nk会战血量 [刷新]` | 联盟阶段及 BOSS 血量 |
| `nk资源查询 [刷新]` | 本人资源与保管箱状态 |
| `nk开启收菜提醒` / `nk关闭收菜提醒` | 当前群聊或私聊的本人收菜提醒开关 |
| `nk收菜提醒状态` / `nk收菜免打扰 00:00-08:00` | 本地状态与当前会话免打扰时段 |
| `nk个人突袭推荐 [亮色/暗色/随机]` | 查看本人编队推荐，优先复用五天缓存 |
| `nk个人突袭推荐刷新 [亮色/暗色/随机]` | 重新导入养成数据并计算推荐 |
| `nk日历` / `nk日历 帮助` | 官网当前默认活动日历及范围说明 |
| `nk黑莲别名查询` | 查询角色本名及已注册别名 |
| `nk绑定UID` / `nk我的UID` / `nk解绑UID` | 单独登记、查看或清理社区/游戏/分享标识 |

方括号表示可选参数，不需要输入方括号。UID登记只保存标识，不代表登录成功或允许查询他人的私人资料。

## 社区任务

| 命令 | 行为 |
|---|---|
| `nk签到` | 立即执行本人本周期签到；已成功不重复请求 |
| `nk开启全量签到` | 为本人开启签到、浏览及点赞，并立即执行一轮 |
| `nk自动社区 状态` | 查看授权、暂停原因和执行状态 |
| `nk自动社区 开启` / `关闭` | 开启签到与浏览，或停止自动任务 |
| `nk自动社区 点赞开启` / `点赞关闭` | 单独调整点赞授权 |

周期以北京时间08:00划分，默认每天08:33执行已授权账号。后台「每日签到时间（北京时间）」支持HH:MM，保存后更新调度；手动签到仍须排队、限频。重新登录后需重新开启自动社区授权。

请求间隔默认随机 **5～15秒**，换号等待默认 **10～120秒**。后台填写如 `5-15`、`10-120`，允许1～3600秒及最多三位小数，同值为固定间隔，重启生效。每账号每周期最多30次请求，签到一次、浏览和点赞各最多5帖；失败暂停，不通过重启或开关重置预算。不自动评论、发帖或兑换金币。

Bot主可用 `nk签到查询 [页码]` 查看本群绑定或近30天使用过插件账号的本周期本地记录。群通知也只覆盖这些已知用户，同账号跨群不重复签到；未确认不冒报成功，缺少有效群消息路由时不发送通知。

| Bot主指令 | 功能 |
|---|---|
| `nk签到群通知 开启/关闭/状态` | 全局开关，默认开启；关闭只停止通知，签到和其他业务照常 |
| `nk签到通知白名单 添加/移除 群号` | 非空时只向白名单群发送；与黑名单重叠时白名单优先 |
| `nk签到通知黑名单 添加/移除 群号` | 白名单为空时排除这些群；名单仅影响签到通知 |
| `nk签到通知白名单 状态` / `nk签到通知黑名单 状态` | 查看通知专用名单 |

通知名单独立于查询权限：全局开关优先，白名单非空时仅通知白名单（重叠群也允许），否则排除黑名单；仍须满足Core与插件原有权限。

## 转发设置

使用现有GsCore适配器的标准转发，无需额外NapCat插件。默认保留完整原图、尺寸与DPI，以“文字标题＋图片”发送，转发内外不附加@；头像昵称沿用适配器设置。登录二维码开关独立，普通发送和回退均保留二维码。

NapCat转发的「转发回执等待秒数」默认 **30秒**，可设 **5～300秒**，保存后下次发送生效；等待不包含图片渲染。未确认时普通回退原内容一次，并暂停本连接转发 **60秒**，到期恢复尝试。超过等待窗口的迟到成功仍可能重复。OneBot私聊、Core不允许转发或不支持回执时使用普通消息。

“转发图片转换JPG”默认关闭；开启后新编码质量默认95，可设0～100，100仍非无损。已有JPG保持原样，透明图保留PNG；超出8MiB插件安全上限或准备失败时普通发送完整原图，不拆页、缩放或降低质量。

转发仍属实验性功能；群内不可见时可关闭对应开关。适配器、可选配套与传输缓存细节见 [integrations/README.md](integrations/README.md)。

## 管理与配置

### 自定义唤醒指令

在GsCore的**插件管理 → AliceUID**中配置框架自带的 `prefix` 与 `disable_force_prefix`，保存后**完整重启Core**。保存配置本身不会重建已经注册的命令。1.0.13在首个SV注册前，通过Core公开接口同步生效前缀到插件对象，帮助文案通过Core的 `get_plugin_available_prefix()` 读取同一份启动状态。插件默认提供 `force_prefix=["nk"]`；前缀前后的空格由Core识别。

- 默认：`nk登录`、`nk 个人突袭推荐`。
- `prefix` 添加 `alice`，保留默认前缀：`nk登录` 和 `alice登录` 均可用，帮助优先显示 `nk`。
- 添加 `alice` 并开启 `disable_force_prefix`：仅自定义前缀可用，帮助和提示同步显示 `alice`。关闭默认前缀前先设置可用的自定义前缀。

从1.0.12升级会保留已有Core前缀及迁移记录，无需重新配置。

从1.0.11及更早版本升级时，首次启动会将已启用的旧插件前缀迁移到Core；若Core已有自定义配置，以Core为准并记录提示。迁移只执行一次，原值保存在 `data/AliceUID/prefix_migration_v112.json`，旧的三项插件前缀设置退出WebUI。本文命令采用默认 `nk`，独占自定义时替换为实际前缀。

Bot主可使用 `nk数据库更新`、`nk数据库更新 状态`、`nk数据库更新 帮助`；公共资料库默认每周五北京时间02:33增量检查，已有合格素材复用。维护只取公开资料，不使用玩家 Cookie。第一次补齐图库较慢，任务会保存队列并报告剩余项。

角色别名可用 `nk红莲暗影新增别名黑莲` 或 `nk红莲暗影注册别名黑莲`。群查询状态可由群管理员查看；群/用户白名单、黑名单和全局别名由Bot主维护。四名单为空时默认允许，白名单非空先限定范围，再排除黑名单。

| WebUI 配置 | 作用 |
|---|---|
| `AliceUID_LoginUrl` | 用户能访问的 Core 登录页面基地址，反向代理需转发 `/nikke/` 路由 |
| `AliceUID_LoginMode` | `browser` 网页密码/邮箱，或 `cookie` 仅私聊导入 |
| `AliceUID_LoginForward` | 登录/重新登录链接转发，默认开启，保留已有值 |
| `AliceUID_HelpForward` | 帮助图片转发，默认开启 |
| `AliceUID_RosterForward` | 完整阵容卡片转发，默认开启 |
| `AliceUID_UnionForward` | 出刀总览/速查/详情/缺刀/尾刀图片转发，默认开启 |
| `AliceUID_ForwardReceiptSeconds` | 转发回执等待秒数，默认30，可设5～300；保存后下次发送生效 |
| `AliceUID_ForwardReencode` | 转发图片转换JPG，默认关闭，优先原图直通 |
| `AliceUID_ForwardJpegQuality` | 新编码转发图片的JPG质量，整数0–100，默认95；100仍非无损 |
| `AliceUID_LoginQRCode` | 同时发送二维码；普通、转发及失败回退均适用，默认关闭 |
| `AliceUID_BrowserChannel` / `AliceUID_Headless` | 登录浏览器通道及无头运行 |
| `AliceUID_CardTheme` | 默认random随机亮暗；命中缓存不重复随机，已有自定义值保留 |
| `AliceUID_CardLanguage` / `AliceUID_CardFont` | 显示语言及 `formts/` 内字体，失败使用兜底字体 |
| `AliceUID_GlassStrength` | 0～100%背景模糊，默认20%；前景文字和人物保持清晰，已有值保留 |
| `AliceUID_UnionCacheSeconds` | 当期会战共享缓存，默认180秒 |
| `AliceUID_RemoteRenderEnable` | 可选外置HTML渲染服务；默认关闭，失败回退Core原生渲染 |
| `AliceUID_CommunitySignTime` | 每日自动签到的北京时间，默认`08:33`，支持`00:00`～`23:59`，保存后更新调度 |
| `AliceUID_SignGroupNotify` | 群签到汇总通知开关，默认开启 |
| `AliceUID_SignNotifyWhitelist` / `AliceUID_SignNotifyBlacklist` | 签到通知专用名单，独立于查询权限 |
| `AliceUID_CommunityPaused` | 暂停全部社区任务 |
| `AliceUID_CommunityRequestRange` / `AliceUID_CommunityAccountRange` | 请求/换号随机秒数范围，默认`5-15` / `10-120`，重启生效 |
| `AliceUID_AIQueryEnabled` | 允许Core AI调用四类只读查询，默认关闭，开启后重启，关闭立即生效 |
| `Database*` | 公共数据库任务数、下载/存储/时间预算及周检开关 |

`AliceUID_ResourceCacheSeconds` 是兼容键，当前成功图片窗口固定300秒。`AliceUID_MasterQQ` 只作主人标记，不提升Core权限。完整配置字段见[开发文档](DEVELOPMENT.md)。

## 数据与使用范围

运行数据统一位于 Core 资源目录的 `AliceUID/`：公开静态表与图库可复用，配置、密钥、绑定数据库、用户快照及图片缓存按原部署备份。开发工作区中的版本目录名不参与生产路径。

当前只查询发命令者本人的绑定。公开图库有某套皮肤不表示账号拥有；皮肤展示依据本人接口报告并标注缺图/基础回退。分享链接或登记UID不会提供匿名私人练度查询。

官网日历使用官网默认内容，不按绑定区服筛选，暂不支持历史月份。当前不提供跨成员私人练度、任意历史赛季选择或评分系统。

## 排查入口

| 现象 | 先检查什么 |
|---|---|
| 登录页无法打开 | 登录基地址是否可达、`/nikke/` 是否正确转发、浏览器是否安装 |
| Cookie失效 | 使用 `nk重新登录`；换号才需要解绑 |
| 用户/群不能查询 | Core权限及插件群/用户四名单 |
| 图鉴或立绘缺图 | `nk数据库更新 状态`、公开源冷却、角色/皮肤映射 |
| 收菜1302127 | 查看本次错误与短冷却提示，稍后重试；持续错误属于待实机确认的上游情况 |
| 图片生成失败 | 字体与原生渲染依赖、外置渲染配置；`nk帮助 文字` 可获取文字指南 |
| 转发迟到、重复或临时变成普通消息 | 检查消息ID回执、转发等待配置及60秒暂停状态，详见[转发设置](#转发设置) |
| 升级后仍像旧版 | 确认覆盖整个外壳并完整重启Core，未同时加载旧插件 |

开发入口、缓存状态机、接口参数和验证方法见 [DEVELOPMENT.md](DEVELOPMENT.md)。本文件介绍当前功能与使用方式，历史变化集中在 [CHANGELOG.md](CHANGELOG.md)。

## 效果预览

**点击每张图片上方的标题或小三角，即可展开或收起图片。** 前五张默认展开，可按需折叠；Day2出刀总览较长，默认折叠。点击图片可查看高清原图。

以下为功能展示示例，具体数据以实际查询为准；命令采用默认 `nk` 前缀。

<details open>
<summary><strong>图1 · 妮姬练度查询｜点击展开 / 收起</strong></summary>

使用 `nk角色名练度`，例如 `nk爱丽丝练度`，查看本人角色的装备、技能与养成详情。

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/10/20/aea2f6cd6ea2591242d1a07ee1a70f90.png">
    <img src="https://s1.imagehub.cc/images/2026/10/20/aea2f6cd6ea2591242d1a07ee1a70f90.png" width="660" alt="妮姬练度查询示例：角色立绘、装备与技能详情">
  </a>
</p>

</details>

<details open>
<summary><strong>图2 · 个人名片｜点击展开 / 收起</strong></summary>

使用 `nk信息` 或 `nk名片`，展示指挥官资料、主页队伍和角色立绘。

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/10/20/64a52a67726a795a5bb2a1df6bbc85e5.png">
    <img src="https://s1.imagehub.cc/images/2026/10/20/64a52a67726a795a5bb2a1df6bbc85e5.png" width="720" alt="个人名片示例：指挥官资料、角色立绘与主页展示队伍">
  </a>
</p>

</details>

<details open>
<summary><strong>图3 · 资源查询与预计满仓时间 · 暗色主题｜点击展开 / 收起</strong></summary>

使用 `nk资源查询`，查看资源、保管箱容量与预计回满时间；时间预估基于本次查询快照。

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/10/20/1b94addf6276f536bd6628aa8bd0c49e.png">
    <img src="https://s1.imagehub.cc/images/2026/10/20/1b94addf6276f536bd6628aa8bd0c49e.png" width="900" alt="暗色主题资源查询：资源与保管箱容量、预计满仓时间">
  </a>
</p>

</details>

<details open>
<summary><strong>图4 · 保管箱接近满仓的颜色提示 · 亮色主题｜点击展开 / 收起</strong></summary>

资源查询图中的保管箱提示条会随占用比例变色。此图展示接近满仓时的红色警戒色；这是查询图片内的状态提示，不是定时或主动推送提醒。

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/10/20/a363a6f9c270f4fe24001417e8e0f7e3.png">
    <img src="https://s1.imagehub.cc/images/2026/10/20/a363a6f9c270f4fe24001417e8e0f7e3.png" width="900" alt="亮色主题资源查询：保管箱接近满仓时，提示条变为红色警戒色">
  </a>
</p>

</details>

<details open>
<summary><strong>图5 · 个人出刀详情｜点击展开 / 收起</strong></summary>

使用 `nk出刀详情`，查看本人会战队伍与对应的伤害、击杀记录。

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/10/20/69d53dbc204a634d511d40c0e2cabb6d.png">
    <img src="https://s1.imagehub.cc/images/2026/10/20/69d53dbc204a634d511d40c0e2cabb6d.png" width="900" alt="个人出刀详情示例：本人会战队伍、伤害及击杀信息">
  </a>
</p>

</details>

<details>
<summary><strong>图6 · Day2联盟成员出刀总览 · 长图默认折叠｜点击展开 / 收起</strong></summary>

使用 `nk出刀速查 Day2`，查看成员出刀总览、输出前三、击杀前三，以及尚未完成出刀的成员。图片较长，可点击打开高清原图查看细节。

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/10/20/c6214312dc66e19bf15358682e2ab903.png">
    <img src="https://s1.imagehub.cc/images/2026/10/20/c6214312dc66e19bf15358682e2ab903.png" width="900" alt="Day2联盟出刀总览长图：成员出刀情况、输出前三、击杀前三与未完成名单">
  </a>
</p>

</details>

## 鸣谢

感谢 [dildoro.com 妮姬伤害计算器·DILDORO](https://dildoro.com/) 提供妮姬伤害模拟、排行编队推荐及本功能采用的网站截图内容。AliceUID不将这些推荐与截图内容声明为独立原创，结果卡片同时标注来源与联合署名：

`Powered By GsCore & Created By  AliceUID & dildoro`

感谢 GsCore 提供插件运行、消息处理与卡片渲染基础。NIKKE角色、图片与游戏资料的权利归各权利人所有。

## 反馈与贡献

遇到问题或有功能建议，欢迎提交 [Issue](https://github.com/dddada123/AliceUID/issues)。请附插件版本、GsCore版本、复现步骤，以及脱敏后的日志或截图；不要上传 Cookie、Token、密码或验证码。

想参与开发可先阅读 [开发文档](DEVELOPMENT.md)，也欢迎通过 [Pull Request](https://github.com/dddada123/AliceUID/pulls) 改进代码和文档。如果觉得插件有帮助，点一颗 Star 也是很好的支持 ⭐

## Star History

<p align="center">
  <a href="https://www.star-history.com/?repos=dddada123%2FAliceUID&amp;type=date&amp;legend=top-left">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=dddada123/AliceUID&amp;type=date&amp;theme=dark&amp;legend=top-left">
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=dddada123/AliceUID&amp;type=date&amp;legend=top-left">
      <img src="https://api.star-history.com/chart?repos=dddada123/AliceUID&amp;type=date&amp;legend=top-left" width="800" alt="AliceUID Star History Chart">
    </picture>
  </a>
</p>

## ☕ 赞助与支持（完全自愿）

本插件及其核心逻辑**完全免费、永久开源**。

如果 AliceUID 帮你更方便地查询妮姬资料、查看联盟会战或完成社区日常，欢迎随缘打赏，就当请作者喝杯咖啡或者买个甜甜圈啦～ ❤️

赞助完全自愿，不影响任何现有功能的使用。感谢每一位使用、反馈和支持插件的指挥官！

<div align="left">
  <img src="https://raw.githubusercontent.com/dddada123/astrbot_plugin_chisa_still_eating/main/assets/wechat_pay.png" width="200" height="200" alt="微信赞助码">
  &nbsp;&nbsp;&nbsp;
  <img src="https://raw.githubusercontent.com/dddada123/astrbot_plugin_chisa_still_eating/main/assets/alipay.png" width="200" height="200" alt="支付宝赞助码">
</div>
