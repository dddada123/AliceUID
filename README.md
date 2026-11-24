<p align="center">
  <a href="https://github.com/dddada123/AliceUID">
    <img src="https://raw.githubusercontent.com/dddada123/AliceUID/main/ICON.png" width="240" alt="AliceUID">
  </a>
</p>

<h1 align="center">AliceUID</h1>

<p align="center">
  <strong>适用于 GsCore 的《胜利女神：NIKKE》全能战术数据插件</strong><br>
  个人名片 · 角色练度与图鉴 · 全量导出与等级模拟 · 联盟会战与攻略 · 资源收菜提醒 · 自动兑换码 · 社区签到 · DILDORO 个人突袭推荐
</p>

<p align="center">
  <a href="https://github.com/Genshin-bots/gsuid_core"><img src="https://img.shields.io/badge/Framework-GsCore-8A2BE2?style=flat-square" alt="Framework: GsCore"></a>
  <a href="https://github.com/dddada123/AliceUID/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License: MIT"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/Version-1.3.06-ff69b4?style=flat-square" alt="Version: 1.3.06"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-%E2%89%A53.10-3776AB?style=flat-square&amp;logo=python&amp;logoColor=white" alt="Python: ≥3.10"></a>
  <a href="https://github.com/dddada123/AliceUID/stargazers"><img src="https://img.shields.io/github/stars/dddada123/AliceUID?style=flat-square" alt="GitHub Stars"></a>
</p>

<p align="center">
  <a href="#核心能力">核心能力</a> ·
  <a href="#安装与升级">安装与升级</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#常用指令一览">常用指令</a> ·
  <a href="#功能详解">功能详解</a> ·
  <a href="#效果预览">效果预览</a> ·
  <a href="#常见问题qa">常见问题（QA）</a> ·
  <a href="CHANGELOG.md">更新日志</a> ·
  <a href="DEVELOPMENT.md">开发文档</a>
</p>

<p align="center">
  <img src="https://count.getloli.com/@AliceUID?theme=nixietube-1&amp;padding=7&amp;offset=0&amp;align=top&amp;scale=1&amp;pixelated=1&amp;darkmode=auto" alt="AliceUID 访问计数">
</p>

---

> **当前版本：1.3.06**
>
> - **爱丽丝 / 说明文双风格通知与签到异常合并转发**：后台支持一键切换 `爱丽丝风格`（默认）与 `默认说明文`，覆盖收菜提醒、签到、兑换码、群播报与等待提示；每日签到异常名单自动按报错原因合并人员并默认以合并转发消息发送（`AliceUID_SignNoticeForward`），同时清理 `nk资源查询` 等多处冗余规则说明。
> - **全卡片 Bento 战术玻璃 v2 大统一**：全量卡片统一为暗版琥珀金 / 亮版珊瑚红视觉，支持横版大立绘 `-100%` ~ `+100%` 自定义缩放；`nk资源查询` 配备 8 色顶部条纹与保管箱 `>>>>>>` 充能进度条。
> - **爱丽丝专属兑换码提醒与结果标识**：使用 `nk兑换码ABCDEFG` 命中本地已有兑换记录时，爱丽丝将用专属口吻告知兔子先生已兑换时间；批量兑换汇总行非零项自动附带状态 Emoji（`✅`/`❗`/`❌`/`❓`）。
> - **稳定三档串行查询**：游戏查询提供高速（1 秒）/ 中速（推荐，默认 2 秒）/ 缓速（5 秒）三档串行速率；默认指令前缀为 `nk`，可在 Core 插件管理中自定义。

---

## 核心能力

| 模块 | 主要能力 |
|---|---|
| **养成卡片与导出** | 横版 / 纵版亮暗角色练度卡、高透玻璃指挥官名片、完整皮肤图鉴；支持本人与公开链接的 **Excel / JSON（schema v3）全量导出**与 **1400 级内任意指定等级模拟**。 |
| **联盟会战与攻略** | BOSS 血量、出刀总览、Day1 / Day2 切换、成员阵容按伤害排名查询、缺刀与尾刀统计，以及带作者来源与原图长截图的会战阵容攻略。 |
| **资源与收菜提醒** | 紧凑化 8 类核心资源与前哨保管箱进度卡（90% 警戒刻度 + 满仓时间估算），支持按群聊/私聊独立开启 90%、满仓及睡前收菜提醒与免打扰。 |
| **兑换码与自动兑换** | 汇总官方、GameWith 与成员贡献三源并跨源去重；支持手动与自动兑换、新绑定即时补领，重复输入单码时由爱丽丝贴心提示已兑时间。 |
| **社区任务与活动日历** | 本人授权手动/自动社区签到、浏览与点赞（支持单群/全群通知控制），以及官网当前活动日历截图。 |
| **DILDORO 个人突袭** | 接入 [DILDORO](https://dildoro.com/) 按本人养成生成推荐编队与模拟伤害卡片；支持受限账号临时公开妮姬资料并后台自动恢复、翻译异常自动切换原文与降级出图。 |
| **可选 Core AI 查询** | 配合 GsCore AI 开启只读工具后，可用自然语言查询本人资料、角色练度、别名与帮助（默认关闭，不开放登录与写操作）。 |

---

## 安装与升级

AliceUID 依托 **GsCore** 运行，不支持独立启动，环境要求 **Python ≥ 3.10**。

1. **备份与解压**：备份原有插件及 `data/AliceUID` 数据目录，将 **完整安装 ZIP** 解压至 GsCore 的 `plugins/` 父目录覆盖同名文件（完整包已内置图片、背景与字体，无需额外下载素材包）。
2. **安装依赖**：在 **GsCore 实际使用的 Python 环境** 中执行：

```bash
python -m pip install -r plugins/AliceUID/requirements.txt
```

3. **配置与重启**：在 Core WebUI 配置外部可访问的登录地址、黑白名单及卡片外观，**完整重启 Core** 后发送 `nk帮助` 验证。首次启动会自动更新最新角色目录。

> **升级注意事项**
> - 请保留 `plugins/AliceUID/AliceUID/` 的嵌套目录结构，切勿只复制内层目录，也不要同时启用多份同名插件。
> - 升级请保留原 `data/AliceUID`、绑定数据库、加密密钥及 `cdk.sqlite3`（保存兑换回执与自动兑换记录）。
> - 常规卡片（名片、角色练度、图鉴、资源、会战、帮助）默认由 **GsCore 内置原生渲染引擎** 生成；网页登录、官网日历、会战攻略与 DILDORO 个人突袭使用 Playwright，插件默认复用 Core 的 Playwright 并自动补齐配套 Chromium（Cookie 导入登录本身不启动浏览器）。
> - 从旧版 NikkeUID 迁移时仅复用公开素材，需在 AliceUID 中重新登录。

---

## 快速开始

支持 **日服、北美服、韩服、国际服、东南亚服**，登录时需显式选服（港澳台网页登录、邮箱验证码登录暂未开放）。

1. 发送 `nk登录日服`（可将 `日服` 替换为目标区服，支持 `登录` / `登陆`），打开本人专属一次性链接。
2. 在网页中使用账号密码完成验证，或直接导入 Cookie 请求头 / `cookies.txt` 文件（输入框默认打码保护）。
3. 登录成功后插件会在后台自动采集完整资料并向原会话发送指挥官名片；随后即可使用 `nk信息`、`nk爱丽丝练度`、`nk卡片`、`nk资源查询` 等指令。

> 凭据失效请发送 `nk重新登录` 更新同区服 Cookie（失败自动保留原绑定）；换号或换服请先 `nk解绑`。

---

## 常用指令一览

方括号 `[ ]` 表示可选参数，实际输入时无需带括号；更多权限可见指令请发送 `nk帮助` 或 `nk帮助 文字`。

### 账号与隐私
| 命令 | 说明 |
|---|---|
| `nk登录日服` | 五区登录（日服 / 国际服 / 北美服 / 韩服 / 东南亚服） |
| `nk重新登录` | 更新原账号同区服 Cookie，失败保留原绑定 |
| `nk我的账号` / `nk解绑` | 查看绑定摘要或解除当前绑定 |
| `nk妮姬公开` / `nk妮姬隐藏` / `nk妮姬公开状态` | 管理本人官网妮姬资料公开范围与待恢复状态 |
| `nk绑定UID` / `nk我的UID` / `nk解绑UID` | 登记或清理个人分享标识（不能代替登录） |

### 养成、图鉴与导出
| 命令 | 说明 |
|---|---|
| `nk信息` / `nk名片` | 指挥官名片与主页展示队伍（第 3 槽位为大立绘） |
| `nk信息刷新` / `nk刷新信息` | 轻量刷新名片资料 |
| `nk刷新面板` | 全量更新全部角色练度与皮肤缓存 |
| `nk爱丽丝练度` / `nk爱丽丝面板` | 查看指定角色练度卡（横版 / 纵版由后台配置控制） |
| `nk刷新爱丽丝面板` | 仅刷新指定角色练度与对应循环室数据 |
| `nk卡片` | 完整已持有角色与皮肤图鉴 |
| `nk黑莲别名查询` | 查询角色本名及已注册别名 |
| `nk练度全量导出` / `nk练度全量导出json` | 导出本人实际等级 Excel / JSON |
| `nk400练度全量导出` / `nk1000全量导出JSON` | 导出原始与指定等级模拟对照（支持自定义等级与公开链接组合） |

### 联盟会战、资源与个人突袭
| 命令 | 说明 |
|---|---|
| `nk出刀` / `nk查刀` | 联盟会战总览与出刀排行 |
| `nk出刀 Day1` / `nk出刀速查 Day2` | 切换查看 Day1 / Day2 会战阶段 |
| `nk出刀详情 [排名]` | 查本人出刀详情；带数字按本联盟伤害排名查看成员阵容 |
| `nk出刀缺刀` / `nk出刀尾刀` | 未完成出刀名单与尾刀统计 |
| `nk会战血量 [刷新]` | 当前联盟阶段与 BOSS 血量进度 |
| `nk会战阵容` / `nk会战攻略` | 转发当前或最近一期会战阵容攻略（标题、原图、长截图） |
| `nk资源查询 [刷新]` | 查看 8 类核心资源与保管箱 90% / 满仓时间估算 |
| `nk开启收菜提醒` / `nk关闭收菜提醒` | 按当前群聊或私聊独立开关 90%、满仓与睡前提醒 |
| `nk收菜提醒状态` / `nk收菜免打扰 00:00-08:00` | 查看本地提醒状态或设置当前会话免打扰时段 |
| `nk个人突袭推荐 [属性] [亮色/暗色/随机]` | 接入 DILDORO 生成推荐编队（别名 `nk单人突袭推荐`；加 `刷新` 强制重算） |

### 兑换码、社区与日历
| 命令 | 说明 |
|---|---|
| `nk查询兑换码` / `nk兑换码 速查` | 只读查询当前有效兑换码详情或极简清单 |
| `nk兑换码 [兑换码]` | 尝试兑换当前全部或指定兑换码（已由插件兑过将触发爱丽丝专属提醒） |
| `nk增加兑换码ABCDEFG` | 本人核验有效后贡献至共享码池并触发新码派发 |
| `nk自动兑换码` / `nk关闭自动兑换码` | 个人自动兑换开关 |
| `nk签到` / `nk开启全量签到` | 执行本人社区签到，或授权签到+浏览+点赞自动任务 |
| `nk自动社区 状态` / `nk自动社区 关闭` | 查看或停止自动社区任务 |
| `nk日历` / `nk日历 帮助` | 获取官网当前默认活动日历截图 |

### Bot 主管理指令
| 命令 | 说明 |
|---|---|
| `nk日志导出[数字]` | 导出最近 `1~1440` 分钟脱敏诊断日志 MD（推荐 `nk日志导出5`） |
| `nk账号列表` / `nk绑定列表` | 查看绑定概览（群内号码自动脱敏，私聊完整显示） |
| `nk数据库更新` / `nk数据库更新 状态` | 手动触发或查看公开角色库与图库维护进度 |
| `nk刷新兑换码` | 手动刷新官方 / GameWith 公开兑换码库存 |
| `nk启用自动兑换码` / `nk停用自动兑换码` | 自动兑换系统总开关 |
| `nk全群自动兑换码` / `nk关闭全群自动兑换码` | 批量设置当前群绑定用户的自动兑换开关 |
| `nk全员自动兑换码` / `nk关闭全员自动兑换码` | 批量设置全部绑定用户的自动兑换开关 |
| `nk签到查询 [页码]` | 查询本群已知账号的当日签到确认状态 |
| `nk签到群通知 开启/关闭/状态` | 管理当前群的签到汇总通知（快捷：`nk开启/关闭签到群通知`） |
| `nk全群签到通知 开启/关闭/状态` | 批量设置全部群通知策略（支持单群后续覆盖） |

---

## 功能详解

### 养成查询、练度导出与等级模拟
- 普通查询与导出默认读取本地缓存；需要最新数据时主动使用 `nk刷新信息`、`nk刷新面板` 或 `nk刷新爱丽丝面板`。升级后首次本人导出会自动识别旧缓存并执行一次完整升级刷新。
- **全量导出组合语法**：支持 `nk练度全量导出`、`nk练度全量导出json`、`nk400练度全量导出`、`nk400练度全量导出json 链接` 等组合。公开链接支持 Blablalink 主页（`/shiftyspad`）或妮姬列表页 URL（`uid` 与 `openid` 并存时按官网规则优先 `uid`；无标识链接按本人处理），需发起者已登录对应版本账号且目标公开妮姬资料。
- **数据口径**：Excel 支持爆裂阶段、定位、企业、属性四项联动筛选与「编号升序 / 原始战力降序」切换；JSON 采用 `schema_version=3`，`combat/attack/defense/hp` 始终表示当前实际练度，指定等级结果独立保存于 `simulation` 对象（成长资料覆盖至 1400 级，缺失数据标注原因且不补 0）。

### 联盟会战与攻略
- 当期会战同联盟共享短缓存（默认 180 秒），休赛期可长期复用已结算历史记录。出刀详情展示武器、爆裂、属性、等级、星级及核心角标（记录缺失的突破信息按严格身份匹配参考该成员本地缓存）。
- `nk会战阵容` / `nk会战攻略` 无需绑定，自动核对官方赛季归属并按顺序合并转发：原标题与作者来源、组队示例原图、正文完整长截图。

### 资源查询与收菜提醒
- `nk资源查询` 仅请求必要双接口并复用 5 分钟成功图片窗口；保管箱进度条按快照占比动态变色（>70% 橙色、>90% / MAX 红色）并标出 90% 提醒刻度线。
- 收菜提醒按群聊/私聊独立订阅，默认北京时间 `00:00–08:00` 免打扰；连续两晚 23:00–24:00 均处于 100% 满仓将自动停止提醒以免打扰。

### 兑换码与自动兑换
- 官方与 GameWith 库存每日 `00:00 / 08:00 / 16:00` 定时更新，仅对跨来源去重后的真正新码或成员新贡献触发全员派发；新绑定用户自动即时核对当前有效码。
- 手动与自动兑换均需 Bot 主在后台开启「允许本人 CDK 兑换」；当使用 `nk兑换码ABCDEFG` 命中本地已有兑换记录时，爱丽丝将以专属口吻提示兔子先生具体的已兑换时间。

### 个人突袭推荐（DILDORO）
- 自动识别网站当前赛季弱点，也可指定 `火/水/风/电/铁`（或全称），各属性缓存独立保留 5 天；重算任务按 FIFO 排队并具备 3 轮总预算与 20 秒无响应静默重试。
- 支持自动识别并套用网站最新同属性推荐配置；中文翻译异常时自动切换韩语原文继续计算，图片/字体异常支持降级出图。
- 若本人官网妮姬资料处于隐藏/仅盟友/仅好友状态，轮到同步时将自动临时公开并在截图发送后于后台持久化恢复原公开范围（最多 3 条通知，不改动其他隐私项）。

---

## 管理与配置

Bot 主可在 GsCore WebUI 调整以下配置（修改 Core 插件前缀或开启 AI 后需完整重启）：

| 分组 / 配置项 | 关键说明 |
|---|---|
| **游戏查询速度 / 风控策略** | `AliceUID_PanelRiskStrategy`：高速（1 秒）/ 中速（推荐，默认 2 秒）/ 缓速（5 秒），三档均串行；个人突袭、签到、兑换与数据库独立控制。 |
| **登录地址与 HTTPS** | `AliceUID_LoginUrl` 填写外网可访问地址（反代需转发 `/nikke/`）；开启 `LoginRequireHTTPS` 前请确认 Core 正确识别外部 HTTPS 协议。 |
| **登录方式与浏览器** | `AliceUID_LoginMode` 可选 `browser`（账密+Cookie 导入）或 `cookie`（仅导入）；`BrowserAutoInstall` 默认开启自动补装配套 Chromium。 |
| **卡片外观** | 全局主题、语言、字体可调；角色练度支持 `横版亮色` / `横版暗色` / `纵版亮色` / `纵版暗色` 及随机主题；个人突袭推荐拥有独立主题设置。 |
| **消息转发** | 帮助、图鉴、出刀、会战攻略、登录链接、账号列表与兑换码均可独立开关；NapCat 回执等待默认 30 秒（5–300 秒），未确认自动普通回退一次并暂停该连接转发 60 秒。 |
| **社区与兑换码** | `AliceUID_CommunitySignTime` 默认 `08:33`；`AliceUID_EnableWriteOps` 默认关闭，开启后方可执行 CDK 兑换。 |
| **公开数据库与 AI** | 支持首次启动、招募日历与周五 `02:33` 自动维护公开资料；`AliceUID_AIQueryEnabled` 默认关闭。 |

---

## 效果预览

**点击每张图片上方的标题或小三角，即可展开或收起图片。** 前五组默认展开，Day2 出刀总览较长默认折叠；点击图片可查看高清原图（以下示例采用默认 `nk` 前缀，实际渲染以当前版本为准）。

<details open>
<summary><strong>图1 · 妮姬练度查询｜点击展开 / 收起</strong></summary>

使用 `nk角色名练度`（如 `nk爱丽丝练度`），查看本人角色的装备超载词条、技能、魔方、收藏品与循环室。

<p align="center"><strong>宽版亮色</strong></p>
<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/10/29/2bfd48fe190ca4da68c49d29739fc3da.png">
    <img src="https://s1.imagehub.cc/images/2026/10/29/2bfd48fe190ca4da68c49d29739fc3da.png" width="900" alt="宽版亮色角色练度卡：角色立绘、装备词条、技能与循环室">
  </a>
</p>
<p align="center"><strong>宽版暗色</strong></p>
<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/10/29/20103cbcd1626d374df0ab5f2b146911.png">
    <img src="https://s1.imagehub.cc/images/2026/10/29/20103cbcd1626d374df0ab5f2b146911.png" width="900" alt="宽版暗色角色练度卡：角色立绘、装备词条、技能与循环室">
  </a>
</p>

<p align="center"><strong>纵版暗色（窄版）</strong></p>
<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/10/29/27af72b039f827da4ec7a53de114463d.png">
    <img src="https://s1.imagehub.cc/images/2026/10/29/27af72b039f827da4ec7a53de114463d.png" width="600" alt="纵版暗色角色练度卡：角色立绘、装备词条与技能养成">
  </a>
</p>

</details>

<details open>
<summary><strong>图2 · 指挥官信息名片｜点击展开 / 收起</strong></summary>

使用 `nk信息` 或 `nk名片`，以横版名片展示指挥官资料、主页队伍、主推角色立绘、战役爬塔与前哨数据。

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/10/29/ad94378a318bc927b3302e2d86e2b15d.png">
    <img src="https://s1.imagehub.cc/images/2026/10/29/ad94378a318bc927b3302e2d86e2b15d.png" width="900" alt="横版指挥官信息名片：指挥官资料、角色立绘、主页队伍、战役爬塔与前哨数据">
  </a>
</p>

</details>

<details open>
<summary><strong>图3 · 资源查询与预计满仓时间 · 暗色主题｜点击展开 / 收起</strong></summary>

使用 `nk资源查询`，查看核心资源、保管箱容量与预计回满时间；时间预估基于本次查询快照。

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/10/20/1b94addf6276f536bd6628aa8bd0c49e.png">
    <img src="https://s1.imagehub.cc/images/2026/10/20/1b94addf6276f536bd6628aa8bd0c49e.png" width="900" alt="暗色主题资源查询：资源与保管箱容量、预计满仓时间">
  </a>
</p>

</details>

<details open>
<summary><strong>图4 · 保管箱接近满仓的颜色提示 · 亮色主题｜点击展开 / 收起</strong></summary>

资源查询图中的保管箱提示条会随占用比例变色（>70% 橙色、>90% / MAX 红色）；这是查询图片内的状态提示，主动推送需另行开启收菜提醒。

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/10/20/a363a6f9c270f4fe24001417e8e0f7e3.png">
    <img src="https://s1.imagehub.cc/images/2026/10/20/a363a6f9c270f4fe24001417e8e0f7e3.png" width="900" alt="亮色主题资源查询：保管箱接近满仓时，提示条变为红色警戒色">
  </a>
</p>

</details>

<details open>
<summary><strong>图5 · 个人出刀详情｜点击展开 / 收起</strong></summary>

使用 `nk出刀详情`，查看本人或同联盟指定排名成员的会战队伍、伤害与击杀记录。

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/10/20/69d53dbc204a634d511d40c0e2cabb6d.png">
    <img src="https://s1.imagehub.cc/images/2026/10/20/69d53dbc204a634d511d40c0e2cabb6d.png" width="900" alt="个人出刀详情示例：本人会战队伍、伤害及击杀信息">
  </a>
</p>

</details>

<details>
<summary><strong>图6 · Day2 联盟成员出刀总览 · 长图默认折叠｜点击展开 / 收起</strong></summary>

使用 `nk出刀速查 Day2`，查看成员出刀总览、输出前三、击杀前三与未完成名单。

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/10/20/c6214312dc66e19bf15358682e2ab903.png">
    <img src="https://s1.imagehub.cc/images/2026/10/20/c6214312dc66e19bf15358682e2ab903.png" width="900" alt="Day2联盟出刀总览长图：成员出刀情况、输出前三、击杀前三与未完成名单">
  </a>
</p>

</details>

---

## 常见问题（QA）

> 命令中的 `nk` 请替换为当前生效前缀；路径、容器名和 Python 环境以实际部署为准。

<details>
<summary><strong>1. Excel 已经生成，为什么 QQ 收不到文件？</strong></summary>

先查看 AstrBot、NapCat 等 QQ 接入端的文件上传日志。若 AstrBot 运行在宿主机、NapCat 运行在 Docker，而文件以 `file://` 本地路径传递，NapCat 可能因路径不可见报 `ENOENT`。文字或图片正常并不代表文件上传链路正常。

将 AstrBot 实际保存文件的临时目录只读挂载到 NapCat 收到的 URI 对应路径并重建容器即可；若报 `EACCES` 检查读取权限；`retcode 1200` 需结合具体日志判断。

```yaml
services:
  napcat:
    volumes:
      - type: bind
        source: /srv/astrbot-plugin-tmp
        target: /srv/astrbot-plugin-tmp
        read_only: true
```

```bash
docker compose up -d --force-recreate napcat
```

</details>

<details>
<summary><strong>2. 导出提示缺少 XlsxWriter，或装了依赖仍然报错？</strong></summary>

必须在 **GsCore 实际使用的 Python 环境** 执行 `python -m pip install -r plugins/AliceUID/requirements.txt` 并完整重启 Core。Docker 部署需在对应容器内安装；若 `.xlsx` 已成功生成，应排查文件上传链路而非反复装依赖。

</details>

<details>
<summary><strong>3. Playwright 报“浏览器不存在”，或者一直在准备组件？</strong></summary>

插件复用 Core 的 Playwright 并在缺少配套 Chromium 时自动补装（**无需开启 AI**，也不改动 Core 的 Python 包）。首次准备请保持登录页打开，下载失败会冷却 5 分钟。

请检查「自动准备浏览器组件」是否开启以及是否设置了 `GSUID_PLAYWRIGHT_AUTOINSTALL=0`。如需手动修复，在 Core 实际 Python 环境执行：

```bash
python -m playwright --version
python -m playwright install chromium
# Docker 容器示例（缺 Linux 共享库时管理员执行）：
docker exec -u 0 gsuid_core /venv/bin/python -m playwright install --with-deps chromium
```

重建容器可能丢失已下载浏览器，建议将安装加入镜像构建或持久化 `PLAYWRIGHT_BROWSERS_PATH` 目录。

</details>

<details>
<summary><strong>4. 登录链接自己能打开，群友却打不开？</strong></summary>

在 WebUI 将「登录页反代 / 外网地址」填写为外部用户实际可达的域名/端口并确保反代转发 `/nikke/` 路由，不要填入 `localhost` 或内网地址。开启 HTTPS 要求前，先确认证书与 Core 受信代理协议还原已正确配置。

</details>

<details>
<summary><strong>5. 重建容器后，绑定、配置或兑换记录不见了？</strong></summary>

核对挂载的数据目录是否指向原持久化路径，升级或迁移时务必保留绑定数据库、配置及 `data/AliceUID`（特别是 `cdk.sqlite3` 与密钥），切勿通过删库排障。

</details>

<details>
<summary><strong>6. 机器人在线，为什么指令没反应或看不到管理功能？</strong></summary>

检查启动日志是否正常加载 AliceUID、是否保持 `plugins/AliceUID/AliceUID/` 嵌套结构且无重复插件；修改 Core 前缀后须完整重启。管理功能受 Core `masters`、服务范围与黑白名单控制，可用 `nk帮助 文字` 核对当前身份可见指令。

</details>

<details>
<summary><strong>7. 角色卡或 Excel 内容旧，新角色未显示？</strong></summary>

普通查询与导出均优先读本地缓存，先发送 `nk刷新信息`、`nk刷新面板` 或 `nk刷新爱丽丝面板` 同步最新账号资料。若仍提示角色资料缺失，Bot 主可用 `nk数据库更新 状态` 检查公开目录更新。

</details>

<details>
<summary><strong>8. 自动兑换没有执行 / 群友贡献的码上 GameWith 后为何不再通知？</strong></summary>

自动兑换需同时满足：Bot 主开启「允许本人 CDK 兑换」与自动兑换系统总开关、用户个人开关开启且绑定有效。同码跨来源（成员贡献 → 官方 / GameWith）自动去重，仅补充报酬/期限信息，不再重复全员派发；漏领或失败账号可手动 `nk兑换码` 核对。

</details>

<details>
<summary><strong>9. 新一期会战开始了，为什么还没拿到攻略？</strong></summary>

`nk会战攻略` 严格按官方赛季归属校验，不会拿上期攻略冒充本期。若作者尚未发帖或仍在补充组队图，会提示等待并进入冷却，稍后再查即可。

</details>

<details>
<summary><strong>10. 提示登录失效，或转发未收到 / 迟到重复？</strong></summary>

同号更新凭据请用 `nk重新登录`，换号/换服先 `nk解绑`；网络超时、403、429 不等同于 Cookie 失效。转发未收到时请核对 QQ 接入端上传日志与消息回执，可按需调整「转发回执等待秒数」（默认 30 秒，范围 5–300 秒）或关闭单项转发开关。

</details>

---

## 数据安全与鸣谢

- 养成、资源与兑换操作均严格绑定发命令者本人账号，受 Core 权限及四名单保护；请妥善备份 `data/AliceUID`，切勿公开 Cookie、Token、密码或验证码。
- 感谢 [dildoro.com 妮姬伤害计算器·DILDORO](https://dildoro.com/) 提供妮姬伤害模拟与排行编队推荐（结果卡片统一标注联合署名 `Powered By GsCore & Created By AliceUID & dildoro`）。
- 感谢 [GsCore](https://github.com/Genshin-bots/gsuid_core) 提供插件运行与原生卡片渲染框架。NIKKE 相关角色、图像与游戏资料的权利归各权利人所有。

## 反馈与贡献

反馈问题前请由 Bot 主复现后发送 **`nk日志导出5`**（支持 `1~1440` 分钟），获取已脱敏的插件诊断日志并附带插件版本、GsCore 版本与复现步骤提交 [Issue](https://github.com/dddada123/AliceUID/issues)（提交前仍请二次确认无私人信息）。也欢迎通过 [Pull Request](https://github.com/dddada123/AliceUID/pulls) 参与改进；如果觉得插件好用，欢迎点一颗 Star ⭐

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
