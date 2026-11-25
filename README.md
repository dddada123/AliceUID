<p align="center">
  <a href="https://github.com/dddada123/AliceUID">
    <img src="https://raw.githubusercontent.com/dddada123/AliceUID/main/ICON.png" width="240" alt="AliceUID">
  </a>
</p>

<h1 align="center">AliceUID</h1>

<p align="center">
  <strong>适用于 GsCore 的《胜利女神：NIKKE》全能战术数据插件</strong><br>
  个人名片 · 角色练度与图鉴 · 全量导出与等级模拟 · 通用攻略查询 · 官网活动日历 · 联盟会战 · 收菜提醒 · 自动兑换码 · 社区签到 · DILDORO 个人突袭推荐
</p>

<p align="center">
  <a href="https://github.com/Genshin-bots/gsuid_core"><img src="https://img.shields.io/badge/Framework-GsCore-8A2BE2?style=flat-square" alt="Framework: GsCore"></a>
  <a href="https://github.com/dddada123/AliceUID/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License: MIT"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/Version-1.4.01-ff69b4?style=flat-square" alt="Version: 1.4.01"></a>
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

> **当前版本：1.4.01**
>
> - **全新 Bento 视觉体系与亮暗双主题精调**：全面升级 `nk信息`（Bento v3 非对称名片）、横/纵版角色练度卡（支持亮色图标 90% 深灰反色与低扩散白外发光、通透玻璃衬底）及 `nk出刀` 双列「龙傲天 / 活菩萨」榜单；拆分 `nk卡片`（主力妮姬）与 `nk图鉴`（含灰阶未解锁角色）。
> - **Blablalink 通用攻略查询与官网活动日历**：无需登录即可查询 `nk<角色/别名/关键词>攻略`、`nk攻略查询`（支持翻页、默认双气泡 20 条与 120 秒 `nk查询1~20` 点选，与角色歧义/拼写相近候选共用点选路由）、`nk会战攻略` 与高还原 `nk日历`，全面迁移至 GsCore 内置原生渲染引擎。
> - **交互体验与运维能力增强**：统一支持后置 `刷新` 语法（如 `nk信息 刷新`、`nk爱丽丝练度 刷新`、`nk卡片 刷新`）；增强 `nk我的账号` / `nk我的状态` 总览；补全 `爱丽丝风格`（默认）与 `默认说明文` 双文风，支持全局主题随机策略（`纯随机` / `交替` / `昼夜`）；新增 Bot 主 `nk自检` 与 `nk清理缓存`。
> - **稳定三档串行查询与隐私保护**：游戏查询提供高速（1 秒）/ 中速（推荐，默认 2 秒）/ 缓速（5 秒）三档串行速率；`nk日志导出` 自动脱敏发送者身份与敏感凭据。默认指令前缀为 `nk`，可在 Core 插件管理中自定义。

---

## 核心能力

| 模块 | 主要能力 |
|---|---|
| **养成卡片与图鉴** | 横版 / 纵版亮暗角色练度卡（支持横版大立绘缩放微调）、Bento v3 指挥官名片、`nk卡片` 主力妮姬展示与 `nk图鉴` 全量图鉴（含灰阶未解锁）；内置常用别名表，支持本人与公开链接的 **Excel / JSON（schema v3）全量导出**与 **1400 级内任意指定等级模拟**。 |
| **通用攻略与会战攻略** | 无需登录即可查询 Blablalink 角色袖珍指南、单突/联盟战与机制攻略（自动中文翻译、别名/标点模糊匹配、原皮/异格精准区分、带原帖二维码长图与纯文字保序转发），以及自动核对赛季归属的当期会战阵容攻略。 |
| **官网活动日历** | 无需登录即可生成高还原官网活动日历（队员招募、最新时装、版本活动奖励、模拟室双倒计时、竞技场双赛程表），支持亮/暗双主题与默认合并转发。 |
| **联盟会战** | BOSS 血量、出刀总览、Day1 / Day2 切换、成员阵容按伤害排名查询、缺刀与尾刀统计。 |
| **资源与收菜提醒** | 8 类核心资源与前哨保管箱进度卡（90% 警戒刻度 + 满仓时间估算），支持按群聊/私聊独立开启 90%、满仓及睡前收菜提醒与免打扰时段。 |
| **兑换码与自动兑换** | 汇总官方、GameWith 与成员贡献三源并跨源去重；支持手动与自动兑换、新绑定即时补领，单码重复兑换时由爱丽丝贴心提示已兑时间。 |
| **社区任务** | 本人授权手动/自动社区签到、浏览与点赞，支持单群/全群通知控制与签到异常原因归类合并转发。 |
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

3. **配置与重启**：在 Core WebUI 配置外部可访问的登录地址、黑白名单及卡片外观，**完整重启 Core** 后发送 `nk帮助` 验证。首次启动会自动检查公开角色目录并初始化攻略索引。

> **升级注意事项**
> - 请保留 `plugins/AliceUID/AliceUID/` 的嵌套目录结构，切勿只复制内层目录，也不要同时启用多份同名插件。
> - 升级请保留原 `data/AliceUID`、绑定数据库、加密密钥及 `cdk.sqlite3`（保存兑换回执与自动兑换记录）；攻略索引数据库平滑兼容旧版，升级后自动在本地更新规则，无需手动删库。
> - 常规卡片（名片、角色练度、主力卡片、图鉴、资源、会战、帮助）、官网活动日历、会战攻略与通用攻略均默认由 **GsCore 内置原生渲染引擎** 生成；仅网页账密登录与 DILDORO 个人突袭使用 Playwright（插件默认复用 Core 的 Playwright 并自动补齐配套 Chromium；Cookie 导入登录本身不启动浏览器）。
> - 从旧版 NikkeUID 迁移时仅复用公开素材，需在 AliceUID 中重新登录。

---

## 快速开始

支持 **日服、北美服、韩服、国际服、东南亚服**，登录时需显式选服（港澳台网页登录、邮箱验证码登录暂未开放）。

1. 发送 `nk登录日服`（可将 `日服` 替换为目标区服，支持 `登录` / `登陆`），打开本人专属一次性链接。
2. 在网页中使用账号密码完成验证，或直接导入 Cookie 请求头 / `cookies.txt` 文件（输入框默认打码保护）。
3. 登录成功后插件会在后台自动采集完整资料并向原会话发送指挥官名片；随后即可使用 `nk信息`、`nk爱丽丝练度`、`nk卡片`、`nk图鉴`、`nk资源查询` 等指令。

> 凭据失效请发送 `nk重新登录` 更新同区服 Cookie（失败自动保留原绑定）；换号或换服请先 `nk解绑`。无需登录即可直接使用 `nk攻略查询`、`nk<角色>攻略`、`nk会战攻略`、`nk日历`、`nk查询兑换码` 与别名查询。

---

## 常用指令一览

方括号 `[ ]` 表示可选参数，实际输入时无需带括号；更多当前权限可见指令请发送 `nk帮助` 或 `nk帮助 文字`。

### 账号与隐私
| 命令 | 说明 |
|---|---|
| `nk登录日服` | 五区登录（日服 / 国际服 / 北美服 / 韩服 / 东南亚服） |
| `nk重新登录` | 更新原账号同区服 Cookie，失败保留原绑定 |
| `nk我的账号` / `nk我的状态` / `nk解绑` | 查看绑定、缓存与自动化状态总览，或解除当前绑定 |
| `nk妮姬公开` / `nk妮姬隐藏` / `nk妮姬公开状态` | 管理本人官网妮姬资料公开范围与待恢复状态 |
| `nk绑定UID` / `nk我的UID` / `nk解绑UID` | 登记或清理个人分享标识（不能代替登录） |

### 养成、图鉴与导出
| 命令 | 说明 |
|---|---|
| `nk信息` / `nk名片` | Bento v3 指挥官名片与主页展示队伍（第 3 槽位为大立绘） |
| `nk信息刷新` / `nk信息 刷新` | 轻量刷新名片资料（同步支持 `nk刷新信息`） |
| `nk刷新面板` | 全量更新全部角色练度与皮肤缓存 |
| `nk爱丽丝练度` / `nk爱丽丝面板 [刷新]` | 查看指定角色练度卡（歧义或拼写相近时支持 120 秒 `nk查询1~20` 点选） |
| `nk刷新爱丽丝面板` | 仅刷新指定角色练度与对应循环室数据 |
| `nk卡片 [刷新]` / `nk阵容卡片` | 主力妮姬卡片（展示任一技能 ≥ Lv.7 的已持有角色） |
| `nk图鉴 [刷新]` / `nk妮姬图鉴` | 全量角色与皮肤图鉴（含灰阶未解锁妮姬展示） |
| `nk黑莲别名查询` | 查询角色官方名称及已注册别名（无需登录） |
| `nk练度全量导出` / `nk练度全量导出json` | 导出本人实际等级 Excel / JSON |
| `nk400练度全量导出` / `nk1000全量导出JSON` | 导出原始与指定等级模拟对照（支持自定义等级与公开链接组合） |

### 攻略查询（无需登录）
| 命令 | 说明 |
|---|---|
| `nk<角色/别名/关键词>攻略` | 查询角色、单人突袭或机制攻略（如 `nk红莲攻略`、`nk黑莲攻略`、`nk魔方攻略`） |
| `nk攻略查询 [筛选/页码]` | 查看最新攻略并检查新帖（默认双气泡转发 20 篇，支持分类筛选与翻页） |
| `nk查询1` ～ `nk查询20` | 收到攻略列表或角色候选提示后 120 秒内回复编号获取对应结果 |
| `nk会战攻略` / `nk会战阵容` | 转发当前或最近一期联盟战攻略（标题来源、组队原图、完整长图） |

### 联盟会战、资源与个人突袭
| 命令 | 说明 |
|---|---|
| `nk出刀` / `nk查刀` | 联盟会战总览与出刀排行 |
| `nk出刀 Day1` / `nk出刀速查 Day2` | 切换查看 Day1 / Day2 会战阶段 |
| `nk出刀详情 [排名]` | 查本人出刀详情；带数字按本联盟伤害排名查看成员阵容 |
| `nk出刀缺刀` / `nk出刀尾刀` | 未完成出刀名单与尾刀统计 |
| `nk会战血量 [刷新]` | 当前联盟阶段与 BOSS 血量进度 |
| `nk资源查询 [刷新]` | 查看 8 类核心资源与保管箱 90% / 满仓时间估算 |
| `nk开启收菜提醒` / `nk关闭收菜提醒` | 按当前群聊或私聊独立开关 90%、满仓与睡前提醒 |
| `nk收菜提醒状态` / `nk收菜免打扰 00:00-08:00` | 查看本地提醒状态与下次睡前检查时间，或设置免打扰时段 |
| `nk个人突袭推荐 [属性] [亮色/暗色/随机]` | 接入 DILDORO 生成推荐编队（别名 `nk单人突袭推荐`；加 `刷新` 强制重算） |

### 兑换码、社区与活动日历
| 命令 | 说明 |
|---|---|
| `nk日历` / `nk日历 帮助` | 生成官网当期高还原活动日历图（无需登录，默认合并转发） |
| `nk查询兑换码` / `nk兑换码 速查` | 只读查询当前有效兑换码详情或极简清单 |
| `nk兑换码 [兑换码]` | 尝试兑换当前全部或指定兑换码（已由插件兑过将触发爱丽丝专属提醒） |
| `nk增加兑换码ABCDEFG` | 本人核验有效后贡献至共享码池并触发新码派发 |
| `nk自动兑换码` / `nk关闭自动兑换码` | 个人自动兑换开关 |
| `nk签到` / `nk开启全量签到` | 执行本人社区签到，或授权签到+浏览+点赞自动任务 |
| `nk自动社区 状态` / `nk自动社区 关闭` | 查看或停止自动社区任务 |

### Bot 主管理指令
| 命令 | 说明 |
|---|---|
| `nk自检` / `nk清理缓存 [确认]` | 检查插件目录、依赖与缓存健康度，或安全清理可再生衍生缓存 |
| `nk日志导出[数字]` | 导出最近 `1~1440` 分钟脱敏诊断日志 MD（推荐 `nk日志导出5`） |
| `nk攻略重索引 [清空]` | 重新回溯全量攻略索引（默认保留长图缓存；追加 `清空` 则清库重建） |
| `nk数据库更新` / `nk数据库更新 状态` | 手动触发或查看公开角色库与图库维护进度 |
| `nk<角色名>新增别名<别名>` | 添加全局角色别名（如 `nk红莲暗影新增别名黑莲`） |
| `nk注销别名 <别名>` / `nk别名导出` | 屏蔽指定别名（含内置默认别名）或导出当前完整别名表 MD |
| `nk账号列表` / `nk绑定列表` | 查看绑定概览（群内号码自动脱敏，私聊完整显示） |
| `nk群查询 开启/关闭/状态` | 管理本群查询权限及当前状态 |
| `nk群黑名单` / `nk群白名单` / `nk用户黑名单` / `nk用户白名单` | 维护群聊与用户四名单权限控制 |
| `nk刷新兑换码` | 手动刷新官方 / GameWith 公开兑换码库存 |
| `nk启用自动兑换码` / `nk停用自动兑换码` | 自动兑换系统总开关 |
| `nk全群自动兑换码` / `nk全员自动兑换码` | 批量开启本群或全员自动兑换（对应 `nk关闭全群/全员自动兑换码`） |
| `nk签到查询 [页码]` | 查询本群已知账号的当日签到确认状态 |
| `nk签到群通知 开启/关闭/状态` | 管理当前群的签到汇总通知（快捷：`nk开启/关闭签到群通知`） |
| `nk全群签到通知 开启/关闭/状态` | 批量设置全部群通知策略（支持单群后续覆盖） |

---

## 功能详解

### 通用攻略查询与会战攻略
- **多维度精准检索**：无需登录即可查询 Blablalink 已收录作者（首批内置 `在舒恩裡面卍解【Syuen】`）的角色袖珍指南、单人突袭、联盟突袭与魔方/机制专题。支持内置/自定义别名自动映射、跨简繁与中英检索，并忽略全/半角冒号、空格与双词词序。
- **原皮与异格精准区分**：严格区分同名角色原皮与异格（如 `灰姑娘` 与 `灰姑娘：琉璃波光`）。若目标角色暂未收录但存在同系异格攻略，会主动询问是否查看对应异格并附带快捷指令与 120 秒 `nk查询1~20` 编号选择。
- **自动中文翻译与保序转发**：命中外语原帖时自动获取官方中文译文并渲染中文长图（右下角附带原帖直达二维码）；合并转发严格按序发送「标题/作者/原帖与主页链接」→「完整攻略长图」→「纯文字正文（含图片位置标注）」。
- **自动增量更新**：插件启动自动初始化索引，每天北京时间 `04:15` / `14:15` 自动检查新帖；若极少数配图因网络波动未拉取成功，过 60 秒短冷却后再次查询将仅增量补全缺失配图并重绘完整长图。
- **联盟会战攻略**：`nk会战阵容` / `nk会战攻略` 同样无需绑定，自动核对官方赛季归属并依次转发原标题来源、组队示例原图与正文完整长图。

### 养成查询、图鉴与练度导出
- 普通查询与导出默认读取本地缓存；需要最新数据时主动使用 `nk刷新信息`、`nk刷新面板` 或 `nk刷新爱丽丝面板`。
- **`nk卡片` 与 `nk图鉴` 区分**：`nk卡片` 聚焦任一技能 ≥ Lv.7 的主力妮姬并自适应列数；`nk图鉴` 展示全量已持有角色并以灰阶队列补全未解锁角色。
- **全量导出组合语法**：支持 `nk练度全量导出`、`nk练度全量导出json`、`nk400练度全量导出`、`nk400练度全量导出json 链接` 等组合。公开链接支持 Blablalink 主页（`/shiftyspad`）或妮姬列表页 URL（`uid` 与 `openid` 并存时优先 `uid`；无标识链接按本人处理），需发起者已登录对应版本账号且目标公开妮姬资料。
- **数据口径**：Excel 支持爆裂阶段、定位、企业、属性四项联动筛选与「编号升序 / 原始战力降序」切换；JSON 采用 `schema_version=3`，`combat/attack/defense/hp` 始终表示当前实际练度，指定等级结果独立保存于 `simulation` 对象（成长资料覆盖至 1400 级，缺失数据标注原因且不补 0）。

### 官网活动日历、资源与收菜提醒
- **`nk日历`**：直接拉取官网公开日程与官方图文素材，高还原呈现卡池 Banner、时装头像条、活动奖励、模拟室双倒计时与竞技场双赛程表，默认通过合并转发发送。
- **资源与收菜提醒**：`nk资源查询` 仅请求必要双接口并复用 5 分钟成功图片窗口；保管箱进度条按快照占比动态变色（>70% 橙色、>90% / MAX 红色）并标出 90% 提醒刻度线。收菜提醒按群聊/私聊独立订阅，默认北京时间 `00:00–08:00` 免打扰；在免打扰前 1 小时窗口内设置免打扰将即时补检一次睡前提醒；连续两晚 23:00–24:00 均满仓将自动停止提醒。

### 兑换码与自动兑换
- 官方与 GameWith 库存每日 `00:00 / 08:00 / 16:00` 定时更新，仅对跨来源去重后的真正新码或成员新贡献触发全员派发；新绑定用户自动即时核对当前有效码。
- 手动与自动兑换均需 Bot 主在后台开启「允许本人 CDK 兑换」；使用 `nk兑换码ABCDEFG` 命中本地已有兑换记录时，爱丽丝将以专属口吻提示具体的已兑换时间。

### 个人突袭推荐（DILDORO）
- 自动识别网站当前赛季弱点，也可指定 `火/水/风/电/铁`（或全称），各属性缓存独立保留 5 天；重算任务按 FIFO 排队并具备 3 轮总预算与 20 秒无响应静默重试。
- 自动识别并套用网站最新同属性推荐配置；中文翻译异常时自动切换韩语原文继续计算，图片/字体异常支持降级出图。
- 若本人官网妮姬资料处于隐藏/仅盟友/仅好友状态，轮到同步时将自动临时公开并在截图发送后于后台持久化恢复原公开范围（最多 3 条通知，不改动其他隐私项）。

---

## 管理与配置

Bot 主可在 GsCore WebUI 调整以下配置（修改 Core 插件前缀或开启 AI 后需完整重启）：

| 分组 / 配置项 | 关键说明 |
|---|---|
| **游戏查询速度 / 风控策略** | `AliceUID_PanelRiskStrategy`：高速（1 秒）/ 中速（推荐，默认 2 秒）/ 缓速（5 秒），三档均串行；个人突袭、签到、兑换与数据库独立控制。 |
| **登录地址与 HTTPS** | `AliceUID_LoginUrl` 填写外网可访问地址（反代需转发 `/nikke/`）；开启 `LoginRequireHTTPS` 前请确认 Core 正确识别外部 HTTPS 协议。 |
| **登录方式与浏览器** | `AliceUID_LoginMode` 可选 `browser`（账密+Cookie 导入）或 `cookie`（仅导入）；`BrowserAutoInstall` 默认开启自动补装配套 Chromium。 |
| **卡片外观与主题策略** | 全局主题支持 `random` / `dark` / `light`；新增 `AliceUID_ThemeRandomStrategy`（`纯随机` / `交替` / `昼夜`，06:00–18:00 亮色 / 18:00–06:00 暗色）；角色练度支持 `横版/纵版亮暗`、`关闭/横版/纵版/全部随机` 及横版大立绘缩放微调（`-100%`～`+100%`）；支持 `爱丽丝风格` / `默认说明文` 通知文风切换。 |
| **消息转发** | 帮助、图鉴、出刀、会战攻略、通用攻略、活动日历、登录链接、账号列表、签到异常名单与兑换码均可独立开关；NapCat 回执等待默认 30 秒（5–300 秒），未确认自动普通回退一次并暂停该通道转发 60 秒。 |
| **社区与兑换码** | `AliceUID_CommunitySignTime` 默认 `08:33`；`AliceUID_EnableWriteOps` 默认关闭，开启后方可执行 CDK 兑换。 |
| **公开数据库与 AI** | 支持首次启动、招募日历与周五 `02:33` 自动维护公开资料；`AliceUID_AIQueryEnabled` 默认关闭。 |

---

## 效果预览

> **浏览说明**：核心主卡片默认展开，次要主题、高信息密度长图与帮助菜单默认折叠以保持页面清爽。**点击标题或小三角即可展开 / 收起，点击任意图片可查看高清原图**（以下示例均由 `1.4.01` 原生渲染引擎生成，个人昵称与 UID 已做脱敏处理）。

### 1. 角色练度面板（横版 & 纵版 · 亮暗双主题）

使用 `nk角色名练度`（如 `nk爱丽丝练度`，加 `刷新` 可实时同步），完整呈现角色立绘/皮肤、装备超载词条、技能练度、收藏品、魔方与循环室；支持横版与纵版自由切换，以及亮/暗主题与全局随机策略。

<details open>
<summary><strong>横版角色练度卡 · 亮色 &amp; 暗色｜点击展开 / 收起</strong></summary>

<p align="center"><strong>横版亮色（90% 深灰反色图标 + 轻透玻璃衬底）</strong></p>
<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/11/25/243e7149486a1e15ceabaa35480fe3cc.png">
    <img src="https://s1.imagehub.cc/images/2026/11/25/243e7149486a1e15ceabaa35480fe3cc.png" width="900" alt="横版亮色角色练度卡：爱丽丝立绘、装备词条、技能、收藏品、魔方与循环室">
  </a>
</p>

<p align="center"><strong>横版暗色（兔女郎皮肤立绘示例）</strong></p>
<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/11/25/d0556f656cc2ae2ca1ab438b676372ba.png">
    <img src="https://s1.imagehub.cc/images/2026/11/25/d0556f656cc2ae2ca1ab438b676372ba.png" width="900" alt="横版暗色角色练度卡：兔女郎爱丽丝立绘、装备词条、技能、收藏品、魔方与循环室">
  </a>
</p>

</details>

<details open>
<summary><strong>纵版角色练度卡（手机单屏适配）· 亮色 &amp; 暗色｜点击展开 / 收起</strong></summary>

<table>
  <tr>
    <th align="center">纵版亮色（玛丽安：女王皮肤）</th>
    <th align="center">纵版暗色（莉贝雷利奥皮肤）</th>
  </tr>
  <tr>
    <td align="center">
      <a href="https://s1.imagehub.cc/images/2026/11/25/82b5b313dafa9dbaf2aa13c5d914bec0.png">
        <img src="https://s1.imagehub.cc/images/2026/11/25/82b5b313dafa9dbaf2aa13c5d914bec0.png" width="430" alt="纵版亮色角色练度卡：玛丽安女王皮肤、装备词条、技能、收藏品与循环室">
      </a>
    </td>
    <td align="center">
      <a href="https://s1.imagehub.cc/images/2026/11/25/2041c2cb28f5d957521f2137fbe15b40.png">
        <img src="https://s1.imagehub.cc/images/2026/11/25/2041c2cb28f5d957521f2137fbe15b40.png" width="430" alt="纵版暗色角色练度卡：莉贝雷利奥皮肤、装备词条、技能、收藏品与循环室">
      </a>
    </td>
  </tr>
</table>

</details>

---

### 2. 指挥官名片、阵容图鉴与别名查询

使用 `nk信息` / `nk名片` 生成 Bento v3 指挥官名片；使用 `nk卡片` 查看主力妮姬、`nk图鉴` 查看全量图鉴（含灰阶未解锁角色）；使用 `nk<角色>别名查询` 快速确认可用简称。

<details open>
<summary><strong>指挥官信息名片（Bento v3 · 暗色主题）｜点击展开 / 收起</strong></summary>

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/11/25/a0eb6c6866dab1dc664e616490dbda82.png">
    <img src="https://s1.imagehub.cc/images/2026/11/25/a0eb6c6866dab1dc664e616490dbda82.png" width="900" alt="指挥官信息名片暗色主题：主推立绘、核心 KPI、战役与四大企业塔、前哨基地及主页队伍">
  </a>
</p>

</details>

<details>
<summary><strong>指挥官信息名片（Bento v3 · 亮色主题）｜点击展开</strong></summary>

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/11/25/d819fc37efdfd8a12f58f5044426fd56.png">
    <img src="https://s1.imagehub.cc/images/2026/11/25/d819fc37efdfd8a12f58f5044426fd56.png" width="900" alt="指挥官信息名片亮色主题：主推立绘、反色企业塔图标、核心 KPI、前哨基地及主页队伍">
  </a>
</p>

</details>

<details>
<summary><strong>主力妮姬卡片（<code>nk卡片</code> · 任一技能 ≥ Lv.7）｜点击展开</strong></summary>

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/11/25/ac997bf993504ad20ed1326de6beee5a.jpg">
    <img src="https://s1.imagehub.cc/images/2026/11/25/ac997bf993504ad20ed1326de6beee5a.jpg" width="900" alt="主力妮姬卡片：技能大于等于7级主力阵容、同步器等级与星级核心角标">
  </a>
</p>

</details>

<details>
<summary><strong>完整妮姬图鉴（<code>nk图鉴</code> · 含灰阶未解锁展示）｜点击展开</strong></summary>

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/11/25/84ed5d8c071a4e4eebdabf91127b0868.jpg">
    <img src="https://s1.imagehub.cc/images/2026/11/25/84ed5d8c071a4e4eebdabf91127b0868.jpg" width="900" alt="完整妮姬图鉴：全量已持有角色与灰阶未解锁妮姬列表">
  </a>
</p>

</details>

<details>
<summary><strong>角色别名查询卡片（<code>nk黑莲别名查询</code> · 亮色 &amp; 暗色）｜点击展开</strong></summary>

<table>
  <tr>
    <th align="center">亮色主题（红莲：暗影）</th>
    <th align="center">暗色主题（莉贝雷利奥）</th>
  </tr>
  <tr>
    <td align="center">
      <a href="https://s1.imagehub.cc/images/2026/11/25/5825d35c36ab05e44abed765ab064bc1.png">
        <img src="https://s1.imagehub.cc/images/2026/11/25/5825d35c36ab05e44abed765ab064bc1.png" width="430" alt="角色别名卡片亮色主题：红莲暗影可用别名列表">
      </a>
    </td>
    <td align="center">
      <a href="https://s1.imagehub.cc/images/2026/11/25/088eb3e492086485c1f8affdb5d7e9ae.png">
        <img src="https://s1.imagehub.cc/images/2026/11/25/088eb3e492086485c1f8affdb5d7e9ae.png" width="430" alt="角色别名卡片暗色主题：莉贝雷利奥可用别名列表">
      </a>
    </td>
  </tr>
</table>

</details>

---

### 3. 资源查询、联盟会战与个人突袭

<details open>
<summary><strong>资源查询与保管箱收菜估算（<code>nk资源查询</code>）｜点击展开 / 收起</strong></summary>

展示 8 类核心资源、前哨保管箱动态警戒进度条（>70% 橙色、>90% / MAX 红色）及 90% 提醒线与满仓时间预估；主动推送需另行开启 `nk开启收菜提醒`。

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/11/25/f8b36493a103be85473f65ddcfd7ed7b.png">
    <img src="https://s1.imagehub.cc/images/2026/11/25/f8b36493a103be85473f65ddcfd7ed7b.png" width="760" alt="资源查询卡片：8类核心资源、保管箱90%警戒刻度与满仓时间估算">
  </a>
</p>

</details>

<details open>
<summary><strong>联盟突袭 · 个人出刀详情（<code>nk出刀详情</code>）｜点击展开 / 收起</strong></summary>

查看本人或同联盟指定伤害排名成员的会战配队、角色练度角标、单刀伤害与尾刀击杀记录。

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/11/25/e8492d9ea9802636392942ade204afb5.png">
    <img src="https://s1.imagehub.cc/images/2026/11/25/e8492d9ea9802636392942ade204afb5.png" width="900" alt="联盟突袭出刀详情：成员会战队伍、角色头像角标、单刀伤害与尾刀标记">
  </a>
</p>

</details>

<details>
<summary><strong>联盟突袭 · 查刀概览与双列榜单（<code>nk出刀</code> / <code>nk查刀</code>）｜点击展开</strong></summary>

包含左右双列「龙傲天 · 输出前三」与「活菩萨 · 击杀前三」榜单、Day2 出刀速查表、缺刀名单与尾刀统计。

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/11/25/fc2b7a1cc95ffdd4f0539a03a71819c4.png">
    <img src="https://s1.imagehub.cc/images/2026/11/25/fc2b7a1cc95ffdd4f0539a03a71819c4.png" width="900" alt="联盟突袭查刀概览：龙傲天与活菩萨双列榜单、成员出刀速查与缺刀统计">
  </a>
</p>

</details>

<details>
<summary><strong>联盟突袭 · BOSS 血量进度（<code>nk会战血量</code>）｜点击展开</strong></summary>

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/11/25/da6975173ec63e1980a3f22ea914eccd.png">
    <img src="https://s1.imagehub.cc/images/2026/11/25/da6975173ec63e1980a3f22ea914eccd.png" width="820" alt="联盟会战 BOSS 血量卡片：当前阶段、总削减进度与 5 位 BOSS 剩余血量">
  </a>
</p>

</details>

<details open>
<summary><strong>DILDORO 个人突袭配队与伤害模拟（<code>nk个人突袭推荐</code>）｜点击展开 / 收起</strong></summary>

自动识别当前弱点或按指定五属性导入本人养成，生成排行编队推荐与伤害模拟参考。

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/11/25/b123b0fb788248134887aa2eb9eab0ab.png">
    <img src="https://s1.imagehub.cc/images/2026/11/25/b123b0fb788248134887aa2eb9eab0ab.png" width="900" alt="个人突袭推荐卡片：查询弱点、赛季信息与 DILDORO 推荐编队伤害模拟">
  </a>
</p>

</details>

---

### 4. 官网活动日历、社区攻略与帮助菜单（长图默认折叠）

<details>
<summary><strong>官网活动日历 · 亮色主题（<code>nk日历</code> · 无需登录）｜点击展开</strong></summary>

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/11/25/b15e363dc91aa3c83de5aa4240e4778b.png">
    <img src="https://s1.imagehub.cc/images/2026/11/25/b15e363dc91aa3c83de5aa4240e4778b.png" width="860" alt="官网活动日历亮色主题：队员招募、最新时装、版本活动奖励、模拟室倒计时与竞技场赛程">
  </a>
</p>

</details>

<details>
<summary><strong>官网活动日历 · 暗色主题（<code>nk日历</code> · 无需登录）｜点击展开</strong></summary>

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/11/25/a0f572cb5e6d5939c4f4c793a2a24b55.png">
    <img src="https://s1.imagehub.cc/images/2026/11/25/a0f572cb5e6d5939c4f4c793a2a24b55.png" width="860" alt="官网活动日历暗色主题：队员招募、最新时装、版本活动奖励、模拟室倒计时与竞技场赛程">
  </a>
</p>

</details>

<details>
<summary><strong>Blablalink 社区攻略长图（<code>nk&lt;角色&gt;攻略</code> · 含自动中文翻译与原帖二维码）｜点击展开</strong></summary>

<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/11/25/da24e2d4240eeca29e0892553f4b36e8.jpg">
    <img src="https://s1.imagehub.cc/images/2026/11/25/da24e2d4240eeca29e0892553f4b36e8.jpg" width="860" alt="Blablalink 社区攻略长图示例：自动中文翻译、图文排版与原帖直达二维码">
  </a>
</p>

</details>

<details>
<summary><strong>指令帮助菜单 · 普通用户版 &amp; Bot 主完整版（<code>nk帮助</code>）｜点击展开</strong></summary>

<p align="center"><strong>普通用户指令指南</strong></p>
<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/11/25/c8c6829ca0c7a5fcd2cbe8f5e09a7da9.png">
    <img src="https://s1.imagehub.cc/images/2026/11/25/c8c6829ca0c7a5fcd2cbe8f5e09a7da9.png" width="860" alt="帮助菜单普通用户版：三步快速上手与常用指令分组一览">
  </a>
</p>

<p align="center"><strong>Bot 主完整指令指南（含运维自检、攻略重索引与四名单管理）</strong></p>
<p align="center">
  <a href="https://s1.imagehub.cc/images/2026/11/25/e7ed07285f61d25c24856321d9e659bd.png">
    <img src="https://s1.imagehub.cc/images/2026/11/25/e7ed07285f61d25c24856321d9e659bd.png" width="860" alt="帮助菜单 Bot 主完整版：全量用户指令与 Bot 主运维管理指令">
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

常规卡片、活动日历与攻略均已使用 GsCore 原生渲染，**仅网页账密登录与 DILDORO 个人突袭需要 Playwright**。插件默认复用 Core 的 Playwright 并在缺少配套 Chromium 时自动补装（**无需开启 AI**，也不改动 Core 的 Python 包）。首次准备请保持登录页打开，下载失败会冷却 5 分钟。

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

<details>
<summary><strong>11. 通用攻略查不到某角色、或偶尔提示配图缺失怎么办？</strong></summary>

攻略仅检索已收录作者发布的文章；若查询原皮而库内仅有同系异格（如 `灰姑娘` 与 `灰姑娘：琉璃波光`），机器人会主动提示并给出快捷编号。Bot 主可随时发送 `nk攻略重索引` 手动回溯更新索引（追加 `清空` 可彻底重建）。若某次因海外图床波动导致少数配图缺失，60 秒后再次查询会自动仅补下缺失配图并重绘完整长图。

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
