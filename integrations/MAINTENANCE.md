# AliceUID 1.0.08 维护与接手说明

## 1.0.08 当前规则

- candidate3已由用户实机验收：nk卡片、nk帮助、nk出刀均成功。正式1.0.08保留完全相同的发送代码、默认值和节点结构，仅更新文档与发布包。下方“待实机”是历史阶段记录；不要为复测而重新改变已通过的发送链路。

- 最新candidate3取代candidate2安装主线：只更新Core的AliceUID，默认fix1标准标题文字＋完整原图节点，不附外层at，过滤节点内at/at_all。用户再次确认该两节点方式曾实机成功，不能删去标题或否定这份成功证据。
- ForwardReencode新增默认False；默认图像原字节缓存后直通，原尺寸/DPI/格式不变。True才启用既有JPG转换，保留质量95/0–100和旧设置。保留回执与一次普通回退/300秒暂停。额外NapCat配套不作为要求，已安装者要测试标准路线需先禁用并重启NapCat。
- 下面candidate2与编码规则为历史说明，只有显式可选路径才适用。现有标准路线不能保证修复Highway网络超时，须实机验收。

- 最新candidate2：成品图先由outbox.py原子保存并读回校验，再交给Core。64MiB/32份、15分钟有效，后续写入清理过期。缓存只传图，不缓存登录/二维码，不绕过权限或自动重放。
- 原生转发需要单独安装NapCat配套，识别AliceUID帮助/图鉴/出刀标题及单图结构；先准备自身会话的全部节点，才合并发群，不改全局Packet。节点缺失不发仅标题转发，不重试Packet，8秒总预算、单项在途。禁用配套并重启可恢复；普通回退仍一次，迟到合并可能重复。
- candidate1卡片也已实机未通过，不能再以旧卡片成功为当前通路正常的证据。候选包分开保存，进一步验收见handoff；以下完整单图/缓存/权限基础仍适用。
- 用户要求优先复用曾成功的卡片写法：完整单图，不再按高度或体积分页；帮助标题/附注合并为一个文字节点，随后一张完整图。真正透明图保留完整PNG，合规现有JPG字节直通，其他不透明图转指定质量JPG。
- JPG默认95、严格整数0–100，保留完整尺寸、DPI与ICC；完整输出8MiB上限，超出即普通发送原图，不降质量/缩放或丢弃尾部。原渲染器、二维码及普通发送不改。
- 保留实验性标记、四默认开启、已有值、实际适配器身份、权限/绑定锁、一次回退及300秒连接暂停。日志增加实际格式、尺寸、体积、节点数与回执耗时，不保存用户内容或原异常。
- 1.0.07已冻结；新包仅供实机验收。最早失败发生在分页引入前，不能认定分页是唯一根因；历史Highway连接超时也不能靠改图片格式保证消除。

以下为历史规则，当前修正优先。

## 1.0.07 历史规则

- 正式封包状态：四类转发均为实验性功能，后台标识并说明自动回退。用户fix2实测帮助仍未转发成功，300秒暂停正常；不把回退成功冒充转发稳定。进一步发送修复移至独立1.0.08，1.0.07冻结。
- 本节为1.0.07同目录fix2当前规则。按用户最新授权，Help/Roster/Union/Login四转发开关默认True，已有设置保留；不自动部署或推送。
- 移除ForwardUseBotIdentity、身份控制段与NoneBot适配，头像昵称沿用实际NapCat适配器；不修改Core或第三方适配器源码。旧NoneBot实现与测试已可恢复归档。
- 帮助首节点AliceUID帮助；图鉴首节点AliceUID·绑定游戏昵称·图鉴展示；出刀首节点AliceUID·查询公会名-出刀统计。普通消息/错误不附标题。
- 识别WS_BOT_ID=napcat或napcat-*的OneBot通道，要求Core有_recall_waiters且_supports_recall非False，发送时wait_recall=True。成功消息ID列表才算确认；缺失/空回执回退普通内容一次，最长等待由Core控制（参考版本10秒）。旧Core/已锁定不支持直接普通，取消仍传播。
- Core入队不代表平台投递。缺失回执可能是失败、丢失或仍在上传，有限回退可能重复；未确认后暂停该连接转发300秒，后续查询直接普通。其它适配器None/空列表仍不自动重发，不绕过权限/绑定锁、不重新取数或重绘。
- 转发inline图片通过images.py有界处理，不透明图JPG质量默认95，后台整数0–100实时生效，4:4:4；完整按行分页，不缩放。符合限制的现有JPG直通，透明PNG保留，登录二维码和普通回退保留原消息。100仍非无损；源码注释与后台提示不可称其无损或文件压缩比例。
- 实机Highway错误为上传服务器8080连接超时；图像编码处理不等于修复出站网络。不改第三方适配器或Core，具体排查见integrations/README.md。
- 新主题默认random、毛玻璃20%，已有自定义保留，随机只在新渲染选亮暗，缓存不重新抽样；原字体、DPI、签到和短卡片不变。日志只记录阶段/类型/体积，不输出原异常或个人资料。

以下节为历史规则，当前修正优先。

## 1.0.06 当前规则

- F26登录链接发送采用纯node，不在外层at_sender；OneBot私聊与Core全局禁止转发时直接普通发送，防止混合帧拒收或节点被静默丢弃。
- 首次登录/重新登录共用_send_login_link(...,ev=ev)。文本使用明确text段，二维码按开关加入node；失败回退保留同一文本/二维码，不创建新链接。
- 转发异常或显式False仅回退一次，None/空列表不自动重发。普通群消息可at，私聊不at，原发送权限包装保持。CancelledError不转普通消息。
- _make_qr_png与转发回退日志仅记error_type，不能输出异常原文中的登录URL或会话标识。Core内部历史/平台投递不是插件回退成功的证明，实机仍需验收。
- 本版继承1.0.05发布后README徽章、赞助、访问计数、六张预览及折叠：前五默认展开、总览长图收起；资源为预估与查询图内颜色提示，不是主动满仓推送。

以下节为历史规则，当前修正优先。

## 1.0.05 当前规则

- CommunityRequestRange默认5-15，CommunityAccountRange默认10-120。请求起始时刻间隔与上一账号最后响应后的换号等待分别抽样，取较晚可发送时刻；SQLite持久化next_at/last_account/switch_at，保留旧预算和去重。修改范围后重启；原默认15迁为5-15，原非默认固定值迁同值范围。
- Policy范围1～3600秒，后台最多三位小数；长等待自动延长租约。关闭授权、绑定变化和08:00边界仍在每次请求前重新核验；403/429/超时不重试。
- 结果counts只累计本轮确认成功动作，signin_confirmed来自独立签到确认。后续失败不丢签到成功，也不能用整轮completed推断已签到；金币缺失不能补0。
- nikke_commands在配置加载后捕获启动快照，所有SV注册和权限包装结束后重建自定义前缀Trigger，并通知Core候选索引。只替换prefix，复用原func及权限；改设置要完整重启，防止后台保存即改变提示却没改变实际指令。
- 文案在源字符串中插入command_prefix()，不对发送结果做全局替换，用户昵称、账号与URL不被误改；静态REGION_HELP与RELOGIN在启动快照捕获后导入。登录网页通过受限前缀占位符映射。保留nk时提示仍用nk。
- 帮助三个新衬底仅限.help-page作用域；背景图、字体、DPI、模糊强度和其它卡片布局不改变。

以下1.0.04及更早节保留为历史，以当前节为准。

## 1.0.04 当前规则

- CommunitySignTime为HH:MM字符串，默认08:33，后台set_config严格校验并重排Core共享每日cron；失败恢复原配置。数据库周检02:33未改变。
- cycle_day按北京时间08:00划周期；cycle_bjt08_v104迁移只执行一次，保留重叠旧预算/动作，不用last_day推断签到成功。缺少旧时间戳时优先避免重复写。
- signin_confirmations独立记录请求确认/服务器已完成；group_seen记录本群近期使用者。群查询仅Core pm=0，使用当前群范围，本地只读，不加载成员客户端。名单来源是绑定/近30天使用记录，不是实时群全员。
- 登录恢复：NikkeClient将HTTP401和业务401/300001归入NikkeLoginRequired；load_client在缓存之前拒绝本地过期或已知失效版本。cache/auth_invalid仅保存owner/revision摘要和错误码，不含Cookie。新凭据版本不会继承旧失效标记。
- 现有私有查询及自动社区均给出明确重新登录入口；403拒绝、429限流和网络错误不标记为凭据失效。

以下1.0.03及更早节为历史说明，时刻/周期以本节为准。


## 1.0.03 当前规则（优先于历史记录）

- ResourceStatusService.prepare_image持有本人/bot/账号/凭据版本工作锁，执行取数、渲染、图片校验后写入_ready，从成功出图时起算300秒。_cache仅为数据缓存，不能启动成功图片窗口。无ready图时丢弃旧数据快照并重新查询；并发成功只取一次、渲染一次。
- ready图按24MiB总上限淘汰，过期清理；命中不延长时间。主题模式、语言、字体指纹、毛玻璃强度参与复用判断；随机主题命中不重新随机。旧disk资源图片缓存仍由draw保留，但没有ready状态时不以旧数据冒充新查询。
- 取数/渲染失败只设置5秒故障门槛，403/429为60秒；成功图窗口与故障门槛分离。每接口仍用AccountReads保持5秒串行；仅1302127允许一次间隔补读，不认定其官方含义，不自动重试鉴权/限流。
- 查询/渲染在途撤销用epoch阻止旧快照与ready图提交；调用前、生成前后及发送锁内核验绑定和权限。已生成图的发送失败保留图片供重发。重新登录新凭据键不会被旧版无图的5分钟时间戳阻塞。
- 登录on_command增加登陆别名，五区参数与裸命令共享nikke_login_cmd；重新登录/重新登陆已有on_fullmatch继续使用。图文帮助与REGION_HELP明确别名。

## 继承1.0.02行为



- profile/builder提供真实星级、角色元信息与企业塔，resource/service只为首位请求MI，其余SI；不以静态皮肤/缓存存在推定拥有。profile模板720 CSS宽，首位图片contain、18px圆角，指挥官头像88px与UID末行底边对齐。
- card_meta统一SSR/SR/R、grade+core、01～06/MAX与未知降级；metadata投影与素材哈希纳入图鉴指纹。十列图鉴128px头像+32px单层50%透明姓名区，ROW=160/FOOTER=32，197名1400×3560，203名1400×3728；编码与96DPI保持。
- badges.py固定4个已审核URL，期望SHA256，按路径合并并发，复用匿名public_stream和2秒公共节流。磁盘路径仍rolemeta/breakthrough与rolemeta/power。成功origin=community_download；失败origin=reviewed_official_bundled_fallback并持久retry_after。带哈希文件名长期复用，无哈希core固定URL每7天条件校验；旧审核内置元数据及原始字节一致时直接复用并起算本地TTL，不立即重复下载；临时下载失败的fallback在冷却后可恢复下载。
- base_icons资源补全含23个基础图标与4个徽章，数据库断点/剩余数/预算覆盖全部27项。PublicHTTP只扩展4个精确URL，禁止API、附加查询串和片段；无玩家凭据。同步static_badge_source仅返回内置数据URI，不写盘或覆盖来源。
- 帮助图.region使用内容高度、flex横纵居中，.regions整组居中，主题背景alpha=.50；普通用户/Bot主亮暗双引擎验证。
- 插件版本为1.0.02，安装名AliceUID、data/AliceUID和AliceBind不变；不要自动部署。固定哈希地址失效需更新受控清单，运行时不抓JS猜地址。

## 继承1.0.01行为



- 修复休赛期丢弃已取得完整名单的问题：优先赛季快照，没有时使用当前名单对照历史出刀并标来源，保留退出成员的真实记录；0刀本人和未完成名单红字恢复。members_reference随快照保存，不能重启后伪装成赛季名单。
- 当前官方赛季表在每次查询时参与选择（公开表60秒缓存）；当期数据仍按可配置短TTL。仅超过结算期且历史接口成功取到出刀/血量的非空快照可标finalized长期复用；重查本人联盟/名单后复用，跨赛季/区服/联盟不得读旧组；刷新可重取。新赛季空数据不补造0刀。
- glass_settings统一配置AliceUID_GlassStrength，整数0～100、默认10，映射0～80 CSS px背景模糊。通用卡片apply_theme、compact底图都使用同一参数，子模块不再次叠加模糊；前景不滤镜。角色/图鉴/状态缓存包含设置指纹，底图LRU包含强度；在途请求保持起始快照，后续新请求独立键。
- 资源按用户/bot/账号/区服/凭据版本缓存成功图片300秒，成功窗口内含刷新指令均复用图；1.0.03开始失败不再启动5分钟窗口。请求basic→outpost→daily；仅日常1302127允许一次有间隔补查，其含义未由官方资料确认，不无限重试。其他鉴权/限流失败不重试。
- 资源PNG保存在私有cache/resource_images，以owner和快照/风格指纹复用，内存LRU淘汰不强迫重绘。凭据撤销清理图片，在途旧渲染不能再次写回。发送仍检查绑定版本与权限。
- 保管箱按快照容量和24小时周期估算北京时间90%/100%，>70%橙、>90%红、100%MAX；未知不推算。时间是快照估计，不自动领取或操作游戏。
- aliases标签与status阶段标签使用显式flex居中/24px行高及自适应高度。roster保持128×180格和1400px整卡，信息区52px整体居中、头像底色透明；完整197名长图仍3976px CSS高。
- 原DPI/字体/输出编码和公开图库保持，不为降低模型请求体牺牲实际输出质量。图像预览只用于离线构造验收，不等同用户Core实机。

以下为旧版本基线记录；如有旧描述与本节冲突，以本节及本轮交付记录为准。

## 1.0.0 接续

- 休赛期会战走官方历史接口，按赛季选择并显式标记状态，快照回退同赛季隔离；默认180秒共享缓存不变。休赛期长期复用已于1.0.01实现，以上方当前行为为准。
- 新命令与帮助：本人立即签到、全量开启立即执行、北京时间23点周期成功去重；角色别名头像查询；新增/注册别名取代旧写法。GsCore后台绑定管理注册保留脱敏和受控解绑边界。
- 验证码移动参考线以蓝色滑块初始中心加实际位移计算；角色卡署名与UID同行、去掉原底部占位；图鉴顶部玻璃与末行完整保留。
- 血量与资源共用status.html：背景使用cover保持比例铺满实际高度，防止预计背景高度小于排版高度时露出纯色底；draw_status缓存版本alice-v100-status-footer-2。原生/浏览器亮暗、空数据与无限血量均有像素检查。
- 当前保留输出DPI、字体、编码质量及全局0～100%毛玻璃强度（默认10%）；1.0.02按确认方案调整信息卡/图鉴布局尺寸。
- 开发记录和完整结果在独立版本工作区handoff/当前进度_恢复入口.md、v100_scope.md与发布交付记录；安装包不携带开发依赖、预览或真实账号信息。

## 0.6.0 基线

0.6.0为独立更名迭代：保留NikkeUID稳定版，使用新的AliceUID数据目录和AliceBind绑定表，测试用户重新登录，不迁移旧Cookie。新增资源/保管箱、会战血量与爱心好感度；维护细节见 [新状态卡模块](AliceUID/nikke_status/MAINTENANCE.md)。工作区回归入口为 tests_alice/ 和 tools_alice/；旧 tests/ 和 tools/ 保留验证冻结稳定版。

> 先看[用户说明](<README.md>)。源码与开发记录有持续更新，最终发布的测试数、资源数量、压缩包哈希以交付manifest及总体报告为准。未在用户NAS/Docker操作，未发真实邮件/社区互动，未作线上提交。

## 0.5.0 接入点

- compact: 660CSS宽，portraits按完整256×512比例显示并圆角裁剪；总览与四装备等高、内容纵向居中、两列底边一致。超过3种总属性用双列简称，最多6种，装备始终全称。
- T10: Integer/Percent已知函数按百分之一百分比解释，保留原字段。1～11普通、12～14高值、15满值。命中/蓄速按正增益显示，未知ID不得靠猜测填阶。
- 主题: dark/light/random、显示语言zh-CN/zh-TW。照片只位于页面底层；信息/联盟/帮助/阵容子模块只用主题底色，禁止将frost_panel图片拉伸进模块。角色compact使用与固定几何匹配的整幅背景。
- 缓存: cache/panels纯数据+派生PNG；按绑定版本隔离，显式刷新、重新获取资料、解绑清理；图片命中先于随机与昂贵渲染。联盟按同服同联盟共享快照，默认180秒，WebUI可设60/0；缓存访问不顺延原始过期时间。
- 命令: 角色“面板”与“练度”等价；省略符号；pm0角色别名写入character_aliases.json。出刀双榜：总伤害前三、击杀前三（同击杀仅比较尾刀伤害）。
- 验证码: 图像解码和非空内容检查、CSS像素截图、刷新挑战校验、移动缩放重排。真实平台挑战仍可能变化，离线回归不能保证免风控。
- 传输: 私有请求失败不自动重试，不携带Cookie跟随跳转，错误正文不回显；公共资源增量队列与冷却保持。

## 不可破坏的约束

- 保留外壳、`__nest__.py`及内层同名包。资源由 `get_res_path()/AliceUID` 派生，不能硬编码NAS或开发者D盘路径。
- 账号始终 `user_id + bot_id` 归属。用户输入的UID、@对象不决定凭据；不借Bot主Cookie代查。
- 既有绑定不覆盖。保存、公开状态必须核对底层返回码和提交后新查询；解绑显式SQL DELETE，不能恢复使用固定Core存在问题的临时实例 `delete_data()`。
- Cookie只加密落库，密钥与核心数据库须安全备份；密码/邮件码不写文件/日志。异常只记阶段/类型/错误码，不回显数据库参数、HTML、Cookie或SDK正文。
- 相同ID不能同时入同类黑白表；双空允许，白非空先限定再判黑；用户规则对群私、帮助/登录/维护全适用，没有Bot主聊天白豁免。
- 公开资源与实际穿戴分离：静态皮肤清单、URL参数、已缓存文件不能证明玩家拥有。以接口报告服装ID映射，缺图回退标实际来源。

## 模块与接口

| 模块 | 核心接口/注意 |
|---|---|
| `nikke_login` | 账号密码默认/OTP热切换；session身份+generation；`still_current`防旧任务保存；手机取码窗口内不按35秒冻结误杀 |
| `nikke_user` | 单owner绑定锁、Fernet、持久化复查；解绑完成后清session与当前actor衍生卡，不因清缓存失败假报Cookie未删 |
| `nikke_api` | 显式服验证；详情name_code关联；游戏UID=role_id不是gsn；枪种在shot_id.element.weapon_type |
| `nikke_permissions` | ValidatedStringConfig必须首次构造；共享runtime policy；全部SV注册后统一guard，发送时再检查用户 |
| `nikke_profile` | 只用SI ICON，当前皮肤来源一致；缓存与刷新同锁，不在普通查询里每日检查公共库 |
| `nikke_character` | 原始逐条T10保留；总属性Decimal分组汇总；unknown不0；构造预览标明非实际玩家 |
| `nikke_roster` | 十列128px SI，1400宽；只名称/突破/核心；真实所有owned不截断；版本/主题入两次hash |
| `nikke_resource` | 七表+收藏/魔方按需缓存；image resolver返回请求与实际皮肤/hash/missing；内嵌alpha裁剪不改原图 |
| `nikke_database` | 公共队列、基础图标+人物共预算、2秒节流/源拒冷却、周五02:33；import不下载 |
| `nikke_union` | 单命令前缀解析；Day1不缺刀；Day2=day1；成员表补0；无名单未知、超过3不截断；赛季未知明示 |
| `nikke_render` | 主题与布局两轴；原生与浏览器都验；不能只靠不受支持CSS滤镜宣称真磨砂 |
| `nikke_community` | 按账号默认关、签/浏览授权、点赞另开；持久预占/去重/租约，异常停止，不重试不确定写入 |
| `nikke_uid` | 独立SQLite、TEXT ID与namespace；登记不创建空Cookie；解析分享不请求其目标 |
| `nikke_proxy` | 仅预留协议/单固定节点适配；未激活新出口，不宣称每人独立IP |

详细维护资料：

- [邮箱认证状态机](<AliceUID/nikke_login/EMAIL_MAINTENANCE.md>)
- [访问控制与真实Core保存链](<AliceUID/nikke_permissions/MAINTENANCE.md>)
- [数据库队列、预算与接线](<AliceUID/nikke_database/MAINTENANCE.md>)
- [社区授权/持久限频](<AliceUID/nikke_community/MAINTENANCE.md>)
- [UID登记边界](<AliceUID/nikke_uid/MAINTENANCE.md>)
- [联盟数据口径](<AliceUID/nikke_union/MODULE_MAINTENANCE.md>)

## 关键修复与复盘

1. **解绑无响应根因**：固定Core用瞬态对象 `session.delete(cls(...))`，SQLAlchemy拒绝；现用owner谓词DELETE、提交后查空，失败有清晰回复。
2. **假成功**：Core update_data即使0行匹配也可返0，不能只靠返回码。保存/公开/解绑都做新查询复核。
3. **命令前缀**：无参数命令fullmatch；出刀只一个handler解析子参数；练度command/suffix用真实Trigger测试单回复。
4. **缓存竞争**：刷新与抓取锁/epoch配套；绑定版本和发图前身份、权限重新校验；被禁后后台send返回False不续缓存。
5. **皮肤与图类**：信息页误用MI的问题已改SI；不再强制所有当前皮肤回基础。映射依服务器报告，三类分别保实际回退索引。
6. **公开数据schema**：角色小写zh-tw目录203条，大写旧目录仍200但177条；装备源records包装的旧数量须解包再检截断。枪种不在顶层，电击枚举Electronic，不能让合成fixture掩盖。
7. **发布漏模板（重要）**：旧0.2.0构建白名单未含HTML/CSS，实际ZIP没有login/profile模板，合并升级可能残留旧模板。新脚本必含全部模板，解压到空目录校对哈希、Jinja编译，并用旧模板哨兵验证覆盖；禁止再只验py编译就发布。
8. **配置损坏**：已有配置变空对象/null/部分权限键或冲突时拒绝，不重建全允许；合法旧非空配置可迁移。Core批量保存逐项且可能部分成功，不能称事务。
9. **超长分享图**：旧五列MI约17k高已废止；十列SI示例197/203名为3976/4164高，旧图只保历史，不作验收。

## 回归与资源复现

开发工作区依赖隔离在 `.runtime/packages`，需加入PYTHONPATH；不要改系统Python或复制Windows字体到Linux发布包。

```text
python -m pytest tests_alice -q
python tools_alice/check_plugin.py AliceUID
python tools_alice/audit_resources.py
python tools_alice/verify_database_live.py --tasks 3
python tools_alice/complete_public_gallery.py
python tools_alice/preview_character.py
python tools_alice/preview_roster.py --theme dark
python tools_alice/build_release.py
```

公开源码证据在开发工作区 `.references`，固定Core `1ce50ba381e0d9f48dc42385e35a7310dc5ed0f4`，XWUID `4c1727580c613ef3034a391dc3156a1570cd5260`，NKAS `44fede537982ec3ecb14f9300440eda3be67f81a`；原生核心为pytakumi，不可称固定Playwright回退。必要Core方法仅在临时SQLite/AST契约harness执行，不初始化下载的完整Core。

Windows开发预览用本机中文字体和真实公共PNG，但玩家数值均构造；真实邮件、QQ发送、用户容器字体/网络仍须部署验收。唯一Windows符号链接权限skip不通过改系统ACL掩盖；Linux机制另需真实环境验证。

## 发布与升级门槛

- 生产代码升级完整重启Core，后台主题正常读取热变；旧config单例不能靠页面刷新迁成新工厂。
- 备份核心账号数据库与secret.key，不清data解决模板/权限问题。旧策略交叉冲突按明确错误先移出其中一表，不能自动清名单开放。
- 插件包仅源码、模板、必要品牌素材与小体积公共兜底表；资源包只允许公开表和来源/哈希匹配图片。禁止config、secret、UID/社区SQLite、Cookie、私有渲染cache、.runtime/.references及开发临时文件。
- 全新解压验证、源码/包内哈希一致、旧模板覆盖、ZIP CRC、源码编译与最新完整测试均通过后再交付。
- 全库“complete”仅当前公开清单；真实检测到源变化/预算/失败时要准确显示pending，不拿旧表或部分成功冒充全齐。

## 仍不承诺

单人突袭榜、自动续期、跨成员私有练度、历史赛季/分页查刀、多worker登录状态共享或数据库owner唯一约束迁移未实现。当前锁/会话/渲染任务主要单进程；自动社区另有SQLite租约。代理接口没有把浏览器、验证、API全链路变成每用户独立IP，也不保证供应商IP固定。
