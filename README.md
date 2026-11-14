<p align="center">
  <a href="https://github.com/dddada123/AliceUID">
    <img src="https://raw.githubusercontent.com/dddada123/AliceUID/main/ICON.png" width="256" alt="AliceUID">
  </a>
</p>

<h1 align="center">AliceUID</h1>

<p align="center">
  <a href="https://github.com/Genshin-bots/gsuid_core"><img src="https://img.shields.io/badge/Framework-GsCore-8A2BE2?style=flat-square" alt="Framework: GsCore"></a>
  <a href="https://github.com/dddada123/AliceUID/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License: MIT"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/Version-1.2.06-ff69b4?style=flat-square" alt="Version: 1.2.06"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-%E2%89%A53.10-3776AB?style=flat-square&amp;logo=python&amp;logoColor=white" alt="Python: ≥3.10"></a>
  <a href="https://github.com/dddada123/AliceUID/stargazers"><img src="https://img.shields.io/github/stars/dddada123/AliceUID?style=flat-square" alt="GitHub Stars"></a>
</p>

适用于 GsCore 的《胜利女神：NIKKE》插件，支持本人账号绑定、名片与角色练度、皮肤图鉴、会战出刀、资源与收菜提醒、社区签到、兑换码查询与兑换，以及 **DILDORO** 个人突袭编队推荐。

当前版本 **1.2.06**。个人突袭推荐支持翻译异常时自动切换原生语言，以及图片、字体失败时降级出图；降级截图可能包含韩文。默认指令前缀为 `nk`，可在Core插件管理中调整。

[亮点功能](#亮点功能) · [功能说明](#功能说明) · [常见问题（QA）](#常见问题qa) · [效果预览](#效果预览) · [版本记录](CHANGELOG.md) · [开发文档与接口映射](DEVELOPMENT.md) · [问题反馈](https://github.com/dddada123/AliceUID/issues)

<p align="center">
  <img src="https://count.getloli.com/@AliceUID?theme=nixietube-1&amp;padding=7&amp;offset=0&amp;align=top&amp;scale=1&amp;pixelated=1&amp;darkmode=auto" alt="AliceUID 访问计数">
</p>

## 亮点功能

- **养成与导出**：个人名片、角色练度、皮肤图鉴与 Excel / JSON 全量导出，包含原始与模拟战力、攻防生命和基础属性，支持公开链接与原始战力排序。
- **联盟会战**：BOSS血量、出刀排行、成员阵容、缺刀和尾刀统计，以及带作者来源的阵容攻略。
- **资源与提醒**：查看资源和保管箱，预估满仓时间，按需开启收菜提醒。
- **兑换码**：汇总官方、GameWith和成员贡献，支持本人兑换、新码自动处理与跨来源去重。
- **社区与日历**：手动签到、授权自动社区任务，查看官网活动日历。
- **个人突袭**：接入 DILDORO，按本人养成生成编队推荐与模拟伤害卡片。

## 功能说明

### 养成查询与刷新

名片展示指挥官资料，角色面板展示技能、装备词条、魔方、收藏品与好感；图鉴展示本人持有的角色和皮肤。普通查询复用缓存，需要最新数据时主动刷新。

`nk刷新信息` 更新名片，`nk刷新面板` 更新全部角色练度与皮肤，`nk刷新爱丽丝面板` 只更新指定角色。`nk练度全量导出` 导出实际等级Excel，`nk练度全量导出json`（或 `JSON`）导出实际等级JSON，包含攻击、防御和生命；Excel支持爆裂阶段、定位、企业和属性筛选，以及编号/原始战力排序。角色面板可在后台选择宽窄、亮暗主题，或设置随机样式。

### 练度全量导出

默认按当前实际等级导出。升级后首次本人导出会识别旧缓存，并自动完整刷新一次；刷新失败时停止导出，后续可用 `nk刷新面板` 重试。需要最新资料时也可主动刷新；`nk刷新爱丽丝面板` 也会更新该角色属性及相关回收室数据。角色卡片不必显示攻防生命，文件仍包含这些数据。

| 命令 | 内容 |
| --- | --- |
| `nk练度全量导出` | 实际等级，Excel |
| `nk练度全量导出json` / `nk练度全量导出JSON` | 实际等级，JSON，便于AI分析 |
| `nk练度全量导出 链接` | 指定公开用户，Excel |
| `nk练度全量导出json 链接` | 指定公开用户，实际等级JSON |
| `nk400练度全量导出` | 本人原始与400级模拟对照，Excel |
| `nk1000全量导出JSON` | 本人原始与1000级模拟对照，JSON |
| `nk400练度全量导出json 链接` | 指定公开用户，原始与400级模拟对照 |

“链接”替换成 Blablalink 主页（`/shiftyspad`）或妮姬列表页完整URL，可紧接命令或加空格。支持仅openid、仅uid、uid与openid并存的本人或他人链接；两者不同时按官网规则优先使用uid。不带用户标识的练度页链接按本人当前绑定账号处理。链接导出需要发起者本人已登录对应国际版或港澳台版账号，且目标用户公开妮姬资料；链接导出开始拉取前会提示等待；权限受限时会说明可获取内容及缺失影响。盟友／好友可见资料按查询者实际访问权限读取，回收室不可访问时攻防生命标注缺失。目标无需绑定Bot或预先刷新插件缓存；目标区服由链接用户档案确定。目标档案缺少展示UID，但区服和资料归属明确时仍可导出，UID标为“未提供”。目标未公开回收室时，仍可导出其他练度，攻防生命明确标注缺少依赖。

导出战力为角色原始服务器战力，攻防生命按实际等级计算。Excel总览上方可切换“编号升序 / 原始战力降序”，与四项筛选共同生效；明细可通过列头独立排序。新增基础暴击率、暴击伤害倍率及武器基础参数，这些基础值不代表叠加技能、装备词条后的实战属性。未知、隐藏数据注明原因，JSON数值为null，不当作0。

`nk刷新面板` 会更新角色原始详情、词条和可获取的基础属性，并保留完整公开角色资料；旧卡片继续兼容旧缓存，无需删除数据。 后台“全量面板采集风控策略”默认保守（30人/批、2秒间隔），可选激进（30人/批、1秒间隔）。首次登录、手动面板刷新及本人导出需要的全量采集共用此策略；独立刷新信息和签到CD保持各自设置。基础属性可用而攻防生命缺少回收室依赖时，仍保留已知基础值。

指定等级导出已开放，可将400替换为成长资料覆盖的其他等级，支持Excel、json/JSON与公开链接组合。文件同时保留实际等级、原始服务器战力和原始攻防生命，并单列模拟等级、模拟战力及模拟攻防生命；只改变等级，其余配置保持当前。当前随包成长资料覆盖至1400级，不外推或截断；个别资料缺失时注明原因，所有角色都没有目标等级资料时停止模拟导出。模拟为面板估算，已核验样本最大相差3点，验收容差10点；不代表实战伤害。

JSON采用schema_version=3，保留原有characters字段名称（attack、defense、hp等）及字段字典。raw_character_data补充原始角色详情和当前等级公开属性；state_effects和equipment_metadata为共享数组，effect_refs、cube_ref、favorite_ref使用0基索引引用。重复词条和装备资料只保存一次，属性元数据不重复保存同一组数值。完整多等级成长资料保留在本地公开资料缓存，不逐角色重复塞进练度文件。现有combat、attack、defense、hp始终表示原始练度；指定等级结果在独立simulation对象中，包含level、combat、attack、defense、hp、status和reason，simulation_complete表示模拟是否完整。

新角色实装后，先执行 `nk刷新面板` 更新本人持有列表；新角色公开基础与成长资料按需获取，无需逐角色升级插件。资料尚未公开或暂时下载失败时保留已知原始练度、标明计算缺失，冷却后再次导出可补齐缺少的公开依赖。普通导出继续复用缓存；已取得更新持有列表时会识别新增角色并补齐。

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

网络暂时异常时，每个请求最多3轮尝试；每轮连续20秒无响应便静默重试，持续无响应约1分钟后仅向发起者返回一次最终错误。不同用户分别回复，没有群聊共享冷却；同一用户请求未结束时，重复命令不再刷“正在计算”。有真实响应或计算进度时继续等待，登录失效、权限/验证码、限流或配置冲突不会自动重试。


`nk个人突袭推荐` 将本人养成资料导入 [DILDORO](https://dildoro.com/)，自动按网站赛季识别弱点生成本人区服的推荐队伍与模拟伤害。有可用缓存时直接返回；需要网站重算时全局按先后排队，等待者会收到排队提示。

官网妮姬资料为隐藏、仅盟友或仅好友时，实际轮到同步才会临时设为所有人可见；会先通知，查询可能较慢。截图完成立即返回，并在同条结果说明后台将恢复原公开范围，不等待隐私关闭。受限账号最多3条通知：处理/排队、临时公开、结果；原本公开账号维持处理/排队与结果两步，缓存命中直接返回。推荐失败也会安排恢复；恢复未确认时可查询状态或到官网处理，不另外刷屏。其他名片、前哨基地、资源权限不自动开启；第三方已导入的数据不会因恢复隐藏而删除。

| 官网妮姬隐私命令 | 作用 |
|---|---|
| `nk妮姬公开` | 将本人官网妮姬资料设为所有人可见，持续生效 |
| `nk妮姬隐藏` | 隐藏本人官网妮姬资料，持续生效 |
| `nk妮姬公开状态` | 查看官网实际公开范围及待恢复状态 |


可指定 `火／水／风／电／铁`，也支持完整名称 `燃烧／水冷／风压／电击／铁甲`；`nk单人突袭推荐` 是同义指令。例如 `nk个人突袭推荐火`、`nk单人突袭推荐铁甲`。不填属性自动跟随网站赛季。

默认和五种属性分别保存结果，最长保留5天。默认查询每次先检查最新赛季，再决定是否使用缓存；发现新赛季、对应排行或网站推荐设置变化后，重新导入本人公开养成并计算。手动属性的排行检查间隔为活动期1小时、休赛期6小时，由查询触发。

本人养成变化后使用 `nk个人突袭推荐火刷新` 或 `nk单人突袭推荐刷新`，强制重新导入对应结果；兼容刷新前置写法，末尾可加 `亮色／暗色／随机`。每次网站重算都在独立环境填写本人链接、同步养成，识别并套用同属性最新推荐设置（支持属性简称、繁简体及日期格式变化），再依次选择“排行玩家编队”、本人区服并执行；养成拉取失败或网站报告的采集时间过旧时停止计算。未读取到推荐配置或没有导入入口时继续默认配置模拟，卡片顶部会注明；已有配置却套用失败或属性/日期冲突时停止。

卡片顶部显示指挥官头像、五属性图标、网站赛季和阵容参考赛季；三栏均配各自属性图标，跨赛季分别显示。两期不一致时醒目提醒，并建议在本期活动第3天下午之后再查询或刷新；此建议不保证届时一定更新。手动指定属性可能使用历史同属性排行，不能当作本期实战阵容。主动刷新失败直接提示，自动更新失败若展示旧结果会明确标注；赛季预检失败不把旧缓存当成本期结果。网站未报告养成采集时间时卡内会说明，无法保证上游隐藏缓存的新鲜度。功能仍为实验性，模拟伤害仅供参考。

### 可选AI查询

配合Core AI，启用插件「允许AI调用只读查询」并完整重启后，可用自然语言查询本人资料、角色练度、别名和帮助。默认关闭，不开放登录、兑换或社区操作。

## 安装与升级

AliceUID依赖GsCore，不能独立运行；需要Python ≥3.10。

1. 备份原插件及运行数据，将**完整安装ZIP**解压到GsCore的 `plugins/` 父目录，覆盖同名文件。图片、背景和字体已包含，无需另下素材包。
2. 使用GsCore实际运行的Python安装依赖：

```bash
python -m pip install -r plugins/AliceUID/requirements.txt
```

3. 在WebUI配置用户可访问的登录地址、名单和主题，完整重启Core，再发送 `nk帮助`。首次启动会自动更新角色列表。

保留 `plugins/AliceUID/AliceUID/` 的嵌套结构，不要只复制内层包。升级保留 `data/AliceUID`、绑定和配置，尤其是保存领取回执的 `cdk.sqlite3`；不要同时启用多份插件。

网页登录、会战攻略、官网日历和DILDORO需要浏览器。插件复用Core的Playwright，默认自动补齐缺少的配套Chromium，与AI开关无关，不更新Core的Python包。首次准备可能需要下载；异常处理见下方QA。Cookie导入登录本身无需启动服务端浏览器。

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
| `nk日志导出[数字]` | 仅Bot主：导出最近指定分钟的插件日志MD，如 `nk日志导出5`、`nk日志导出10` |
| `nk帮助` / `nk帮助 文字` | 查看帮助，文字版可复制 |
| `nk登录日服` | 五区登录；日服可替换为国际服/北美服/韩服/东南亚服 |
| `nk重新登录` | 更新原账号同区服 Cookie，失败保留原绑定 |
| `nk我的账号` / `nk解绑` | 查看或解除登录绑定 |
| `nk信息` / `nk名片` | 本人个人资料与展示队伍；第三槽位角色作为大立绘，其余四人按摆放顺序从左到右展示 |
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
| `nk个人突袭推荐 [亮色/暗色/随机]` | 先检查最新赛季，未变化时复用五天缓存 |
| `nk个人突袭推荐刷新 [亮色/暗色/随机]` | 重新导入养成数据并计算推荐 |
| `nk日历` / `nk日历 帮助` | 官网当前默认活动日历及范围说明 |
| `nk黑莲别名查询` | 查询角色本名及已注册别名 |
| `nk兑换码` / `nk查询兑换码` | 兑换本人当前码，或只读查询清单与详情 |
| `nk自动兑换码` / `nk关闭自动兑换码` | 个人自动兑换开关 |
| `nk绑定UID` / `nk我的UID` / `nk解绑UID` | 登记或清理分享标识 |
| `nk练度全量导出` / `nk练度全量导出json` | 导出本人实际等级Excel / JSON；可组合等级和公开链接 |
| `nk会战阵容` / `nk会战攻略` | 当前或最近一期对应攻略 |

## 转发设置

登录链接、帮助、图鉴、出刀和会战攻略等可分别设置转发开关。转发图片默认保留原图，可选转为JPG；新编码质量默认95，会战攻略长截图沿用该质量设置。

NapCat转发回执默认等待30秒，可设5～300秒。发送未确认时普通回退一次，并暂停该连接转发60秒；迟到回执仍可能造成重复。OneBot私聊及不支持转发的连接使用普通消息。

## 管理与配置

Bot主在WebUI调整配置，普通用户只显示有权使用的指令。修改Core插件前缀或启用AI后须完整重启；默认前缀为 `nk`。

| 设置 | 必要说明 |
|---|---|
| 登录地址 | `AliceUID_LoginUrl` 填写用户可访问的地址；反代需转发 `/nikke/` 路由 |
| 浏览器组件 | `AliceUID_BrowserAutoInstall` 默认开启；`BrowserChannel` 可选auto、chromium或msedge |
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

## 常见问题（QA）

适用于AliceUID 1.1.24。命令中的 `nk` 请替换为当前前缀；路径、容器名和Python环境以实际部署为准。

### 1. Excel已经生成，为什么QQ收不到文件？

先查看AstrBot、NapCat等QQ接入端的文件上传日志。若AstrBot运行在宿主机、NapCat运行在Docker，而文件以 `file://` 本地路径传递，NapCat可能因路径不可见报 `ENOENT`。文字或图片正常，也不代表文件上传链路正常。

将AstrBot实际保存文件的临时目录只读挂载到NapCat收到的URI所对应的路径，应用配置重建NapCat后重试。已有用户通过此方式解决。若报 `EACCES`，检查容器运行用户的读取权限；若文件已被清理，则先排查临时文件保留时间。`retcode 1200`需结合具体日志判断，不能单凭错误码确定原因。

<details>
<summary>Linux / Docker Compose挂载示例</summary>

假设接入端传递 `file:///srv/astrbot-plugin-tmp/example.xlsx`，文件也确实位于宿主机该目录，可将下面的挂载合并到现有NapCat服务配置。这里的目录和服务名均为示例，必须替换为实际值。

```yaml
services:
  napcat:
    volumes:
      - type: bind
        source: /srv/astrbot-plugin-tmp
        target: /srv/astrbot-plugin-tmp
        read_only: true
```

应用配置后重建该服务，例如：

```bash
docker compose up -d --force-recreate napcat
```

确认NapCat容器内能按收到的路径读取文件，再重新导出。只改挂载名称、未应用新配置，或挂到了另一个容器，都不能解决路径问题。Windows宿主机、远程Docker或双容器部署需按实际路径映射调整，不能机械照抄此示例。

</details>

### 2. 导出提示缺少XlsxWriter，或装了依赖仍然报错？

在**GsCore实际使用的Python环境**执行 `python -m pip install -r plugins/AliceUID/requirements.txt`，完成后重启Core。若Core运行在Docker中，应在对应容器环境安装；装在宿主机或另一个Python环境中不会替它补齐依赖。

如果xlsx已经成功生成，应继续检查文件上传链路，而不是反复安装导出组件。

### 3. Playwright报“浏览器不存在”，或者一直在准备组件？

`Executable doesn't exist at ...chromium_headless_shell-...` 表示Playwright找不到配套浏览器文件。1.1.24默认复用Core已安装的Playwright，并在组件缺失时自动下载对应Chromium；**无需开启AI**，也不会升级或降级Core的Playwright包。

首次运行或Core更新后，请保持登录页面打开。若提示组件仍在准备，稍后在原页面重试；下载完成不等于账号已绑定。原链接过期后重新获取链接。下载失败会冷却5分钟，反复提交账号不会加快下载。

先检查「自动准备浏览器组件」是否开启，以及是否设置了 `GSUID_PLAYWRIGHT_AUTOINSTALL=0`。显式选择 `msedge` 时需自行安装Edge，也可将通道改为 `auto` 或 `chromium`。若提示缺少Playwright Python包，先在Core实际使用的Python环境安装插件requirements，再完整重启Core。

<details>
<summary>手动修复、Docker路径与下载问题</summary>

在**运行Core的同一个Python环境**执行：

```bash
python -m playwright --version
python -m playwright install chromium
```

Docker默认部署示例（容器名和解释器路径按实际部署替换）：

```bash
docker exec gsuid_core /venv/bin/python -m playwright --version
docker exec gsuid_core /venv/bin/python -m playwright install chromium
```

安装时沿用Core的 `PLAYWRIGHT_BROWSERS_PATH`。报错查找 `/ms-playwright` 时，不能把浏览器装到宿主机或另一个用户的默认缓存后就认为已修复。目录不可写、只读挂载或磁盘不足，需先修正对应问题。

如果报缺少Linux共享库，可由管理员在对应容器里执行系统依赖安装。默认Docker解释器示例：

```bash
docker exec -u 0 gsuid_core /venv/bin/python -m playwright install --with-deps chromium
```

自动补装不会执行apt或提权安装系统包。下载超时、证书或代理报错时，检查容器本身的网络和Playwright下载源；「浏览器代理」仅用于登录访问，不会自动配置安装器下载代理。不要通过反复升级Playwright或随意指定旧版浏览器文件来解决。

容器重启通常保留已下载组件，**删除并重建容器可能丢失**。可把匹配浏览器的安装加入镜像构建，或持久化实际浏览器目录并保持环境变量和权限一致；只持久化 `/venv` 不包含浏览器文件。

浏览器恢复后，重新尝试原来的登录或截图。Cookie导入登录可不启动浏览器，但日历、攻略截图和DILDORO仍需要浏览器。账号、验证码或网站访问失败不会触发重新下载。

</details>

### 4. 登录链接自己能打开，群友却打不开？

在WebUI将「登录页反代 / 外网地址」填写为用户实际能访问的地址，检查域名、端口和 `/nikke/` 路由。不要把 `localhost`、容器名或仅服务器可达的内部地址直接发给外部用户。

使用HTTPS反代时，还需确认证书、代理协议传递和Core受信代理配置一致；插件「登录页面要求HTTPS」开关不会自动生成证书或配置反向代理。

### 5. 重建容器后，绑定、配置或兑换记录怎么不见了？

先核对是否启动了另一套实例，或把数据挂载到了错误目录，再检查备份。Core实际使用的数据目录应持久化；升级保留原绑定数据库、配置及 `data/AliceUID`，尤其是 `cdk.sqlite3` 中的领取与派发记录。

不要通过删除数据库来修复这类问题。应让当前实例重新使用原数据目录，或从确认过的备份恢复。

### 6. 机器人在线，为什么插件指令没反应或看不到管理功能？

先查看启动日志是否成功加载AliceUID，并确认只启用一份插件；安装包应保留 `plugins/AliceUID/AliceUID/` 的嵌套结构。修改Core插件前缀后须完整重启，再用生效的前缀发送帮助指令。

若普通功能可用但管理项缺失，检查Core的 `masters`、服务范围和黑白名单。群内允许查询不等于拥有Bot主管理权限，可用 `nk帮助 文字` 核对当前身份可用的指令。

### 7. 角色卡或Excel内容旧，新角色没有显示？

普通查询和Excel导出会读取本地缓存。先用 `nk刷新信息` 更新名片、`nk刷新面板` 更新全部角色练度与皮肤，或用 `nk刷新爱丽丝面板` 更新指定角色，再查询或导出。

如果仍提示角色资料缺失，Bot主可检查 `nk数据库更新 状态`。导出成功不代表它已经重新同步了全部账号数据。

### 8. 自动兑换没有执行，需要检查哪些设置？

确认Bot主已开启「允许本人CDK兑换」、自动兑换系统总开关，且该用户的个人自动兑换开启、绑定有效、权限允许。个人可用 `nk自动兑换码` / `nk关闭自动兑换码` 调整，系统总开关由Bot主管理。

1.1.23在官方/GameWith库存更新后或成员成功贡献新码时触发自动兑换，新绑定成功后仅立即核对该用户，不再每分钟扫描。Bot主可用 `nk刷新兑换码` 更新公开库存；没有真正新码时不会重新发起全员任务。

### 9. 群友贡献过的兑换码又出现在GameWith，为什么不再通知？

这是正常的跨来源去重。同一码只因来源变化不会再次触发全员自动兑换，后来的来源可补充报酬等信息；只有真正新增码才派发并通知。

新绑定用户仍会单独核对已有有效码。某用户上一轮失败，可使用 `nk兑换码` 手动核对，不需要等待另一来源再次收录。

### 10. 新一期会战已经开始，为什么还没拿到攻略？

`nk会战攻略` / `nk会战阵容` 在查询时检查官方赛季并寻找本期完整帖子。若作者尚未发布或仍在补充组队示例，会提示可能还在编写；按提示等待冷却结束后再次查询。

官方赛季表尚未更新、网络错误或截图失败也会影响查询，应按具体提示处理。跨月或同月多期会校验赛季归属，不能拿上期攻略代替本期。

### 11. 提示登录失效，重新登录却一直失败？

使用 `nk重新登录` 更新原账号、原区服的凭据；需要换账号或换区服时先 `nk解绑`，再重新绑定。Cookie导入后仍会核验账号与区服，请确认导出的是自己的有效登录凭据。

网络超时、403、429等错误应分别检查网络或访问限制，不应全部当作Cookie失效反复登录。不要把Cookie、密码或验证码发到群里排查。

### 12. 转发显示已发送，但没收到，或者隔一会儿重复出现？

先查看QQ接入端的实际错误及消息ID回执。Core已提交消息不一定等于QQ最终上传成功；上传较慢时，原转发可能在普通回退后才送达，造成迟到重复。

可临时关闭对应功能的转发开关比较，或调整「转发回执等待秒数」（默认30秒，可设5～300秒）。若是文件消息报路径错误，应按第一条检查路径和权限，延长等待时间不能修复文件不可见。

---

仍未解决时，请提供插件、Core和QQ接入端版本，说明各组件在宿主机还是容器内，并附触发命令、发生时间和脱敏报错。文件路径中的用户名、账号及文件名也请脱敏，不要提交Cookie、Token或完整私人练度文件。

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

请先在 GsCore 中设置好 Bot 主账号。由 Bot 主发送 **`nk日志导出5`（推荐值，最近5分钟）**，即可导出插件诊断日志，用于提交 Issue 排查问题。分钟数支持1～1440；应先复现问题再导出。日志会脱敏身份和凭据，提交前仍请检查是否包含私人信息。

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
