<p align="center">
  <a href="https://github.com/dddada123/AliceUID">
    <img src="https://raw.githubusercontent.com/dddada123/AliceUID/main/ICON.png" width="256" alt="AliceUID">
  </a>
</p>

<h1 align="center">AliceUID</h1>

<p align="center">
  <a href="https://github.com/Genshin-bots/gsuid_core"><img src="https://img.shields.io/badge/Framework-GsCore-8A2BE2?style=flat-square" alt="Framework: GsCore"></a>
  <a href="https://github.com/dddada123/AliceUID/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License: MIT"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/Version-1.0.07-ff69b4?style=flat-square" alt="Version: 1.0.07"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-%E2%89%A53.10-3776AB?style=flat-square&amp;logo=python&amp;logoColor=white" alt="Python: ≥3.10"></a>
  <a href="https://github.com/dddada123/AliceUID/stargazers"><img src="https://img.shields.io/github/stars/dddada123/AliceUID?style=flat-square" alt="GitHub Stars"></a>
</p>

适用于 GsCore 的《胜利女神：NIKKE》插件，提供本人账号绑定、个人资料、角色练度、皮肤图鉴、联盟会战、资源与保管箱查询，以及可选的社区日常任务。当前版本 **1.0.07**，默认使用 `nk` 前缀，也支持后台自定义。

[亮点功能](#亮点功能) · [效果预览](#效果预览) · [版本记录](CHANGELOG.md) · [开发文档与接口映射](DEVELOPMENT.md) · [问题反馈](https://github.com/dddada123/AliceUID/issues)

<p align="center">
  <img src="https://count.getloli.com/@AliceUID?theme=nixietube-1&amp;padding=7&amp;offset=0&amp;align=top&amp;scale=1&amp;pixelated=1&amp;darkmode=auto" alt="AliceUID 访问计数">
</p>

## 功能

| 功能 | 能做什么 |
|---|---|
| 账号绑定 | 网页账号密码、邮箱验证码，或私聊导入 Cookie；支持原账号重新登录更新凭据 |
| 个人信息 | 指挥官身份、战役与爬塔、前哨与统计、主页展示队伍；主立绘与队员角标 |
| 角色练度 | 本人持有角色的装备、技能、词条、魔方、收藏品与好感；支持简繁角色名与别名 |
| 完整图鉴 | 十列已持有角色头像、姓名及星级/核心角标，按接口报告展示皮肤 |
| 联盟会战 | 出刀速查、本人队伍详情、漏刀/尾刀、伤害及击杀排行、BOSS血量；区分当前与历史赛季 |
| 收菜与资源 | 八类资源、保管箱容量、到90%与回满的北京时间估算；查询不会自动领取资源 |
| 活动日历 | 匿名截取官网当前默认日历，显示来源与拍摄时间 |
| 社区日常 | 本人手动签到，或按本人授权启用签到/浏览/点赞；自动任务默认关闭 |
| 管理与外观 | 群/用户四名单、角色别名管理、公共资料库更新、亮暗/随机主题、字体与毛玻璃强度 |

支持日服、北美服、韩服、国际服、东南亚服。登录时必须明确选服；港澳台网页登录流程暂未支持。

## 亮点功能

### ⚔️ 会战血量与联盟成员出刀总览

- **BOSS血量查询**：发送 `nk会战血量`，查看联盟会战阶段、BOSS血量与进度；休赛期可展示上一期记录，并注明赛季与数据状态。
- **Day2出刀总览**：发送 `nk出刀速查 Day2`，集中查看联盟成员出刀情况、输出前三、击杀前三，以及尚未完成出刀的成员，方便掌握联盟整体进度。
- **本人出刀详情**：发送 `nk出刀详情`，查看本人队伍、伤害与击杀记录；还可用 `nk出刀缺刀`、`nk出刀尾刀` 分别查看未完成名单与尾刀统计。

### 📦 资源查询与满仓时间预估

发送 `nk资源查询`，查看资源与保管箱容量，并根据本次查询快照预估到90%及回满的北京时间。保管箱提示条随占用比例变色，接近满仓时在查询图内呈现红色警戒色，方便一眼识别。

这里的满仓时间是**预估值**；“提醒”仅指资源查询图片中保管箱提示条的颜色变化，**不会主动推送满仓消息，也不会自动领取资源**。

### 🎨 个人名片、角色练度与亮暗主题

`nk信息` 展示指挥官资料、主页队伍与完整主立绘；`nk爱丽丝练度` 等角色命令展示本人的装备、技能、词条、魔方、收藏品与好感。卡片支持亮色、暗色及随机主题，字体和毛玻璃强度可在后台调整。

下方[效果预览](#效果预览)收录六张示例图，可直接查看名片、练度、资源预估及出刀总览的展示效果。

## 安装与升级

插件依赖 GsCore 的命令、数据库、WebUI、调度器和原生渲染服务，不能作为独立 Bot 运行。项目声明 Python ≥3.10，具体依赖见 [requirements.txt](requirements.txt) 和 [pyproject.toml](pyproject.toml)。

1. 首次安装或升级前备份原插件及其运行数据。解压安装包，把整个外壳放入 `plugins/AliceUID/`。
2. 保留以下嵌套结构，不要只拷内层包，也不要将开发目录 `AliceUID_1.0.07` 当成插件目录。
3. 在运行 GsCore 的 Python 环境安装插件依赖。使用网页登录或官网日历时，准备 Playwright Chromium。
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

`登录` 和 `登陆` 两种写法均可，例如 `nk登录日服`、`nk登陆国际服`、`nk重新登陆`。不带区服的 `nk登录` 会给出选服提示。

私人查询会识别已知过期、HTTP401和业务登录失效，并提示重新登录；已知失效凭据不会继续使用旧图缓存。普通网络、403权限拒绝和429限流不会统一误报为Cookie过期。

打开本人命令返回的登录链接完成验证；Cookie 失效时用 `nk重新登录` 更新同账号同区服凭据。换号或换服先 `nk解绑`，再重新选择。

「登录链接用转发消息」为**实验性功能**，默认开启，登录和重新登录共用；二维码开关独立。开启转发后，二维码会放入转发中。OneBot私聊、Core非“允许”转发策略或发送失败时改用普通消息，复用原链接和二维码。转发节点外不附加 `@`。如果开启后看不到消息，请关闭此功能回退普通模式。

### 实验性转发（默认开启，未确认时自动回退）

**转发目前仍可能发送失败，特别是帮助和出刀长图，1.0.07尚未解决其投递稳定性。** 当前NapCat通道失败或未确认发送时会自动回退一次普通消息，并暂停该连接转发5分钟；暂停期间后续查询直接普通发送。进一步修复安排在1.0.08，本版不承诺转发一定成功。

`nk帮助`、`nk卡片`、`nk出刀` 与登录链接各有独立的转发开关，**本版全部默认开启，已有设置保留**。开启后，图片前的首节点显示明确标题：帮助为“AliceUID帮助”，图鉴为“AliceUID·游戏昵称·图鉴展示”，出刀为“AliceUID·公会名-出刀统计”。帮助文字版、生成进度、错误和其它短卡片不受影响。

已移除AliceUID中的“使用当前QQ身份”选项与上次不适用于NapCat直连的NoneBot适配，不再往转发节点中加入身份控制段。头像和昵称沿用你使用的GsCore适配器设置，默认可保持“小助手”；xiowo的NapCat适配器本身支持当前机器人身份，详见[通道与回退说明](integrations/README.md)，无需为AliceUID额外安装机器人前端。

识别到NapCat适配器连接时，会请求Core消息ID回执；未取得确认则回退一次普通原图，并暂停该连接转发5分钟，后续查询直接普通发送。迟到成功可能造成一次重复。旧Core不支持回执时直接普通发送。如果群内仍不可见，可关闭对应转发开关；升级前已关闭的设置不会自动打开。

帮助与出刀等不透明图片在转发时生成高质量 JPG 副本，默认质量 **95**，后台可设 **0–100整数**，下次转发生效。100仍是有损编码，数值不是文件压缩比例。图片保留原宽度和DPI，超过4096像素高或单页4MiB时完整分页，不缩放或截断内容。符合限制的现有JPG直接发送；透明图保留PNG，登录二维码和普通发送使用原图。该处理不能修复NapCat到QQ上传服务器的网络连接超时，详见[排查说明](integrations/README.md)。

## 常用命令

| 命令 | 用途 |
|---|---|
| `nk帮助` / `nk帮助 文字` | 按权限显示图片指南或可复制文字 |
| `nk登录日服` | 五区登录；日服可替换为国际服/北美服/韩服/东南亚服 |
| `nk重新登录` | 更新原账号同区服 Cookie，失败保留原绑定 |
| `nk我的账号` / `nk解绑` | 查看或解除登录绑定 |
| `nk信息` / `nk名片` | 本人个人资料与展示队伍 |
| `nk刷新信息` | 清理个人资料缓存，随后重新查询 |
| `nk爱丽丝练度` / `nk爱丽丝面板` | 查询指定角色练度 |
| `nk练度 爱丽丝 刷新` | 显式刷新该角色详情 |
| `nk卡片` | 完整已持有角色图鉴 |
| `nk更新面板` / `nk刷新面板` | 更新本人资料并使相关面板缓存失效 |
| `nk出刀` | 联盟出刀速查与排行 |
| `nk出刀 Day1` / `nk出刀速查 Day2` | 选择会战阶段 |
| `nk出刀详情` / `nk出刀缺刀` / `nk出刀尾刀` | 本人队伍、未完成名单、尾刀统计 |
| `nk会战血量 [刷新]` | 联盟阶段及 BOSS 血量 |
| `nk资源查询 [刷新]` | 本人资源与保管箱状态 |
| `nk日历` / `nk日历 帮助` | 官网当前默认活动日历及范围说明 |
| `nk黑莲别名查询` | 查询角色本名及已注册别名 |
| `nk绑定UID` / `nk我的UID` / `nk解绑UID` | 单独登记、查看或清理社区/游戏/分享标识 |

方括号表示可选参数，不需要输入方括号。UID登记只保存标识，不代表登录成功或允许查询他人的私人资料。

## 收菜查询与缓存

没有可用缓存图片时，会重新获取本人资料并渲染。只有成功生成有效图片后才开始 **5分钟复用窗口**；窗口内重复查询或附带“刷新”均复用该图，窗口不会因重复查询延长。

取数或渲染失败不会锁满5分钟：普通失败保留5秒短间隔，403/429拒绝或限流使用独立60秒冷却。图片生成成功但消息发送失败时，下次查询可重发已有图片。查询本人资料的接口仍可能失败，错误1302127不能保证通过重试消除。

保管箱超过70%显示橙色，超过90%显示红色，满量显示MAX。到90%及回满时间以本次快照、24小时回满假设和北京时间计算；未知或隐藏容量不作估算。它是状态查询，不执行游戏内收取。

角色练度会复用已有面板数据；图鉴在内容未变时复用图片，成功发送后续期。会战数据会核验本人当前联盟与官方赛季，历史记录明确标注来源。

## 社区任务

| 命令 | 行为 |
|---|---|
| `nk签到` | 立即执行本人本周期签到；已成功不重复请求 |
| `nk开启全量签到` | 为本人开启签到、浏览及点赞，并立即执行一轮 |
| `nk自动社区 状态` | 查看授权、暂停原因和执行状态 |
| `nk自动社区 开启` / `关闭` | 开启签到与浏览，或停止自动任务 |
| `nk自动社区 点赞开启` / `点赞关闭` | 单独调整点赞授权 |

周期以北京时间08:00划分，默认每天08:33开始执行已授权账号的自动任务。Bot主可在GsCore后台的「每日签到时间（北京时间）」填写HH:MM，精确到分钟，保存后立即更新调度；手动签到无需等到定时时刻，但仍须排队、限频。

单次请求间隔默认随机 **5～15秒**，换账号在上一账号最后响应后默认随机等待 **10～120秒**。后台分别填写 `5-15`、`10-120`，也可改成 `2-5`；允许1～3600秒和最多三位小数，前者不能大于后者，同值如 `15-15` 为固定间隔。保存后完整重启Core生效。换号同时满足两种间隔，取较晚时刻，不把两段等待相加。

每账号每周期最多30次请求，含查询与失败；签到最多一次、浏览和点赞各最多5帖。失败暂停、不自动重试，不通过重启或开关任务重置预算。当前不自动评论、发帖、金币兑换或执行未知活动任务。重新登录后需要重新开启自动社区授权。

回执按实际确认显示，例如：`已完成本轮签到✅ 点赞5帖✅ 浏览5帖✅ 当前金币🪙：16726`。没有执行的互动不补零或冒报；后续任务失败会保留已确认签到和成功数量，并说明暂停。默认不再附完整日期区间，周期仍可在签到查询/状态中核对。

Bot主可在群内发送 `nk签到查询` 或 `nk签到查询 2` 翻页，查看本周期本群绑定/近30天使用过插件账号的本地记录。显示已签到、待执行、暂停、登录失效或未确认；这不是实时全员名单，也不会借成员Cookie重新请求社区。在官网自行签到但尚未被插件读取的账号不会被猜测为已完成。

升级时保留旧周期的请求预算与不确定写入，避免重复提交；旧账本没有精确时间戳时，首次周期可能采取保守限次。08:00前设置的自动时刻归属前一刷新周期。

## 管理与配置

### 自定义唤醒指令

在GsCore的AliceUID设置中启用「自定义唤醒指令」，填写1～12位中英文字母、数字、`_`或`-`，例如 `alice`、`妮姬`，保存后完整重启Core。

- 默认关闭自定义：只用原 `nk`。
- 启用自定义、保留默认：例如 `nk登录` 和 `alice登录` 都可用，帮助和提示继续显示 `nk`。
- 启用自定义且禁用默认：仅 `alice登录` 等可用；图片/文字帮助、区服提示、Cookie失效提示和登录网页均显示 `alice`。

前缀按填写内容区分大小写，不改变角色名、权限或绑定。本文命令表采用默认 `nk`；独占自定义时换成你设置的前缀。

数据库周检的周五02:33是独立任务，与每天08:33的社区签到不同。

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
| `AliceUID_ForwardJpegQuality` | 新编码转发图片的JPG质量，整数0–100，默认95；100仍非无损 |
| `AliceUID_LoginQRCode` | 同时发送二维码；普通、转发及失败回退均适用，默认关闭 |
| `AliceUID_BrowserChannel` / `AliceUID_Headless` | 登录浏览器通道及无头运行 |
| `AliceUID_CardTheme` | 新默认random随机亮暗；命中缓存不重复随机，已有自定义值保留 |
| `AliceUID_CardLanguage` / `AliceUID_CardFont` | 显示语言及 `formts/` 内字体，失败使用兜底字体 |
| `AliceUID_GlassStrength` | 0～100%背景模糊，默认20%；前景文字和人物保持清晰，已有值保留 |
| `AliceUID_UnionCacheSeconds` | 当期会战共享缓存，默认180秒 |
| `AliceUID_RemoteRenderEnable` | 可选外置HTML渲染服务；默认关闭，失败回退Core原生渲染 |
| `AliceUID_CommunitySignTime` | 每日自动签到的北京时间，默认`08:33`，支持`00:00`～`23:59`，保存后更新调度 |
| `AliceUID_CommunityPaused` | 暂停全部社区任务 |
| `AliceUID_CommunityRequestRange` / `AliceUID_CommunityAccountRange` | 请求/换号随机秒数范围，默认`5-15` / `10-120`，重启生效 |
| `AliceUID_CustomPrefixEnabled` / `AliceUID_CustomPrefix` | 自定义前缀开关/内容，重启生效 |
| `AliceUID_DisableDefaultPrefix` | 自定义启用时是否关闭默认nk并同步帮助文案，重启生效 |
| `Database*` | 公共数据库任务数、下载/存储/时间预算及周检开关 |

`AliceUID_ResourceCacheSeconds` 是兼容键，当前成功图片窗口固定300秒。`AliceUID_MasterQQ` 只作主人标记，不提升Core权限。完整配置字段见[开发文档](DEVELOPMENT.md)。

## 数据与使用范围

运行数据统一位于 Core 资源目录的 `AliceUID/`：公开静态表与图库可复用，配置、密钥、绑定数据库、用户快照及图片缓存按原部署备份。开发工作区中的版本目录名不参与生产路径。

当前只查询发命令者本人的绑定。公开图库有某套皮肤不表示账号拥有；皮肤展示依据本人接口报告并标注缺图/基础回退。分享链接或登记UID不会提供匿名私人练度查询。

官网日历使用官网默认内容，不按绑定区服筛选，暂不支持历史月份。当前没有跨成员私人练度、任意历史赛季选择、单人突袭或评分系统。

## 排查入口

| 现象 | 先检查什么 |
|---|---|
| 登录页无法打开 | 登录基地址是否可达、`/nikke/` 是否正确转发、浏览器是否安装 |
| Cookie失效 | 使用 `nk重新登录`；换号才需要解绑 |
| 用户/群不能查询 | Core权限及插件群/用户四名单 |
| 图鉴或立绘缺图 | `nk数据库更新 状态`、公开源冷却、角色/皮肤映射 |
| 收菜1302127 | 查看本次错误与短冷却提示，稍后重试；持续错误属于待实机确认的上游情况 |
| 图片生成失败 | 字体与原生渲染依赖、外置渲染配置；`nk帮助 文字` 可获取文字指南 |
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
