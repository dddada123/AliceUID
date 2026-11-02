<p align="center">
  <a href="https://github.com/dddada123/AliceUID">
    <img src="https://raw.githubusercontent.com/dddada123/AliceUID/main/ICON.png" width="256" alt="AliceUID">
  </a>
</p>

<h1 align="center">AliceUID</h1>

<p align="center">
  <a href="https://github.com/Genshin-bots/gsuid_core"><img src="https://img.shields.io/badge/Framework-GsCore-8A2BE2?style=flat-square" alt="Framework: GsCore"></a>
  <a href="https://github.com/dddada123/AliceUID/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License: MIT"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/Version-1.1.23-ff69b4?style=flat-square" alt="Version: 1.1.23"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-%E2%89%A53.10-3776AB?style=flat-square&amp;logo=python&amp;logoColor=white" alt="Python: ≥3.10"></a>
  <a href="https://github.com/dddada123/AliceUID/stargazers"><img src="https://img.shields.io/github/stars/dddada123/AliceUID?style=flat-square" alt="GitHub Stars"></a>
</p>

适用于 GsCore 的《胜利女神：NIKKE》插件，支持本人账号绑定、名片与角色练度、皮肤图鉴、会战出刀、资源与收菜提醒、社区签到、兑换码查询与兑换，以及 **DILDORO** 个人突袭编队推荐。

当前版本 **1.1.23**。默认指令前缀为 `nk`，可在Core插件管理中调整。

[亮点功能](#亮点功能) · [功能说明](#功能说明) · [效果预览](#效果预览) · [版本记录](CHANGELOG.md) · [开发文档与接口映射](DEVELOPMENT.md) · [问题反馈](https://github.com/dddada123/AliceUID/issues)

<p align="center">
  <img src="https://count.getloli.com/@AliceUID?theme=nixietube-1&amp;padding=7&amp;offset=0&amp;align=top&amp;scale=1&amp;pixelated=1&amp;darkmode=auto" alt="AliceUID 访问计数">
</p>

## 亮点功能

- **养成与导出**：个人名片、角色练度、皮肤图鉴与 Excel 全量导出，支持多条件筛选。
- **联盟会战**：BOSS血量、出刀排行、成员阵容、缺刀和尾刀统计，以及带作者来源的阵容攻略。
- **资源与提醒**：查看资源和保管箱，预估满仓时间，按需开启收菜提醒。
- **兑换码**：汇总官方、GameWith和成员贡献，支持本人兑换、新码自动处理与跨来源去重。
- **社区与日历**：手动签到、授权自动社区任务，查看官网活动日历。
- **个人突袭**：接入 DILDORO，按本人养成生成编队推荐与模拟伤害卡片。

## 功能说明

### 养成查询与刷新

名片展示指挥官资料，角色面板展示技能、装备词条、魔方、收藏品与好感；图鉴展示本人持有的角色和皮肤。普通查询复用缓存，需要最新数据时主动刷新。

`nk刷新信息` 更新名片，`nk刷新面板` 更新全部角色练度与皮肤，`nk刷新爱丽丝面板` 只更新指定角色。`nk练度全量导出` 导出Excel，支持爆裂阶段、定位、企业和属性筛选。角色面板可在后台选择宽窄、亮暗主题，或设置随机样式。

### 联盟会战与攻略

`nk出刀` / `nk查刀` 查看联盟总览，`nk会战血量` 查看BOSS进度；`nk出刀详情` 查本人，追加伤害排名可查看本联盟对应成员阵容。支持Day1/Day2、缺刀和尾刀查询，休赛期可查看上期记录。

`nk会战阵容` / `nk会战攻略` 转发指定作者的标题与来源、组队示例图和正文长截图。休赛期无缓存时拉取最近一期对应攻略，新赛季首次查询自动换期；尚未发布时提示等待作者更新。

### 资源与收菜提醒

`nk资源查询` 查看资源、保管箱和预计满仓时间。`nk开启收菜提醒` 接收90%、满仓及睡前提醒，`nk关闭收菜提醒` 关闭。群聊和私聊独立设置，默认北京时间00:00～08:00免打扰。

### 兑换码与自动兑换

`nk查询兑换码` 只读查看清单，`nk兑换码` 为本人尝试领取，`nk增加兑换码ABCDE` 核验并贡献共享码。期限优先参考官方，实际领取以官方结果为准。

官方/GameWith库存每天00:00、08:00、16:00更新，真正新码或成员新贡献触发自动兑换；同一码跨来源不重复派发，通知列出来源和新增码。新绑定只立即核对该用户，已领取项自动跳过。

手动和自动兑换均需Bot主开启「允许本人CDK兑换」；自动兑换还需系统与个人开关允许。个人用 `nk自动兑换码` / `nk关闭自动兑换码` 调整，Bot主可批量设置，见[管理与配置](#管理与配置)。

### 社区任务与日历

`nk签到` 执行本人签到，`nk开启全量签到` 授权签到、浏览和点赞。自动社区任务默认关闭，授权后默认每天北京时间08:33执行，可在后台调整。`nk自动社区 状态` 查看状态，`nk自动社区 关闭` 停止任务。

`nk日历` 发送官网当前活动日历截图，暂不支持指定历史月份或区服。

### 个人突袭推荐

`nk个人突袭推荐` 将本人养成资料导入 [DILDORO](https://dildoro.com/)，返回推荐队伍与模拟伤害。需公开Blablalink个人档案和妮姬列表；结果缓存5天，养成变化后使用 `nk个人突袭推荐刷新`。该功能为实验性，模拟结果仅供参考。

### 可选AI查询

配合Core AI，启用插件「允许AI调用只读查询」并完整重启后，可用自然语言查询本人资料、角色练度、别名和帮助。默认关闭，不开放登录、兑换或社区操作。

## 安装与升级

AliceUID依赖GsCore，不能独立运行；需要Python ≥3.10。

1. 备份原插件及运行数据，将**完整安装ZIP**解压到GsCore的 `plugins/` 父目录，覆盖同名文件。图片、背景和字体已包含，无需另下素材包。
2. 使用GsCore实际运行的Python安装依赖：

```bash
python -m pip install -r plugins/AliceUID/requirements.txt
python -m playwright install chromium
```

3. 在WebUI配置用户可访问的登录地址、名单和主题，完整重启Core，再发送 `nk帮助`。首次启动会自动更新角色列表。

保留 `plugins/AliceUID/AliceUID/` 的嵌套结构，不要只复制内层包。升级保留 `data/AliceUID`、绑定和配置，尤其是保存领取回执的 `cdk.sqlite3`；不要同时启用多份插件。

网页登录、会战攻略长截图、官网日历和DILDORO需要Playwright浏览器。升级Playwright后需重装匹配的Chromium；Docker环境须在运行容器内安装，缺少系统依赖时可用 `python -m playwright install --with-deps chromium`。Cookie导入登录本身无需启动服务端浏览器。

从旧NikkeUID迁移时，仅复用公开素材，用户需在AliceUID重新登录。

## 快速开始

支持日服、北美服、韩服、国际服、东南亚服，登录时明确选服；港澳台网页登录、邮箱验证码登录暂未开放。

1. 发送 `nk登录日服`（可替换区服），打开本人登录链接。
2. 使用账号密码，或导入Cookie请求头、cookies.txt文件完成验证。Cookie输入默认打码。
3. 发送 `nk信息`、`nk爱丽丝练度` 或 `nk卡片` 开始查询。

`登录` / `登陆` 均可使用。凭据失效用 `nk重新登录`；换号或换服先 `nk解绑`。

## 常用命令

方括号表示可选参数，使用时不输入方括号。更多指令见 `nk帮助` / `nk帮助 文字`；UID登记只保存标识，不能代替登录。

| 命令 | 用途 |
|---|---|
| `nk帮助` / `nk帮助 文字` | 查看帮助，文字版可复制 |
| `nk登录日服` | 五区登录；日服可替换为国际服/北美服/韩服/东南亚服 |
| `nk重新登录` | 更新原账号同区服 Cookie，失败保留原绑定 |
| `nk我的账号` / `nk解绑` | 查看或解除登录绑定 |
| `nk信息` / `nk名片` | 本人个人资料与展示队伍 |
| `nk信息刷新` / `nk刷新信息` | 更新名片资料 |
| `nk刷新面板` | 更新全部角色练度与皮肤 |
| `nk爱丽丝练度` / `nk爱丽丝面板` | 查询指定角色练度 |
| `nk刷新爱丽丝面板` | 更新指定角色练度 |
| `nk卡片` | 完整已持有角色图鉴 |
| `nk出刀` / `nk查刀` | 联盟总览与排行 |
| `nk出刀 Day1` / `nk出刀速查 Day2` | 选择会战阶段 |
| `nk出刀详情 [排名]` | 不带数字查本人，带数字按本工会伤害排名查成员阵容 |
| `nk出刀缺刀` / `nk出刀尾刀` | 未完成名单与尾刀统计 |
| `nk会战血量 [刷新]` | 联盟阶段及 BOSS 血量 |
| `nk资源查询 [刷新]` | 本人资源与保管箱状态 |
| `nk开启收菜提醒` / `nk关闭收菜提醒` | 当前群聊或私聊的本人收菜提醒开关 |
| `nk收菜提醒状态` / `nk收菜免打扰 00:00-08:00` | 本地状态与当前会话免打扰时段 |
| `nk个人突袭推荐 [亮色/暗色/随机]` | 查看本人编队推荐，优先复用五天缓存 |
| `nk个人突袭推荐刷新 [亮色/暗色/随机]` | 重新导入养成数据并计算推荐 |
| `nk日历` / `nk日历 帮助` | 官网当前默认活动日历及范围说明 |
| `nk黑莲别名查询` | 查询角色本名及已注册别名 |
| `nk兑换码` / `nk查询兑换码` | 兑换本人当前码，或只读查询清单与详情 |
| `nk自动兑换码` / `nk关闭自动兑换码` | 个人自动兑换开关 |
| `nk绑定UID` / `nk我的UID` / `nk解绑UID` | 登记或清理分享标识 |
| `nk练度全量导出` | 导出本人练度Excel |
| `nk会战阵容` / `nk会战攻略` | 当前或最近一期对应攻略 |

## 转发设置

登录链接、帮助、图鉴、出刀和会战攻略等可分别设置转发开关。转发图片默认保留原图，可选转为JPG；新编码质量默认95，会战攻略长截图沿用该质量设置。

NapCat转发回执默认等待30秒，可设5～300秒。发送未确认时普通回退一次，并暂停该连接转发60秒；迟到回执仍可能造成重复。OneBot私聊及不支持转发的连接使用普通消息。

## 管理与配置

Bot主在WebUI调整配置，普通用户只显示有权使用的指令。修改Core插件前缀或启用AI后须完整重启；默认前缀为 `nk`。

| 设置 | 必要说明 |
|---|---|
| 登录地址 | `AliceUID_LoginUrl` 填写用户可访问的地址；反代需转发 `/nikke/` 路由 |
| 登录方式 | `AliceUID_LoginMode` 可选网页账号密码或Cookie导入，也可设置仅Cookie导入 |
| HTTPS | 使用HTTPS反代时，确认Core正确识别外部协议后再开启插件HTTPS要求 |
| 卡片外观 | 全局主题、语言、字体可调；角色面板和个人突袭推荐有独立主题设置 |
| 转发图片 | `AliceUID_ForwardReencode` 默认关闭；`AliceUID_ForwardJpegQuality` 默认95 |
| 转发等待 | `AliceUID_ForwardReceiptSeconds` 默认30秒，保存后下次发送生效 |
| 兑换写操作 | `AliceUID_EnableWriteOps` 默认关闭，手动和自动兑换均需Bot主开启 |
| 自动兑换 | `AliceUID_AutoCDKEnabled` 默认开启，停用不会修改个人开关 |
| 社区任务 | 需本人授权，默认08:33执行；点赞可独立关闭 |
| AI查询 | `AliceUID_AIQueryEnabled` 默认关闭，需配合Core AI使用 |

角色资料支持启动、日历和周检自动更新；Bot主可用 `nk数据库更新` 手动更新，`nk数据库更新 状态` 查看进度。

| Bot主指令 | 用途 |
|---|---|
| `nk账号列表` / `nk绑定列表` | 绑定概览，群内号码脱敏，私聊显示完整号码 |
| `nk刷新兑换码` | 更新官方/GameWith库存 |
| `nk启用自动兑换码` / `nk停用自动兑换码` | 系统总开关 |
| `nk全群自动兑换码` / `nk关闭全群自动兑换码` | 设置当前群绑定用户的个人开关 |
| `nk全员自动兑换码` / `nk关闭全员自动兑换码` | 设置全部绑定用户的个人开关 |
| `nk签到查询 [页码]` | 本群已知账号的签到记录 |
| `nk签到群通知 开启/关闭/状态` | 当前群的签到通知 |
| `nk开启签到群通知` / `nk关闭签到群通知` | 当前群通知快捷开关 |
| `nk全群签到通知 开启/关闭/状态` | 批量设置全部群，之后可单群覆盖 |

## 数据与使用范围

养成、资源与兑换操作使用发命令者本人的绑定账号；会战详情可按本联盟伤害排名查看成员阵容。查询、自动任务与通知均受Core权限及插件名单控制。

请备份 `data/AliceUID`，不要公开Cookie、Token、密码和验证码。实现与历史细节见 [开发文档](DEVELOPMENT.md)、[版本记录](CHANGELOG.md)。

## 排查入口

| 问题 | 处理 |
|---|---|
| 浏览器不存在或版本不匹配 | 在GsCore运行环境重装Chromium，Docker须在容器内执行 |
| 绑定或登录失效 | `nk重新登录`，并确认区服一致 |
| 查询缺少新角色 | `nk刷新面板`；Bot主可查看数据库更新状态 |
| 自动兑换没有执行 | 检查兑换写开关、系统开关、个人开关与权限 |
| 看不到管理指令 | 核对Core的masters和当前身份，使用 `nk帮助 文字` |
| 转发未送达或重复 | 调整转发开关与等待时间，见[转发设置](#转发设置) |

## 效果预览

**点击每张图片上方的标题或小三角，即可展开或收起图片。** 前五组默认展开，可按需折叠；Day2出刀总览较长，默认折叠。点击图片可查看高清原图。

以下为功能展示示例，具体数据以实际查询为准；命令采用默认 `nk` 前缀。

<details open>
<summary><strong>图1 · 妮姬练度查询｜点击展开 / 收起</strong></summary>

使用 `nk角色名练度`，例如 `nk爱丽丝练度`，查看本人角色的装备、技能与养成详情。

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

使用 `nk信息` 或 `nk名片`，以横版名片展示指挥官资料、主页队伍、角色立绘、战役爬塔和前哨数据。

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/10/29/ad94378a318bc927b3302e2d86e2b15d.png">
    <img src="https://s1.imagehub.cc/images/2026/10/29/ad94378a318bc927b3302e2d86e2b15d.png" width="900" alt="横版指挥官信息名片：指挥官资料、角色立绘、主页队伍、战役爬塔与前哨数据">
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

`Powered By GsCore & Created By AliceUID & dildoro`

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
