# AliceUID 开发文档

适用版本：**1.1.10**。本文依据本目录实际源码编写，涵盖插件生命周期、模块与命令、客户端及HTTP接口、字段和资源映射、缓存与权限，以及测试发布流程。社区端点是当前适配代码使用的协议，不代表上游提供永久稳定的接口承诺。

### 1.1.10 横版信息卡（当前实现）

nk信息/名片唯一生产布局为1228×720，原竖版profile.html已替换，无竖版切换入口。profile_wide.css提供左右玻璃分区，保留1张大立绘+4小头像；身份、部队战斗力、五项养成指标、战役与爬塔、前哨资料密排。职业与属性使用官方图标，独立Alpha阴影保持原图清晰。

nikke_profile.presentation.prepare_profile_art在成品图缓存未命中后准备资源，优先当前皮肤full，缺失回退对应MI/SI，禁止用另一皮肤full冒充；full/MI传统定位沿用隔离进程和素材哈希缓存。类型、当前皮肤、头像、数值均沿用本人资料。头像保持方形显示，信息卡尺寸72px，沿用1.1.08用户头像/立绘角色头像回退策略。依赖跟踪含准备后的full，旧720px成品因模板、CSS和painter指纹变化自然重绘；正式渲染root_width=1228、PNG/DPI不变。

亮色不透明度70%、暗色74%，覆盖角色横版练度卡主信息底板以及信息卡右侧各主面板和左下角色说明区。GLASS配置键、默认20和已有值保留，WebUI标题/描述明确仅对竖版/窄版毛玻璃生效；新版横版信息卡、横版练度卡不使用该模糊强度，没有新增调节项。历史段落与当前实现冲突时以本节为准。

### 1.1.09 宽版总属性三行占位

wide布局visible_rows至少3行，工具区顶部固定按三行计算。aggregate-rows最小高度84px、双列grid-auto-rows=28px；四类词条额外插入一个跨两列、带顶部分割线的空白展示行，不参与统计。0～6类词条均按三行占位，原数值、总阶、排序不变。缓存版本alice-v1109-three-row-summary-1。

nk信息的横版重构已在1.1.10完成。

### 1.1.08 跨卡片头像与署名

cached_profile将当前绑定的profile快照与commander.json头像补齐记录按checked_at选择最新有效icon，核验game_id、area_id和已知UID；只合并返回值的icon，不改写旧快照或资料核对时间。信息卡context中的commander_icon_id随合并结果变化，自然使旧成品图失效，角色查询也可读取后续名片刷新得到的新icon。图片仍共用prepare_commander/ImageCache，未增加全量刷新或额外账号请求。

prepare_profile优先采用至少128×128的指挥官SI（官方常用尺寸），缺失/尺寸不足时使用top_nikke[0]的SI，即大立绘对应角色；都不可用才显示占位。avatar_source区分commander/lead/placeholder，标题注明来源，保留88×88、18px圆角的原方形头像。原图与头像缓存不改写。

glass_finish.css和profile.html署名text-shadow全部为none，20种卡片/主题组合检查computed style。立绘和装备原有光效保留。

### 1.1.07 署名、日期与圆圈装饰

brand_credit.html统一Powered By GsCore & Created By AliceUID；solo.html附加dildoro保留、双空格移除。共享glass_finish.css及独立profile模板为其他卡片使用1px/3px白色text-shadow；练度卡.frame>.brand-credit及日期片段明确text-shadow:none。宽版署名以右侧信息面板中心x=862px对齐，位于卡片底778px到图片底810px的间隔中心y=794px；窄版以右侧面板中心x=496px对齐，位于932px到982px间隔中心y=957px。采用独立底部容器flex居中，margin清零，避免共享署名margin使位置偏上。

生成时间按北京时间格式化为YYYY-MM-DD·HH:MM，通过credit_timestamp附加到署名末尾；明确时区输入先转UTC+8，缺少时区沿用既有北京时间语义，异常输入回退当前北京时间。宽窄版时间均作为brand-credit内的credit-timestamp行内片段，整行居右侧卡片下方居中；署名与日期整行统一theme.muted：day #35475D、night #BDCCE0；日期片段color:inherit。不再有循环室下方、工具面板下方或旧footer日期DOM。角色缓存版本alice-v1107-footer-rings-5。宽版wide-tool-value改为透明背景、1px技能圆圈同色边线、theme.muted标签同色文本；line-height17px加上下边框保持总高19px、宽80px，不改变行布局。

宽版收藏品/魔方/循环室增加48px细线圆圈，窄版已有工具布局补充34px/52px圆圈。暗色收藏品与魔方的ring-frost层inset=4px、20%白色，局部backdrop-filter=blur(3px)，外圈和内层之间保留背景间隔，图标独立在上层。原生引擎以透明白色内层呈现，浏览器额外支持背景采样柔化；前景图标不参与模糊。暗色宽版立绘单独Alpha白色外光，60%强度、3px局部柔化，无偏移；其他主题保留原黑色局部阴影，原图/头部定位/放大尺寸不改写。

验证包括四主题双引擎压缩预览、署名中心和完整文案、日期格式/颜色/署名行内合并及无溢出、内层尺寸与20%白色、原图无transform以及全部图片完整加载。

### 1.1.06 图标效果与头像按需修复

nikke_render/icon_effects.py 仅从图标Alpha派生独立阴影PNG，icon_url前景不改写、不预合成。模板icon-stack内前景使用原尺寸原Data URI，阴影层绝对定位150%并保留透明边距，不使用transform，也不触发整图二次采样。普通图标亮色为70%黑色局部投影、暗色#10397B柔光；T10 Lv5使用加深#C80C60，外层4.5%原图短边柔化、90%强度，内层1.8%/80%。只有阴影模糊，源图纹理不参与模糊。

立绘同样独立原图前景与黑色阴影层：65%不透明度、3 CSS px柔化、右2/下3px偏移，透明边距15px；根据既有立绘显示尺寸换算源图坐标，不修改立绘像素、头部定位或放大尺度。缺少有效PNG或明确布局尺寸时省略阴影。宽窄亮暗共用，生产字体、144DPI与PNG编码流程保持。

WEBUI配置在CONFIG_DEFAULT中按功能重排，LoginUrl首项；Core reconcile_config按默认模板顺序输出并保留用户data。仅更新反代地址标题提示，不新增配置键、不覆盖用户配置。

角色查询在没有可用saved.icon时，通过既有账号串行请求门控单独调用get_saved_role_info，成功写入账号隔离commander.json，不更新面板明细或全量完成标记；同一绑定重启后复用。临时失败沿用300秒内存冷却，登录失效继续提示重登。prepare_commander按官方avatar map解析真实SI，缺图走ImageCache按需下载和持久冷却，不返回其他皮肤代替；图像准备完成后才进入渲染。成品缓存版本alice-v1106-sharp-icons-art-shadow-5。

### 1.1.05 练度卡主题与数据来源

`AliceUID_CharacterCardStyle` 为 compact_light/compact_dark/wide_light/wide_dark，默认wide_light；旧compact/classic等不在新选项时回退默认，其他卡片全局主题不受影响。`AliceUID_CharacterRandomTheme` 为off/wide/compact/all，默认off。成品图片键包含固定模式、随机策略、模板/字体/DPI/素材依赖；命中先返回PNG，仅未命中时解析一次具体布局和亮暗色。

窄版头部使用独立compact_header宏，左列标题/核心突破/类型、右列战斗力/指挥官，普通flex文档流各自纵向居中；块间gap=10CSS像素，避免绝对定位导致间隔不均。宽版1228×810 CSS，窄版660×982 CSS；实际像素随原有RenderDpi，默认144（1.5倍）。生产render.py保持父版字节不变：image_format=png，原字体及外置/原生回退保留。开发preview脚本先以144DPI在内存渲染，再仅将缩小、高压缩JPG保存到handoff；这些参数不进入生产渲染。

头像：GetSavedRoleInfo的data.icon保留到角色资料，以`character_avatar_map.json`中id查resource_id/costume_index，SI为`/character/si/si_c{rid:03d}_{skin:02d}_s.png`。未知映射/重复映射/缺图/基础皮肤回退不能冒充用户头像，使用文字占位。访客主页Tools/GetUserSavedRoleInfo使用base64解码后的uid，但匿名实测返回300001；预览头像为明确构造的官方素材选择，不声称取得了用户真实头像。接口及证据详见工作区handoff。

循环室等级来自本人GetUserProfileOutpostInfo的outpost_info.recycle_room_researches列表，tid/lv。职业Attacker/Defender/Supporter分别1101/1102/1103；Elysion/Missilis/Tetra/Pilgrim/Abnormal分别1201～1205。沿用官网QueryKeys映射，按当前角色职业/企业选两条及官方类型图标；缺失、隐藏值-9999、异常/重复记录显示未知，已报告0保留Lv.0。复用当前绑定最新profile快照，不额外请求循环室接口。

本人列表costume_id优先，缺失时同角色详情costume_tid回退；静态costumes.id→costume_index→resource_id，full缓存`characters/full/c{rid:03d}_{skin:02d}.png`。不从公开皮肤清单推断拥有关系。缺少对应full时优先同皮肤MI/SI并说明，保留既有基础回退。源素材不物理裁剪；内存嵌入沿用既有alpha透明边修整。CSS的立绘层overflow:visible/z-index:1，衬底2，文本3；顶部约50px，底部及画布自然裁出。

特征匹配：只在宽版准备，当前皮肤full和MI均准确时执行；MI顶部60%与FULL顶部60%使用SIFT+RANSAC，FULL识别边长上限896、最多1600特征，估计头部锚点，横向居中；MI中央70%上半部透明轮廓估计头部上沿，经同一变换映射回FULL，明显顶部道具占位超过80CSS像素才纵向平移，将头部上沿定位到约50CSS像素；小幅差异保留角饰等头部配件；无法估计轮廓时将头部锚点限制到上方180CSS像素内，不改变放大比例。单线程短命工作进程、最长12秒，主进程后台线程等待；一个进程级锁限制并发为1。以源文件哈希及算法版本将结果写resource/rolemeta/framing，正常和低置信度结果复用；环境失败回退并冷却600秒。无模型、GPU、AI服务、凭证或网络依赖。Windows两样本冷次约0.5～0.6秒，子进程峰值约137～149MiB，结束即释放；缓存读取约2ms。并非NAS实测。

两版总属性共用summary_display：按攻击/优越/装弹/蓄速/暴击/暴伤优先排序，展示至多六项；超过三项用短名双列，总阶及完整aggregate不截断。宽版亮色/暗色只从各自day/night池选背景，背景等比cover，不模糊；窄版继续使用玻璃强度设置。

### 1.1.04 登录与签到通知

登录通知不再以 failed 为终点：每个 generation 最多发送一次失败提醒，沿用 sessions.get 的链接有效期与处理中宽限；成功后发送一次回执并退出，删除/替换/过期会话自然退出。通知发送异常仅记录异常类型，不使后续成功失去监听，也不自动重发不确定回执。普通绑定、重新登录及网页 Cookie 兜底共享监听，私聊 Cookie 导入也显示帮助与全量签到引导。

签到 messages 的默认输出保留文本兼容；structured=True 时仅对未确认签到成功且存在有效 QQ ID 的页返回 {text, mentions}。分页同时保存对应 mentions，notify_batches 的 JSON 存储兼容旧字符串页；发送层通过 MessageSegment.at 生成真实提醒，校验 ASCII 数字、长度和去重，不解析昵称/原因中的文本为 @。已成功签到而后续任务暂停不会误提醒 Cookie 过期。保留群权限、精确 Bot 路由、发送前预约及不确定回执不重发策略。

### 1.1.03 满词条外观与资源读取重试

character_base.html仅为line.max增加1px透明边界、双层背景（黑色padding-box+主题渐变border-box）和外发光，亮色使用加深红色，暗色金色。compact满词条padding由4px补偿为3px，保持原28px行高与文字位置。cube-tool及内部tool-icon透明，阴影仅通过PNG的filter:drop-shadow产生，技能与收藏品样式保留。角色render_version升级为alice-v1103-max-affix-glow-1，旧PNG自然失效，正式字体/DPI与素材不变。

ResourceStatusService.query对一次查询总计最多三次尝试：1302127、HTTP5xx、httpx.TransportError及TimeoutError/ConnectionError可静默重试；每次走AccountReads.transaction的五秒节流，成功端点在本轮复用，失败端点续查，不是每端点各三次。NikkeLoginRequired、401/300001立即退出并要求登录，403/429保留拒绝/限流含义，不循环请求。结构/渲染错误不伪装为网络故障。

prepare_image将still_current传入query，每轮以及每次请求前核验绑定epoch和当前权限；中途撤销停止后续请求。三次临时故障抛出StatusRetryExhausted，用户只收到最终网络提示，不含1302127或缓存内部信息；失败冷却独立于成功图片窗口。Cookie失败在短冷却内仍抛登录异常，不改成一般故障。并发请求继续复用取数/渲染工作锁，成功出图后300秒固定窗口及提醒观测回调不变。

CHANGELOG将1.1.02与1.1.03合并到当前1.1.03条目，父版原文与ZIP保持。离线预览使用已有公开素材、1.5倍DPI，亮暗两主题×浏览器/原生两引擎完整图和局部图集中handoff/max_affix_preview；无外部HTTP或真实账号请求。

### 1.1.02 单体出图、静默全量同步与账号列表

普通/手动角色查询若缓存缺少目标name_code，优先get_character_details([code])。唯一匹配的有效详情确认持有；只合并目标角色行，缺少的列表字段保持未知，等级可从详情lv取得。空详情才读取列表以区分未持有与暂缺详情；异常不返回未持有。单体缓存complete=False并设置full_refresh_pending，返回context._needs_full_refresh；发送成功后调度schedule_silent_refresh，同绑定复用既有任务，手动刷新可加入并取得正常回执。自动worker的bot=None，成功或失败都不发QQ。

角色命令以foreground_view覆盖查询、渲染和发送，不等待wait_for_refresh。全量任务改用独立_refresh_locks串行，_RefreshReads每个端点分别申请AccountReads.transaction(background=True)，不在网络期间持有角色账号锁。前台网络请求计数使下一后台请求让位，取消等待会释放优先标记；原五秒间隔与全局并发上限保留。后台发布通过background_publish等待活动卡片结束，短暂取得角色/绑定锁后再提交；绑定版本、权限、失效状态和显式缓存撤销计数仍检查。

snapshot schema=1兼容，新增可选row_checked_at、full_refresh_pending；profile.json另记roster_checked_at，避免以基本资料完成时间冒充角色列表核对时间。latest_roster将较新单角色行叠加到最近完整列表；后台提交比较列表时间、每行时间及详情时间，保留期间前台取得的新数据，再计算complete。失败保留原快照与已保存的单体详情，不渲染全量角色图。

账号列表权限仍为Core Bot主或插件主账号。按(user_id,bot_id)统计绑定账号，群来源字段按下划线拆分并在相同适配器内去重；私聊/来源未知绑定计入账号总数。统计为绑定来源记录覆盖，非Bot实际加入群数；保留既有get_all_binds查询范围。群内数字QQ长度>4时显示前2位+****+后2位，其余标识完全掩码；昵称中的长数字也脱敏以免绕过。列表稳定排序、每页20账号、每批最多40页，跨页/批连续编号，超过9999自然扩展；第一节点总览，不列任何群明细。私聊保留完整QQ。

AliceUID_AccountListForward默认True，沿用标准转发与既有回执/回退策略；_AccountListDelivery逐次核验管理员权限，普通回退逐页发送同一份预处理文本。账号凭据不参与列表数据。

### 1.1.01 持有状态核实

CharacterQueryService.query 在有效缓存缺少目标角色时至多补一次 get_characters；冷读取和 refresh=True 已有本次列表，不再补请求。拥有则仅获取目标详情，无全量预取。完整社区列表的成功核实结果在进程内复用五秒，超出后再次核实；手动刷新仍遵守原五秒限流。

持有列表在账号锁内获取、绑定锁内校验并原子写回，先于详情请求提交，因此详情失败不会丢失持有核实结果。重复/无效列表不写回；网络/登录错误保持独立错误类型。列表变化使旧查询context失效，发送前继续核验绑定、权限与epoch。单角色手动更新继续保留其它角色行，不把部分合并列表当成完整社区核实证据。

snapshot.json新增可选roster_checked_at；旧schema=1可继续读取，缺省回退profile_checked_at/saved_at。PanelCache.latest_roster比较它与profile.json.checked_at，cached_profile仅覆盖较旧的chars，保留基本信息核对时间。其它角色details及checked_at保留，新确认角色强制丢弃孤立旧详情；complete只有原快照完整且详情覆盖持有列表时才保留，自动补查不宣称全量刷新。

验证使用离线API替身、真实缓存落盘与虚拟限流时钟。1.1.0全目录哈希冻结；未执行真实社区登录/查询或QQ发送。

### 1.1.0 里程碑封包与帮助关联排序

本版仅重排nikke_help.draw.build_help_context中的既有条目，完全按用户确认的预览实施。普通版41条、Bot主版61条；原命令文本、说明、模块划分及权限不变。section_bands与help.html沿用：超过7条的模块通栏、内部逐行左→右，短模块保持单列。查询与刷新同列相邻，信息在左首行、轻量刷新在左次行；角色面板及其刷新在右首/次行。

帮助CACHE_VERSION升级为1.1.0:associated-command-order-1，原30天缓存因内容/版本变化自然失效，无需手动删缓存。文字版同步采用相同条目顺序；命令注册、服务接口、字体/模板/DPI和图片质量均未改变。该里程碑继承下述1.0.27完整行为，不将离线验收描述为线上部署或QQ实测。

### 1.0.27 名片轻量刷新与成品图复用

本版将原始数据新鲜度、图片内容版本、并发发布epoch、磁盘清理期限分开。普通信息读取cached_profile，接受独立profile.json或既有完整snapshot中的有效资料，不要求全角色details齐备。ensure_profile(refresh=True)仅调用名片所需的basic/outpost/characters/saved/player五类读取，不请求character_details；同一绑定的轻量请求共用锁、失败冷却及原账号读取节流。两条精确命令“信息刷新”“刷新信息”共用该入口，全量“刷新面板”继续queue_refresh。

轻量profile.json只写当前已核验绑定的数据，不伪装成完整角色快照。登录预取仍先取资料再分批取详情；冷启动可在第一阶段拿到资料后出名片。完整snapshot的profile_checked_at记录资料实际核对时刻，saved_at仅代表整个快照发布；晚到的全量任务不能凭更晚的saved_at盖过更新的轻量资料。完整详情失败仍保留原完整快照；新取得且已核验的轻量资料可独立使用。

nikke_render/cache.py管理信息、别名、出刀图片。每个身份/视图槽仅指向一个当前PNG，图片hash命名后先写图片再原子发布元数据；成功后清理旧图。信息/出刀图片最多7天，别名30天，时长只控制派生文件，不驱动游戏账号刷新。同槽同内容任务共用shield保护的在途渲染；返回和发布前检查本人绑定/权限/版本。解绑或重登清除对应私有槽。

resource.cache.track_assets用上下文收集该图实际读取的公开PNG（包括缺图路径），命中只stat相应依赖及少量静态表，不重新解码/转Base64/准备全部头像。新补齐缺图、替换头像或皮肤会使相应图失效；无关PNG和只更新ETag/304侧车不会导致重绘。没有依赖记录的旧缓存安全地准备一次以建立依赖。阵容图仍保持1400宽、固定96DPI、完整JPEG质量/尺寸校验及成功发送后7天滑动清理。

样式指纹包含模板/CSS、绘图源版本、实际字体指纹、语言、玻璃、主题和实际DPI。角色图片内容摘要排除_panel_epoch、_snapshot_saved_at等内部发布元信息，但这些字段仍用于迟到结果保护；单角色详情另记录checked_at供消息说明。缓存PNG保留原生成/快照时间，消息报告最新资料核对时刻。出刀数据仍先过180秒缓存/赛季/本人联盟校验，图片缓存不能延长数据有效期。资源样式变化可以重画已有有效数据，但不能顺延原300秒窗口。

历史UnionHistory.result仅提供本地轻量记录：赛季/联盟范围、核对时间、每日总量、按稳定脱敏成员键汇总的Day2刀数/伤害/尾刀；不保存队伍角色、图片或完整Boss载荷。Day1明确为Boss通关记录，不算个人出刀。仅确认finalized的记录标结算；旧未结算快照缩为标记清楚的观测，不能冒充结算。完整快照保留最近两期，旧期先写并核实紧凑结果再清理；写入失败保留原快照，不中断查询。年度/月度/季度查询界面本版不实现，也不额外自动拉历史接口。

所有HTTP凭据、四名单、本人身份、静默收菜和CDK规则沿用；不新增运行依赖、不修改Core。下文历史章节中的全量刷新信息语义以本节为准。用户检查机制总结后自行决定线上实测，本轮只执行隔离离线验证。

### 1.0.26 官方CDK期限与库存保留

无凭据公开POST `/api/game/direct/Game/GetCdkRedemption`，正文仍为intl_game_id=29080。2026-10-24实测HTTP200/code0/is_last_page=true/total5；问题在旧解析器把GLOBAL,HMT整串视为未知产品。parse_official按逗号拆分已知产品成员，含GLOBAL/29080则接纳，仅HMT/29157则排除；未知结构、目录数量/分页、非法码或期限使整源失败并保留旧快照。

valid_time_start/valid_time_end是Unix秒，使用整数或ASCII数字字符串，不二次按本地时区解释。display_time为官网展示字段，不能替代真实有效期或覆盖valid_time_end。官网前端dayjs按浏览器本地时区显示；插件统一Asia/Shanghai到秒。实测1795532399为2026-11-24 22:59:59+08:00；退库边界为1795532699，即23:04:59，now>=该边界不再可用。

Store以CREATE TABLE IF NOT EXISTS新增official_code_times，按产品与ASCII大小写无关code保存官方起止和更新时间。原code_details继续单独保存GW报酬/日期；details计算有效视图时官方起止优先，报酬只取GW。缺失/0期限、列表空、推荐撤下、缓存TTL和来源失败均不清除已确认官方时间；较新的官方期限可更新，较老快照不得反向覆盖。原库存名和position不变；raw receipts/member_codes/blocks不因刷新清空。

merged除合并当前来源及成员池，还为已在inventory_codes中收录且拥有有效官方期限的码保留来源资格，直到expires_at+300。推荐位撤下不等于失效。GW更早/更晚期限都不能改写已知官方截止；没有官方期限时使用可靠GW期限，同样加300秒。时间退库只过滤可用库存，不写永久invalid/expired标记；明确官方兑换失效标记仍优先，公共刷新不得解除。若官方后来明确延长期限，非永久停用码可重新可用。

Redemptions在读取及提交前再次查询同一有效详情；单码、所有来源和48小时成功补录均受同一窗口约束。官方未来开始时间也适用于GW和成员变体；期限失效不删除本人已领取记录。期限显示到年月日时分秒，官方不减秒；GW解析保留原分钟截止的exclusive语义，显示减1秒而退库边界使用原expires_at+300。

PARSER_VERSION=3要求补取官方元数据。已知字段兼容的v2来源仍可在24小时缓存窗口内回退使用，避免升级后首次失败直接隐藏旧库存；v1等未知结构仍禁用。持久官方有效期不受来源24小时TTL限制。Catalog、runtime调度和Core命令注册保持原入口，手动与静默并发共用单飞；异常冷却、0/8/16点、4小时按需及每日首次策略不变，查询/刷新不加载凭据或兑换。

本版test_v126_official_cdk.py/test_v126_native_cdk.py覆盖真实5码响应、时间与产品结构、不同日期冲突、撤下/空/失败/重启、无成员兜底的保留、旧缓存升级、5分钟边界、未来开始、收据保全及真实Core命令+cron并发。公开接口研究和本地命令收集结果见当前handoff，不冒充线上QQ或真实领取验收。以下历史小节记录当时行为，期限以本节为准。

### 1.0.25 邮箱验证码暂停

同版追加CDK回执精简：result_text仅呈现兑换成功✅/已领取✅和原失败原因、统计、共享池结果，不渲染reward字段。数据层与查询详情保留报酬。detailed_result仅依据实际回执超过600字符或12行判断，后台结果开关仍默认关闭，5码简短成功回执在开关开启时也直发。

email_flow.EMAIL_LOGIN_AVAILABLE=False为发布级开关，不由旧配置自动开启。email_login_available供页面渲染、模式切换、发码/验码、工作任务和浏览器适配器共用；三条HTTP路由仍注册，返回503及固定提示。密码模式和取消操作保持可用。旧邮箱任务遇状态查询/提交会取消并清除码、滑块及截止时间，已成功会话和现有绑定不受影响；晚到邮箱结果在保存前再次检查开关。

模板保留可见邮箱按钮，服务端初始输出disabled/aria-disabled和提示；前端切换、发送、提交均检查同一可用值，异步finally不会重新启用暂停按钮。390/1440宽度的真实浏览器离线回归验证灰态、提示、无横向溢出及密码登录。原邮箱测试仅在隔离fixture中显式启用，保留接口回归，不代表生产恢复。

用户故障在发送阶段：滑块不出现、无邮件、等待后异常。2026-10-24无凭据核验公开官网/SDK：邮箱选择器与5位校验仍匹配；阻断所有认证/邮件写请求的模拟输入可生成腾讯验证分支。无法据此证明用户部署环境资源可达或找到确定根因。_wait_official在无可用frame或资源截图未就绪时不会调用on_captcha，最终报错，能解释症状但不能确认真实网络原因。详细证据与置信度见当前handoff排查报告。

### 1.0.24 大小写统一与库存结构保留

code_key将合法ASCII码casefold，仅作为匹配键，实际消息和提交保留既有显示写法。merged不再隔离大小写变体，同码合并来源与GW详情。inventory_codes按product+code_key唯一，以递增position保存首次入库顺序和code原文；成员先入库后刷新GW只补资料，新码追加。此表只提供显示顺序，不单独授予可用资格，仍须来自当前来源或有效成员记录并通过停用和期限过滤。

Store启动从旧来源和成员记录回填库存，以已有成员写法映射同码；保留全部旧表数据。新增查询使用ASCII NOCASE，在同事务里查重后写入；既有大小写重复的领取记录按success、claimed、submitting、uncertain、其他状态及更新时间选最强证据。补录不延长成功时间，历史确认仍不作为实际成功。GW元数据按同码归并，取最新可靠值并保留非空说明。共享失效、期限、命令查找、同轮去重和历史核验统一大小写匹配。

未执行破坏性数据库合并或清空，旧重复行作为历史证据保留。原账号隔离、权限、48小时窗口、期限后24小时退库与结果开关不变。test_v124_cdk_case_merge.py复现用户五个码先补录后GW反向顺序/大小写刷新，并检查逐码详情、顺序、重启、旧库恢复、领取/补录去重和失效一致性。

### 1.0.23 近期成功补录与库存生命周期

contribute_recent在单个SQLite事务读取当前identity(account/game/area/UID)的success或直接官方1302016回执，要求0<=now-updated<=48h，再按全局停用和期限原子入库。直接1302016使用固定DIRECT_CLAIMED_RESULT标记，兼容旧版相同回包记录；普通claimed、历史核验和uncertain不入库。complete_claimed将直接1302016回执与主动贡献入库原子提交；普通兑换仍不自动共享。已领取状态保持claimed，不冒充兑换成功。补录不提交官方兑换、不改回执时间；重复补录不延长48小时。member_codes验证时间保留原成功时刻，入库失败不会丢失原成功证据。原绑定、权限、有效凭据和CDK写开关继续适用。

新增code_details保存GameWith的报酬、可靠截止/开始时间和更新时间；启动时从旧sources回填。刷新更新非空报酬和可靠日期，空列表、空报酬或来源TTL不清除此证据。报酬覆盖对应库存条目的展示，但不会把历史来源标记为当前推荐。原始expires_at保持来源语义，retirement_at=expires_at+86400；查询、速查、各来源合并、成员池与提交前均按该时刻过滤。期限失效只退出可用库存，保留账本审计；明确官方停用优先，后续公共刷新和近期成功补录不能恢复停用码。

共享即时停用仅限1302003/1302015（无效/不存在）和原1302009（确认过期或不在时间窗口）。envelope保留网络异常标记；带超时/连接信息的矛盾业务回包视为uncertain。HTTP非200、无响应、连接中断、超时、5xx和限流不会归为码失效；账号/区服/次数/重复领取不共享停用。未知结果可只读核验，不重提、不新入池。

AliceUID_CDKForward继续保存查询详情原设置、默认True；新增AliceUID_CDKResultForward默认False。后者仅对带成功报酬或超过600字符/12行的结果生效，简短结果仍直发。两者复用原首文本节点、发送前核验、回执等待和失败回退，无Core改动或新增依赖。帮助仅更新补录说明与缓存版本，布局不变。

### 1.0.22 兑换码详情转发

Commands通过注入forward/profile接入共享send_with_forward和AliceBind.get_bind。query与无参redeem的公开列表进入send_detail；profile只读本地绑定，不调用load_client，速查始终绕过profile。结果带成功报酬、超过600字符或12行时进入同一链路，否则保留result_text直发及原@行为。

AliceUID_CDKForward默认True。首文本节点说明查询/结果并列出指挥官、区服与UID；所有节点为纯文本，无QQ昵称或@段。未绑定显示未绑定，未知昵称/UID明确标注。_DeliveryBot代理在实际转发及每个普通回退页前检查allowed/current；回退将字符串列表按1800字符分页并保留身份。使用原30秒回执等待（5～300可配）、60秒暂停及一次回退，不新增兑换提交或重试。

### 1.0.21 成员兑换码与只读速查

store启动以CREATE TABLE IF NOT EXISTS增加member_codes，不清空原sources/receipts/blocks。成员表按product+code唯一，保存有效/暂停/过期状态和验证时间；不向查询暴露验证者身份。Redemptions.run(contribute=True)只由新增码入口传入，只有submit明确返回成功后调用complete_success，在同一事务将submitting回执转success并写成员表。已有终态跳过、1302016、历史核验和未知结果均不晋升为新成功。

Catalog.report读取活动成员表并与官方/GameWith源合并，不要求公开来源刷新后才能看到新成员码，也不对成员表套公开源24小时TTL。block写共享停用时同步将成员行移出active，保留审计；publish只更新公开来源，不能抹掉成员验证或停用。精确码去重及大小写冲突保护沿用。

commands以原生增加兑换码命令(pm=6)承接新增；兑换码处理器先检测argument.strip()==速查并切到只读分支，不再注册一个会双命中的兑换码前缀命令。查询与速查均不load_client。详细文本按码块组织，pages优先段落，再按行，极端长行才硬分；源码中不拼接HTML外部资源。

HTTP服务错误判断收窄为500<=code<600，避免1302xxx业务码都被算入5xx。PARSER_VERSION=2使旧来源缓存按需重查，以恢复br/块元素中的报酬换行；网络抓取周期与CDK写开关保持原行为。当前帮助普通40项、Bot主60项，布局仍按7项阈值。

### 1.0.20 帮助模块与布局

仅 `nikke_help/draw.py`、`nikke_help/cache.py` 与 `templates/help.html` 改动帮助显示。context按七模块整理，普通身份不构造两个Bot主模块；原命令保留，签到说明按用户追加要求删除“任何”两字，其余逐条说明完全保留。section_bands将<=7条模块两两配对，>7条独占一行；大模块按items顺序每两个切为一行，确保DOM和视觉都是左→右→下一行。渲染采用明确的flex行与卡片宽度，避免原生渲染器的跨列兼容差异。

半宽468 CSS px，通栏952，页面仍1000；长卡行内两格自然高度，短卡不被同排较高卡拉伸。保持正文字号15、说明12、既有渲染DPI和字体/主题。CACHE_VERSION更新为1.0.20:help-modules-1，模板变化立即失效旧图；完整PNG与发送链路不变。

### 1.0.19 CDK 增量说明

实现位于 `AliceUID/nikke_cdk/`：parser处理GameWith DOM与板块/期限；api负责匿名来源与官方CDK局部请求头；catalog负责单飞刷新和8小时/4小时/每日首刷；store保存 `MAIN_PATH/cdk.sqlite3`；service只为经本人核验的角色串行兑换；commands/runtime接入原生Core注册与调度。只读命令为 `查询兑换码`；`兑换码` 内部按正文有无区分汇总/单码，避免前缀竞争。

官方端点：POST `/api/game/direct/Game/GetCdkRedemption`（公共列表）、`/api/game/proxy/Game/GetCdkRedemption`（本人列表）、`RecordCdkRedemption`（正文仅cdkey）、`GetCdkRedemptionHistory`（page_num/page_size）。CDK公共参数局部覆盖为game_id=16、area_id=global、intl_game_id=29080，保持旧客户端其他接口请求头不变。官网保存角色必须与绑定game_id/area_id/role_id一致。

目录、来源快照、共享停用、本人回执及租约共用一个SQLite。领取以真实账号/产品/区服/角色的哈希键识别，不存Cookie；成功与已领取跨命令保留。提交前落盘submitting，成功后先记success再回消息；崩溃/超时留下的submitting/uncertain只查官方近期历史，无法确认就不重发。没有官方幂等键，不能声称服务端严格exactly-once。1302009为不在时间窗口，只有明确过期证据才记expired，其余共享暂停；地区/次数/认证错误不记全局过期。

公开目录仅含当前支持的29080产品，港澳台仍未开放登录。每次展示和提交前按当前时间过滤截止期限。来源失败保留24小时内最后成功快照，失败不推进完整汇总时间；后台与Bot主刷新不触发兑换。lxml为显式运行依赖。维护与测试细节见 `AliceUID/nikke_cdk/MAINTENANCE.md`。

用户使用说明见 [README.md](README.md)，版本变化见 [CHANGELOG.md](CHANGELOG.md)。路径以本文件所在的插件外壳为基准；`AliceUID/nikke_api/client.py` 指外壳下的内层代码。

## 1. 系统与目录

```text
AliceUID/                       ← 可安装外壳
├─ __init__.py / __nest__.py     ← Core嵌套插件发现入口
├─ AliceUID/                    ← 内层代码
│  ├─ __init__.py               ← Plugins、SV、Web路由、调度与权限注册
│  ├─ nikke_*/                  ← 业务模块
│  ├─ templates/                ← Jinja HTML/CSS
│  └─ data/                     ← 随包静态表兜底
├─ assets/                      ← 登录页及资源小图
├─ card_bg/                     ← 六张原始背景
├─ formts/                      ← 字体；拼写是现有目录契约
├─ pyproject.toml / requirements.txt
└─ README.md / CHANGELOG.md / DEVELOPMENT.md
```

版本工作区额外包含 `tests_alice/`、`tools_alice/`、`docs/`、`handoff/`、`.references/`、`.runtime/`、`dist/`。这些属于开发与交付环境，不应直接放入Core插件扫描目录。生产与开发数据路径的区别见第9节。

### 注册顺序

[内层入口](AliceUID/__init__.py) 在正常模式下执行：

1. 注册 `Plugins(name="AliceUID", force_prefix=["nk"], allow_empty_prefix=False)`。
2. 在任何SV与StringConfig初始化前，通过Core PluginConfigStore完成旧前缀的一次性迁移，通过Plugins.set同步内存前缀，再调用Core的get_plugin_available_prefix读取帮助文案快照；随后建立插件配置与四名单策略。
3. 导入 `AliceBind` 模型并尝试挂载Core后台管理；不兼容的管理界面不会阻止普通登录。
4. 导入各模块命令和登录Web路由；部分模块在 `setup()` 中注册。
5. 启用日历、数据库命令及周检、社区调度、图鉴命令，绑定会战发送前核验。
6. 调用 `guard_plugin_triggers()` 保留普通命令的统一用户权限检查。前缀完全由Core原生SV注册生成，不替换触发器，不手动刷新候选索引。AI入口在to_ai注册前已加专用查询检查。

`ALICEUID_STANDALONE=1` 只供测试/离线渲染，跳过上述Core注册；生产不能设置它。

```mermaid
flowchart TD
    A[Core发现外壳与内层包] --> B[配置与权限策略]
    B --> C[AliceBind与登录路由]
    C --> D[命令与调度器]
    D --> E[统一用户权限包装]
    E --> F[本人绑定解析]
    F --> G[业务服务与缓存]
    G --> H[社区客户端或公共资源服务]
    H --> I[Builder规范化数据]
    I --> J[模板与渲染]
    J --> K[发送前再次核验绑定和权限]
```

### 模块职责

| 模块 | 主要责任与入口 |
|---|---|
| `nikke_config` | `config_default.py` 默认配置；`config.py` 路径与ValidatedStringConfig |
| `nikke_commands` | 旧前缀迁移、Core前缀启动快照、command_prefix提示映射 |
| `nikke_ai` | 四类to_ai查询入口的权限检查、图片结果核验后的最小数据摘要 |
| `nikke_message` | 默认开启的实验性转发、标题首节点、完整单图JPG、NapCat消息ID回执与普通消息回退 |
| `nikke_permissions` | 四名单校验、Core Trigger包装、群管理命令；`policy.py/config.py/access.py` |
| `nikke_user` | `AliceBind`、加密存储、加载本人客户端、绑定锁、受控后台解绑、主动面板刷新 |
| `nikke_login` | 选服命令、一次性内存会话、密码/邮箱浏览器流程、验证码与HTTP路由 |
| `nikke_api` | Credentials、CookieCipher、NikkeClient、StaticData解析、CDN路径生成 |
| `nikke_resource` | 静态表、图片缓存、皮肤映射、徽章、收藏品元数据、卡片资源准备 |
| `nikke_database` | 公共数据增量队列、预算与冷却、维护命令、周检调度 |
| `nikke_profile` | 个人资料取数与缓存、720 CSS宽信息卡Builder及绘制 |
| `nikke_character` | 角色匹配、本人持有校验、练度详情、装备词条、别名与持久面板缓存 |
| `nikke_roster` | 完整十列图鉴、AccountReads节流、可见内容指纹和发送后续期 |
| `nikke_union` | 本人联盟确认、赛季路由、成员/出刀规范化、当前与历史快照 |
| `nikke_status` | 资源与BOSS状态；成功图片窗口、容量估算、状态图缓存与命令 |
| `nikke_uid` | 明确类型的UID/分享标识登记；本地解析，不加载私人查询客户端 |
| `nikke_community` | 本人授权、任务协议、持久预算/幂等账本、立即执行与30分钟调度 |
| `nikke_calendar` | 匿名浏览器截取官网日历、缓存与过期提示 |
| `nikke_help` | 同源的权限感知帮助Context，图片与文字输出 |
| `nikke_render` | 模板主题、语言、字体、照片毛玻璃、布局注册、外置/原生渲染 |
| `nikke_proxy` | 浏览器代理适配；当前配置不等于已实现代理池或每用户独立IP |
| `templates` | 正式页面模板及 `card_badges.html` 等共享片段 |

## 2. 命令到业务的调用关系

| 用户入口 | 处理/服务 | 数据来源 | 输出 |
|---|---|---|---|
| 登录/登陆、绑定账号 + 区服 | `nikke_login.commands.nikke_login_cmd` | 显式区服、SessionStore | 一次性本人登录链接 |
| 重新登录/重新登陆 | `nikke_relogin_cmd` | 原绑定revision及区服 | 同账号同区服更新凭据 |
| 我的账号、解绑 | `nikke_login.commands` → `nikke_user` | AliceBind | 摘要/解除与缓存撤销 |
| 信息/名片/个人资料 | `nikke_profile.commands._profile_data` | basic、outpost、characters、saved_role、player_info | `build_profile_context` → `draw_profile` |
| 角色练度/面板 | `nikke_character.commands` → `CharacterQueryService.query` | 本人角色列表、匹配name_code的详情、静态装备表 | compact角色卡 |
| 卡片 | `RosterService.prepare` | basic与本人characters、资源映射 | 完整JPEG图鉴 |
| 刷新信息/刷新面板 | `nikke_user.panel_refresh` | 本人资料及全部角色/皮肤详情 | 原子替换持久快照，手动完成后发送信息图 |
| 出刀及速查/详情/缺刀/尾刀 | `nikke_union.commands` → `UnionService.query` | 本人联盟、成员、当前或历史赛季 | 会战卡片 |
| 会战血量 | `nikke_status.commands` → `UnionService.query_bosses` | 同一已验证联盟快照的level_payload | 血量状态卡 |
| 资源查询 | `ResourceStatusService.prepare_image` | basic→outpost→daily | 成功图片缓存窗口与资源卡 |
| 日历 | `nikke_calendar.commands/service` | 匿名官网默认页面 | 带时间/来源的截图 |
| 角色别名查询/新增/注册 | `nikke_character.alias_commands/aliases` | 静态角色与本地别名字典 | 查询卡/管理员写入 |
| 绑定UID/我的UID/解绑UID | `nikke_uid.commands` → `UIDStore` | 本人提交的明确类型标识 | 本地登记，不证明账号归属 |
| 签到查询[页码]（Bot主） | `runtime.report_group → group_report_text` | 本地绑定、group_seen与独立签到确认 | 本群已知范围文字分页 |
| 自动社区/签到/开启全量签到 | `CommunityCommands` → `CommunityService` | 本人授权及社区账本 | 本轮结果或状态 |
| 数据库更新/状态/帮助 | `DatabaseCommands` → `DatabaseService` | 公共表与固定美术源 | 后台队列与摘要 |
| 帮助/帮助文字 | `build_help_context → draw_help/help_text` | Core用户权限、当前绑定摘要 | 图片失败可回退文字 |

裸命令、空格与别名是否匹配由Core Trigger契约决定。登录与登陆注册到同一个 `on_command`；重新登录/重新登陆是 `on_fullmatch`，不额外接受换服参数。新增命令后必须同步帮助并重新执行统一Trigger包装。

## 3. 身份、区服与持有关系

### 标识不要混用

| 标识 | 含义/来源 | 使用规则 |
|---|---|---|
| `user_id + bot_id` | Core确认的消息发送者 | 选择绑定、权限与个人缓存；不用@对象替代 |
| `game_id` | 游戏产品编号 | 五区使用29080；不是每个玩家唯一值 |
| `area_id` | 区服数字 | 与客户端region及接口响应一起核验 |
| `intl_open_id` | Cookie对应的社区账号身份 | 本人私人接口参数；不能从任意输入UID构造客户端 |
| `uid / role_id` | 游戏角色UID | 主要从GetSavedRoleInfo的role_info.role_id读取，需game_id/area_id匹配 |
| `name_code` | 角色逻辑编码 | 静态名字、本人角色及详情匹配的主键 |
| `resource_id` | 角色美术资源编号 | 静态角色表映射，不能直接把name_code当文件号 |
| `costume_id / costume_tid` | 本人接口报告的皮肤ID | 需映射到本角色costumes中的costume_index |
| `skin_index` | 美术变体序号 | 用于SI/MI/full路径，不独立证明拥有 |
| `binding revision` | `sha256(cookie_enc)` | 旧会话、在途任务与缓存隔离；不日志输出密文本体 |

| 区服 | area_id | region.name |
|---|---:|---|
| 日服 | 81 | japan |
| 北美服 | 82 | na |
| 韩服 | 83 | korea |
| 国际服 | 84 | global |
| 东南亚服 | 85 | sea |

代码定义了港澳台91/29157，但它不在当前登录REGIONS中；不能据此宣传港澳台已支持。登录选服函数向detect_region只传一个所选候选，不跨区自动探测。

### 角色与皮肤映射

[StaticData](AliceUID/nikke_api/parser.py) 加载静态表。角色查询先按官方名称、简繁归一/别名等规则解析；歧义返回候选，不根据持有角色偷偷猜选。之后检查该name_code确实存在于本人characters，再请求/读取对应详情。

[resolve_skin](AliceUID/nikke_resource/skins.py) 优先读取角色列表 `costume_id`；仅在缺失时考虑匹配角色详情的 `costume_tid`。基础皮肤0为显式报告；未知、映射不到或重复映射降级为基础图并保留notice。双方报告冲突时列表优先；详情name_code不匹配时拒绝借用其皮肤。

```python
# 静态映射示例；owned_row应来自发命令者本人接口。
selection = resolve_skin(owned_row, static)
rid = static.resource_id(owned_row["name_code"])
url = character_resource_url("portraits", rid, selection.skin_index)
# 生产卡片通过ResourceService/ImageCache准备资源，不让模板自行联网。
```

头像/完整图库中存在文件、静态costumes列表或分享参数都不代表账号拥有。会战角色ID需要时通过 `character_id_map.json` 辅助映射；不能把其他成员详情当成本人私人练度。

## 4. 私人社区客户端接口

代码：[nikke_api/client.py](AliceUID/nikke_api/client.py)。基地址为 `https://api.blablalink.com`，数据读取默认语言 `zh-TW`。调用方使用 `load_client(ev.user_id, ev.bot_id)` 从本人绑定加载，结束后关闭client。

`_request` 串行访问该客户端实例、禁止跳转；HTTP401与业务401/300001归入NikkeLoginRequired，403/429按拒绝/限流报错，业务code=0解包，其他code为NikkeApiError。它不会通用自动重试；业务服务另行管理节流、缓存和允许的一次性补读。

下表G前缀为 `/api/game/proxy/Game/`；账号参数A为 `{intl_open_id, nikke_area_id}`，必须从已核验的本人客户端取得。

| 客户端方法 | HTTP/端点 | 请求 | 返回与用途 |
|---|---|---|---|
| `check_login()` | GET `/api/user/CheckLogin` | 当前Cookie与公共头 | code=0且msg=ok时True |
| `get_characters()` | POST G+`GetUserCharacters` | A | `data.characters`，本人持有列表 |
| `get_character_details(codes)` | POST G+`GetUserCharacterDetails` | A + `name_codes`列表 | `data`；服务匹配character_details与state_effects |
| `get_basic_info()` | POST G+`GetUserProfileBasicInfo` | A | `data.basic_info`；身份、进度、货币等 |
| `get_outpost_info()` | POST G+`GetUserProfileOutpostInfo` | A | `data.outpost_info`；前哨与同步等级 |
| `get_daily_progress()` | POST G+`GetUserDailyContentsProgress` | A | `data`；daily_progress中的保管箱容量 |
| `get_saved_role_info()` | POST G+`GetSavedRoleInfo` | 空对象 | `data.role_info`；匹配后使用role_id |
| `get_game_player_info()` | POST `/api/ugc/direct/standalonesite/User/GetUserGamePlayerInfo` | 空对象 | `data`；游戏概览/联盟名等 |
| `get_union_raid_data()` | POST G+`GetUnionRaidData` | A | 原始出刀data；实际会战服务负责更完整的联盟确认 |
| `get_union_raid_level()` | POST G+`GetUnionRaidLevelInfo` | A | 原始血量data |

### 会战服务的额外端点

[UnionService](AliceUID/nikke_union/service.py) 直接通过client._request调用以下POST端点，不能只用上表两个raid方法取代它的身份/赛季逻辑。

| G后的端点 | 参数 | 处理 |
|---|---|---|
| GetMyGuildInfo | 空对象 | 确认本人当前guild_id和guild_name |
| GetGuildMembers | guild_id、字符串nikke_area_id | 规范化成员名单，无法获取时不凭空补0刀 |
| GetUnionRaidData / GetUnionRaidLevelInfo | A，已确认时附guild_id | 当前/结算中的赛季快照 |
| GetUnionRaidDataOfGuildSeason / GetUnionRaidLevelDataOfGuildSeason | 数字area_id、guild_id、字符串season_id | 历史赛季；必须先确认本人联盟 |

公开 `/raid/raid_list.json` 经CDN映射后确定赛季与接口类型。只有已结算、通过历史接口取到非空出刀和血量的快照才能长期复用；仍先核对赛季、当前联盟及名单。没有赛季名单时，可将当前完整名单明确标为历史对照；新入会者无记录不能被认定为上期实际漏刀。

### 社区任务端点

代码：[api.py](AliceUID/nikke_community/api.py)、[service.py](AliceUID/nikke_community/service.py)。调用必须经过CommunityService的本人授权、绑定revision、账本与请求预算，不能直接重放写请求。

| HTTP/路径后缀 | 请求关键字段 | 用途 |
|---|---|---|
| GET `/api/lip/proxy/lipass/Points/GetTaskListWithStatusV2` | get_top=false、intl_game_id | 读取本周期任务状态 |
| POST `/api/lip/proxy/lipass/Points/DailyCheckIn` | task_id | 签到，账本去重 |
| POST `/api/ugc/direct/standalonesite/Dynamics/GetPostList` | plate_id=38、plate_unique_id=outpost、limit等 | 受预算约束的帖子候选 |
| POST `/api/ugc/direct/standalonesite/Dynamics/GetPost` | post_uuid | 已授权浏览 |
| POST `/api/ugc/proxy/standalonesite/Dynamics/PostStar` | post_uuid、type=1、like_type=1 | 已授权且确认未赞的帖子点赞 |
| GET `/api/lip/proxy/lipass/Points/GetUserTotalPoints` | 无额外业务参数 | 读取可确认的积分余额 |

已知当期已签到时不继续重复签到、浏览/点赞或积分读取。未知任务不猜测操作；跨北京时间08:00终止当前轮次，由下一轮重新识别。定时任务借用Core scheduler，每天北京时间配置时刻执行（默认08:33），配置保存后重排同一任务，单实例、合并调度。

1.0.05的 `Policy(min_interval,daily_requests,max_interval,switch_min,switch_max)` 默认 `(5,30,15,10,120)`；`pacing.parse_range()`解析后台范围字符串，`CommunityService.uniform`可注入测试随机源。每次逻辑请求抽取均匀分布间隔，只在真正reserve发送时推进全局next_at；等待循环不重复抽样。每轮抽取一个换号等待，pacing表增加last_account（账号哈希）与switch_at；上一账号最后HTTP响应成功/失败后都推进switch_at。下一账号满足max(next_at,switch_at)，同账号只满足next_at，已跳过账号不消耗等待或预算。SQLite迁移保留旧next_at，长等待扩展执行租约；600秒仍为实际请求执行的基础租约。

返回结果新增 `counts={signin,browse,like}` 与 `signin_confirmed`。只在HTTP成功确认后累计对应操作；跨08响应不得用counts冒认新周期签到。`messages.result_message()`生成紧凑文本，金币缺失不写成0，部分完成与异常暂停同时显示。signin_confirmations仍独立于last_day保存。

## 5. 登录Web与后台接口

代码：[routes.py](AliceUID/nikke_login/routes.py)。所有会话型API只面向Bot生成的当前登录会话；token是一次性能力标识，不是匿名查询任意账号的入口。每次检查会话、所属用户访问权限及旧绑定状态。

| 方法/路由 | 输入字段 | 功能 |
|---|---|---|
| GET `/nikke/assets/{filename}` | 安全的资源文件名 | 登录素材，拒绝路径穿越 |
| GET `/nikke/i/{token}` | 有效会话token | 输出登录页 |
| POST `/nikke/api/login` | token、account、password、可选generation | 启动密码登录流程 |
| POST `/nikke/api/mode` | token、mode、可选generation | 切换密码/邮箱等会话模式 |
| POST `/nikke/api/email/send` | token、account、可选generation | 本人触发邮箱验证码发送 |
| POST `/nikke/api/email/verify` | token、code、generation | 提交邮箱验证码 |
| POST `/nikke/api/status` | token | 轮询状态与当前挑战 |
| POST `/nikke/api/captcha` | token、dx、challenge_id、可选generation | 提交当前挑战的位移 |
| POST `/nikke/api/captcha/refresh` | token、challenge_id、generation | 主动刷新挑战 |
| POST `/nikke/api/cookie` | token、cookie | 会话允许时导入凭据 |

具体错误JSON及状态字段以路由函数为准，不依赖人类提示文字判断成功。前端须跟踪generation与challenge_id，过期挑战不能提交给新会话。

[SessionStore](AliceUID/nikke_login/session.py) 只在内存持有会话。创建默认TTL600秒；进行中的登录/验证码流程有独立360秒上限；成功结果保留300秒供状态读取。取消会递增generation、唤醒等待、取消任务并清理验证码/挑战内容。重启不恢复旧登录链接。

保存绑定经过 [save_login](AliceUID/nikke_user/service.py)：先持有本人绑定锁，核验已有绑定、revision和账号/区服；Cookie加密后落库，再重新读取确认提交结果。重新登录使用比较并交换更新，不通过删行重建账号，也不静默换人换服。

### 登录链接消息发送

`nikke_login.commands._send_login_link(bot,text,url,*,ev=None)`由首次登录和重新登录共用，显式传入当前Event；省略时可读取bot.ev。LoginQRCode控制二维码生成，构造显式text/image消息段，避免URL字符串被node构造器误识别为图片。LoginForward开启时以 `bot.send(MessageSegment.node(content))` 发送，不附外层at_sender。

OneBot私聊与Core非「允许」策略直接普通发送。共享边界依连接区分：NapCat适配器请求消息ID回执并在未确认时回退一次；其它适配器沿用异常/False回退、None/空列表不重发的兼容规则。二维码与原链接复用，普通群消息可at，取消向上传播。

发送仍经过原_LiveAccessBot.send权限包装。异常日志只记录类型，不记录URL、会话token或原始错误；不创建新的登录会话来重试发送。参考[鸣潮固定源码](https://github.com/Loping151/XutheringWavesUID/blob/4c1727580c613ef3034a391dc3156a1570cd5260/XutheringWavesUID/wutheringwaves_login/login.py)和[Core固定发送实现](https://github.com/Genshin-bots/gsuid_core/blob/1ce50ba381e0d9f48dc42385e35a7310dc5ed0f4/gsuid_core/bot.py)，验证文件为test_v106_forward.py。

### 1.0.08 修订：复用卡片完整单图路线

2026-10-20，用户已确认candidate3的nk卡片、nk帮助、nk出刀三类群转发成功。正式交付冻结该发送实现，仅更新验收与发布文档；本节后续候选阶段的待验收说明不覆盖该结果。JPG转换和原生配套仍为可选路线，不能将三项标准路线成功当作这些可选方案的实机验收。

当前candidate3以保存的1.0.07 fix1 ZIP为消息结构基线，恢复默认标准转发，无需安装NapCat配套。send_with_forward构造纯MessageSegment.node，首节点标题文字，下一节点完整原图；帮助附注并入标题。过滤输入中的at/at_all，不传at_sender=True给转发；Core默认False，普通回退仍可at。保留wait_recall，它是回执观察参数，不改变适配器最终send_msg节点内容。

prepare_forward_content新增读取AliceUID_ForwardReencode，默认False，先校验完整图格式/像素和大小，再snapshot落盘读回，原图字节不变；PNG不再默认转JPG。显式True才进入现有encode_forward_pages编码器，ForwardJpegQuality默认95/0–100继续保留。格式为PNG/JPEG/WEBP、单帧、6400万像素及完整输出8MiB保护限制不放宽；不获取URL或借用他人图片。诊断默认strategy=classic_original，发送日志strategy=classic_node，可选转换为jpeg_optional。

test_v108_classic.py直接从冻结fix1 ZIP载入原send_with_forward，旧/新实现分别经过固定Core和实际TS适配器，比较最终send_msg action及params完全一致；覆盖PNG/JPEG/WEBP原字节、真实长图尺寸、失败原图回退及转发无at。此验证不模拟QQ已成功。以下candidate2原生路线仅为可选实验，非当前安装前提；已安装者应禁用配套后对照标准路径。

candidate2在保留完整单图的基础上增加两段准备流程。`nikke_message.outbox.snapshot(data,root)`先原子保存成品图并重新读取验证SHA256，`prepare_forward_content`仅使用校验后字节构造image段。路径为CACHE_PATH/forward_outbox，64MiB/32份，15分钟有效，在后续写入时清理；仅处理本模块命名的文件。登录二维码与链接排除，缓存失败在任何转发入队前整体普通回退；不形成自动重放队列。

NapCat配套位于integrations/napcat-plugin-aliceuid-native-forward。它通过公开actions.get('send_msg')取得当前实例，包装该实例base_handle，按固定AliceUID标题及一张inline图片识别帮助/图鉴/出刀。其余消息调用原实现。被识别的单次调用使用Object.create(this)建立专用接收对象，分别提供原生节点准备函数；不更改全局packetStatus，不替换其它实例或适配器源码。原base_handle继续负责目标解析、最终短消息ID映射及返回格式，原OneBot action入口校验不变。

原生准备通过obContext.apis.MsgApi.createSendElements将段准备到NapCat本地，再用sendMsgWithOb11UniqueId发到自身会话并取得raw msgId。每个节点都成功才调用core.apis.MsgApi.multiForwardMsg合并到原群；部分失败不发送仅标题转发。使用新peer对象避免SDK写guildId造成跨调用污染，总预算8秒、单实例一项在途；失败脱敏并交Core一次回退，不重试Packet。最终群发送已发起时不可强制取消，迟到可能与回退重复。卸载只在包装仍属于自身时恢复原方法；后装的其它包装不被覆盖。

XWUID参考固定提交4c1727580c613ef3034a391dc3156a1570cd5260，登录转发采用MessageSegment.node并准备临时二维码；并未发现绕过本次NapCat Packet上传的插件专用接口。新增路线按实际NapCat 4.18.37原生SDK实现，需同时安装Core更新与NapCat配套；单独替换Core不会启用原生路线。详见[integrations](integrations/README.md)。

以下为candidate1实现基础与其回执规则；该候选实机未通过，不作为投递已修复的证据。

四类转发保持实验性。父版1.0.07已经正式封包冻结，实机帮助/出刀投递问题未解决。用户要求优先复用成功卡片的写法，因此本版取消转发图片自动分页，采用完整单图；帮助附注合并到标题文本，形成一条文字节点加一张完整图。分页是最初失败后引入的，不能确认其为全部失败的根因，也不能把离线测试或回退成功写成转发稳定。

`nikke_message.send_with_forward(bot,ev,message,*,config_key,title=None)`由四类输出共用，四开关按最新授权默认True、已有值保留。HelpForward包装成功帮助图片与附注；RosterForward包装完整阵容图片；UnionForward包装出刀成功图片；LoginForward包含首次/重新/处理中原链接和二维码。只在转发时插入title文本首节点，普通路径保留原消息。图鉴标题取已核验绑定nickname，出刀标题取本次context.guild_name，缺失时用明确占位；不额外请求玩家资料。

仅发送标准text/image子段的纯node，不附外层at，不再发送任何身份控制段。ForwardUseBotIdentity配置和上次NoneBot适配已移除。Core和实际适配器都不改，头像昵称沿用适配器设置。

用户实际链路是[napcat-plugin-gscore-adapter @ df1859b](https://github.com/xiowo/napcat-plugin-gscore-adapter/blob/df1859b396ffbd73bd2b72ce4a35147667281472/src/services/gscore-service.ts)。handleGsCoreMessage调用send_msg，并在自身catch错误；Core的bot.send默认只确认WS入队，无法感知这次错误。适配器在MessageSend.echo存在时，无论成功/失败都会回传recall_message_id，成功带消息ID，失败为null。

对bot_id=onebot且WS_BOT_ID为napcat或napcat-*，共享边界检查底层_Bot的_recall_waiters字典与_supports_recall。旧Core缺少能力、HTTP任务或能力已锁定False时直接普通；其余通过受权限包装bot.send(node,wait_recall=True)，由Core按echo匹配回执。取得非空消息ID列表则返回，未确认回退原内容一次并暂停该连接转发60秒，后续查询普通发送。连接暂停表仅存元数据，最多64项。参考Core原等待上限10秒且finally清理Future；1.0.11 fix1的receipt.py为本次AliceUID转发提供默认30秒的实际等待覆盖，取消不回退，不修改Core全局等待常量；回执丢失、失败和仍在上传都可能返回空列表，迟到成功可能造成一次重复，普通回退不触发递归转发。

`nikke_message.images.encode_forward_pages(data,quality=95)`保留兼容入口，但现在只返回包含一张完整图片的列表，不再分页。`prepare_forward_content(content)`只处理inline base64图，读取AliceUID_ForwardJpegQuality，下次发送生效；将文本合并到首节点，保留非文本段顺序。配置保存接受严格整数0–100，非法磁盘值编码时安全回到95。现有JPEG验证后字节直通；不透明图使用指定质量的RGB JPEG、4:4:4、非渐进编码，真正透明图保留无损RGBA PNG。保留DPI、ICC和全部原始尺寸。输入32MiB/6400万像素、完整输出8MiB上限，JPEG尺寸每边上限65500；超出即整体普通发送原图，不降质量、缩放或截断。8MiB是插件保护上限，不能冒称QQ官方限制。不读取文件引用或拉取URL，编码在线程内串行限并发；源渲染器、缓存和LoginForward二维码不改。

历史实机日志出现NapCat Highway上传服务器8080连接超时及HTTP回退超时，最新一次只有Core未确认日志，不能据此认定每次都是同一原因。日志现在记录strategy=roster_single、输入/输出实际格式、尺寸、体积、kind、节点/图片数、回执耗时与确认状态；不输出图片Base64、标题、昵称、QQ号、登录链接或原异常内容。透明图实际输出PNG会如实记录，不能统称所有转发图片已变成JPG。完整单图路线仍需实机检验，不能保证修复上传网络。

test_v107_forward.py使用Node24原生TypeScript类型擦除，执行固定适配器实际handleGsCoreMessage/convertGsCoreToOB11/extractMessageId/sendRecallReceipt，并与固定Core真实target_send/resolve_recall组合验证错误被吞、ID确认、普通原图回退和Future清理。Node只作为离线开发验证，不新增生产依赖。参考AstrBot插件确认“当前账号uin”路径，但其框架能力不移植到Core。更多通道说明见[integrations](integrations/README.md)。

### Core后台绑定管理

[admin.py](AliceUID/nikke_user/admin.py) 在Core提供兼容管理接口时注册AliceBind摘要；`/api/database/table/<table>` 读取/导出做脱敏，通用新增/编辑/导入/删除被拒绝。

专用 `POST /api/aliceuid/bindings/{record_id}/unbind` 依赖Core管理员认证，body包含 `user_id`、`bot_id`、`binding_version`。它核验当前记录版本，执行原解绑生命周期并清除旧会话与缓存。不要通过通用数据库写接口更新凭据。

## 6. 字段与展示映射

| 原始资料 | 规范化/展示 | 位置 |
|---|---|---|
| basic.nickname、lv、area_id | 指挥官姓名、等级、区服 | profile.builder、parser.parse_profile |
| saved role_info.role_id | 游戏UID；先核对game_id/area_id | login.regions、profile.builder |
| basic.created_at | 苏醒日/注册日期，UTC+8日期 | parser._ts_date |
| profile_team[].name_code | 按本人持有角色组成最多5位展示队伍；未设置时按战力前五 | profile.builder |
| progress_normal_campaign / progress_hard_campaign | stage_list对应关卡名 | StaticData.stage_name |
| outpost等级、synchro_level、recycle_room_researches | 前哨、同步等级、循环室数量 | profile.builder |
| 角色grade + core、original_rare | SSR最多3星/SR最多2星/R无星；核心01～06与MAX | resource.card_meta.progression |
| class、element_id.element、use_burst_skill | 职业/属性/爆裂图标键 | character.collection.role_icons |
| shot_id.element.weapon_type | AR/MG/SG/RL/SMG/SR枚举 | parser.static_weapon_type |
| head/torso/arm/leg装备与词条ID、state_effects | 四装备、总览词条、等阶与百分比 | character.builder、overload相关函数 |
| character_skill_map.resource_id | 技能图标映射 | resource.service、character.builder |
| favorite_item/harmony_cube报告 | 珍藏品/收藏品/魔方公开元数据与等级 | character.collection、resource.collections |
| basic.currencies[] | 八类资源；明确0与缺失/隐藏分开 | status.builder.build_resources |
| daily_progress[0].outpost_battle_storage_fullness | 0～1转百分比；隐藏/缺失为未知 | status.builder |
| level_info[].boss_info[].max_hp/current_hp | 大整数血量及截断百分比；无限血量不除零 | status.builder.build_bosses |

货币type映射：钻石98+99，信用点2000，黄金积分券12000，白银积分券11000，战斗数据1000，芯尘3000，招募券5100，高级招募券5200。任一需要合计的组成缺失时显示未知，不用0补齐。

装备词条必须保留原始值、类型与符号，结合静态规则转换；不要将所有字段统一乘100或直接套用某一个Percent名称。普通装备和未知等阶不能伪造T10词条。名称匹配、单位、突破越界与皮肤回退均有对应测试。

## 7. 公共素材与CDN映射

代码：[resource.py](AliceUID/nikke_api/resource.py)、[ResourceService](AliceUID/nikke_resource/service.py)、[ImageCache](AliceUID/nikke_resource/cache.py)。公开下载与私人客户端分开，不携带Cookie/Authorization。

### 角色资源类型

| kind | 逻辑路径 | data/AliceUID/resource下目录 | 嵌入尺寸上限 |
|---|---|---|---|
| icons | `/character/si/si_c{rid:03}_{skin:02}_s.png` | characters/icons | 256×256 |
| portraits | `/character/mi/mi_c{rid:03}_{skin:02}_s.png` | characters/portraits | 600×900 |
| full | `/character/full/c{rid:03}_{skin:02}.png` | characters/full | 1200×1800 |

上限只约束嵌入图，不代表所有源文件具有这些尺寸。原始缓存图保持完整；正式信息卡首位用MI、其余SI；练度compact使用MI完整主体，图库仍可独立维护full。

`character_resource_url(kind,rid,skin)` 验证整数资源键，再交给 `obfuscate_path()`：去除前导斜杠，用受控PRIMES和32位djb2生成中间目录段，最终文件名为完整逻辑路径的MD5并保留扩展名，前缀为 `https://sg-tools-cdn.blablalink.com`。不要猜CDN哈希地址；图片本地文件名为 `cNNN_SS.png`，URL和SHA256写同名侧车JSON。

### 静态表与其他资产

| 本地static文件 | 用途 |
|---|---|
| nikke_list_zh-TW_v2.json | name_code、resource_id、名字、稀有度、属性、costumes等 |
| stage_list.json | 关卡ID到显示名 |
| equip_option_table_v2-zh-tw.json | 词条及状态效果静态描述 |
| ItemEquipTable-zh-tw.json | 装备条目与图标资源 |
| character_skill_map.json | 角色resource_id到技能图标 |
| character_id_map.json | 会战等场景角色编码辅助映射 |
| character_avatar_map.json | 公开头像辅助映射表；有记录不代表玩家拥有 |

实际逻辑路径及主键由 `nikke_resource.service.TABLES` 模块级字典登记。加载先用随包兜底，再合并外部static；更新按字段、行数变化及体积校验，失败保留旧表。

装备、技能、收藏品、魔方分别落到 `equipment/icons`、`skills/icons`、`collections/icons`、`cubes/icons`。属性/职业/爆裂在 `rolemeta/icons`，企业在 `corporations`，武器在 `rolemeta/weapons`。允许的逻辑前缀由PUBLIC_ICON_TYPES控制。

### 固定徽章与基础图标

`base_icons.py` 登记23项基础图标及4个官方徽章基底；`badges.py` 实现star_active、star_inactive、core、power的按需下载与校验。星/核心落 `rolemeta/breakthrough`，战力符号落 `rolemeta/power/team_combat.png`；战力数字仍来自账号数据，不是数字图片API。

URL白名单只增加六个确切武器URL和四个确切徽章URL，不扩大成官网任意路径。成功来源标记为community_download，失败使用已审核内置字节并标记fallback。带哈希文件名长期复用；无哈希core固定URL每7天条件校验，老合格缓存导入时起算本地TTL。403/429持久冷却，强制更新不越过冷却。

普通图片缓存包含按路径锁、原子写入、ETag/304、图片格式/10MiB/24M像素限制、旧可用图回退。基础图标匿名请求共享2秒节流；批量维护另由PublicHTTP共享预算。源URL改变时不能把旧来源图片或旧冷却当成新来源成功。

## 8. 缓存与并发规则

| 层 | 键/存放 | 复用与失效 |
|---|---|---|
| 个人资料、角色列表与皮肤 | `cache/panels/<身份摘要>/snapshot.json` 的profile/roster | 无TTL；信息/图鉴查询复用，整体手动更新替换，解绑清除，重登新revision重建 |
| 练度原始数据 | 同一snapshot.json的details | 无TTL；角色更新仅替换指定角色，保留其余详情及profile；全体更新原子替换 |
| 练度图片 | PanelCache，角色+数据+风格指纹 | 已有图片先复用，身份/参数改变重绘 |
| 图鉴图片 | `cache/roster`，owner/账号/revision+可见内容/素材hash | 成功发送后滑动7天；失败发送不续期 |
| 资源成功图 | ResourceStatusService._ready | 成功校验图片后300秒，不滑动；24MiB总上限；丢失/到期/风格变化重新同步 |
| 状态图底层缓存 | 内存及 `cache/resource_images` | 按内容/身份/主题/语言/字体/模糊指纹复用 |
| 会战 | 账号核验缓存+同服同联盟同赛季快照 | 当期默认180秒；已结算非空历史快照可长期复用但仍核验赛季与本人联盟 |
| 日历 | `cache/calendar` | 默认1800秒；失败冷却300秒，可明确标注旧截图 |
| 公共图片 | `resource/` + 侧车JSON | 按来源、hash、TTL/ETag与失败冷却，不按玩家UID重复保存 |
| 社区账本 | `community.sqlite3` | 授权、lease、请求预算及已完成action持久化；重启不清空 |

### 收菜图片窗口

```mermaid
flowchart TD
    Q[本人查询与权限核验] --> C{有有效同风格成功图?}
    C -- 有 --> S[直接重发 不延长窗口]
    C -- 无 --> F{短故障冷却结束?}
    F -- 否 --> W[返回剩余等待秒数]
    F -- 是 --> R[basic → outpost → daily]
    R --> D[规范化资源与容量]
    D --> P[渲染并校验图片]
    P --> V[再次核验绑定与epoch]
    V --> T[从成功时刻记录300秒窗口]
    R -- 失败 --> E[5秒故障门槛 403/429为60秒]
    P -- 失败 --> E
    T --> S
```

生产命令必须走 `ResourceStatusService.prepare_image()`，不能只调用query就宣布进入5分钟窗口。query的纯数据缓存不等于可发送图片。传入actor=(user_id,bot_id)和异步still_current回调；生成成功但发送失败时保留ready图。invalidate递增epoch，阻止旧在途数据或图重新提交。

`AccountReads.transaction()` 被图鉴、主动面板刷新和资源链路使用：按账号锁、全局两槽、每次get请求间隔5秒、每事务最多5次；wait=True可等待批次间隔。个人资料与练度服务另有自己的账号锁和批次门槛；不要误以为所有私人接口都由一个全局5秒队列控制。会战服务也有自己的每账号5秒请求间隔。

## 9. 存储、权限与绑定生命周期

生产根目录由 `get_res_path() / "AliceUID"` 生成，代码不硬编码开发机D盘。

```text
Core资源根/AliceUID/
├─ config.json / group_policy.json     # 当前配置及旧策略兼容文件
├─ secret.key                         # Cookie加密密钥
├─ character_aliases.json             # 自定义角色别名
├─ uid_bindings.sqlite3               # 独立UID登记
├─ community.sqlite3                 # 社区授权与幂等/预算账本
├─ static/                            # 公开表
├─ resource/                          # 公开美术缓存及来源JSON
├─ database/manifest.json             # 公共更新队列、进度与冷却
├─ cache/auth_invalid/               # 已知失效凭据版本摘要，不含Cookie
├─ cache/panels/                      # 本人面板数据/图
├─ cache/roster/                      # 图鉴图与发送续期
├─ cache/resource_images/             # 私有资源状态图
├─ cache/union_history/               # 按联盟/赛季隔离的历史快照
├─ cache/calendar/                    # 公共日历截图
└─ players/                          # 初始化保留目录，具体使用以模块为准
```

AliceBind继承Core Bind，实际位于Core配置的数据库，不是上面目录中的一份随意复制的独立SQLite。主要字段：intl_open_id、area_id、game_id、cookie_enc、nickname、uid、cookie_expire、is_public、is_master，加上Core的user_id/bot_id等身份字段。

CookieCipher使用独立secret.key进行加密。备份运行环境时保留密钥与原数据库对应关系。密码和验证码属于短期会话数据，不作为配置或发布资料保存。现有`is_public`不代表群排行已实现，`MasterQQ/is_master`也不提升Core服务pm权限。

群白名单非空时先限制范围，再判群黑名单；用户名单同样处理，交叉冲突拒绝保存。用户访问限制覆盖账号命令/Web会话/社区任务；查询命令额外检查群策略。发送者来自ev.user_id，不能用ev.at或用户给的UID选择别人的Cookie。

重新登录使用同账号同区服的比较并交换，更新后撤销旧社区授权并使相关缓存失效；失败保留旧绑定。解绑要走AliceBind.delete_bind及现有清理生命周期，不手工删数据库文件。后台受控解绑会同时清除旧会话。

开发时 `nikke_resource.workspace.nikke_data(ROOT)` 读取版本工作区workspace_paths.json，将数据定位到共享data根下的AliceUID；生产不读取这个开发映射。旧工作区路径仅用于参考/恢复，不应写进可安装代码。

## 10. 渲染接口

[render_html](AliceUID/nikke_render/render.py) 输入HTML与root_width、可选dpi；默认DPI144，对应1.5倍像素。外置服务启用时发送 `POST JSON {"html": "..."}`，可附Bearer Token，期望HTTP200及有效PNG字节；失败转Core原生 `render_html_to_bytes`。

原生渲染用Core当前原生接口，不应在文档中写成“必定Playwright回退”。Playwright也用于登录、日历及离线浏览器对照，属于不同用途。

| 卡片 | CSS宽度/策略 |
|---|---|
| 角色compact | 660；MI主体contain，完整立绘与装备/工具区 |
| 个人信息 | 720；姓名卡与圆角主立绘分离、四位队员、88px指挥官头像 |
| 图鉴 | 1400；十列128px头像+32px姓名；强制96DPI后检查完整尺寸，JPEG编码 |
| 状态、会战、帮助 | 常用1000；以各draw调用root_width为准 |

图鉴197名高3560、203名高3728；encode_complete拒绝尺寸不完整的图，不能通过截断末行适配文件大小。字体优先从formts读取AaZongYiYuan-2.ttf，无法使用时走显式兜底。毛玻璃0～100%只作用背景，新默认20%；主题新默认random，已有自定义值保留。拍照背景只铺底层，子模块使用半透明主题色。

修改可见布局、元信息、资源选择或渲染参数时同步检查缓存fingerprint/render_version，防止发送旧模板图。信息卡目前每次命令绘制，不是独立的持久成图缓存服务。

## 11. 公共数据库维护

`DatabaseService.run_continuous()` 连续执行有预算的run批次；持久manifest保存资产目录、队列、已下载hash、失败冷却及结果。固定27项图标/徽章与角色SI/MI/full共用任务与字节预算，未完成不能报告全成功。

默认每批40图、128MiB下载预算、2048MiB图库预算、总运行30分钟，失败冷却3600秒；请求间隔实际由PublicHTTP限制至少2秒。关闭皮肤补全会剪除待执行的变体任务，但不会删除旧图片。并发手动/周检/后台触发去重。

调度使用Core共享scheduler：周五02:33，时区Asia/Shanghai，max_instances=1、coalesce=True。不要在插件内另建第二个调度器。

## 12. 配置索引与已知说明差异

下面默认值从config_default.py静态提取。运行时约束在各服务校验，历史WebUI描述并不总是当前行为的完整契约。

- ResourceCacheSeconds是兼容键；实际为成功图片后300秒，而非失败请求后的300秒。
- CommunityDailyRequests当前说明与cycle_day均按北京时间08:00划周期；每天执行时刻由CommunitySignTime控制。
- RenderDpi旧描述写1000px模板；实际信息720、角色660、图鉴1400且96DPI。
- DatabaseRequestInterval旧描述提到1.5秒，当前PublicHTTP实际最低2秒。

| 配置键 | 类型 | 默认值 | 用途标题 |
|---|---|---|---|
| `AliceUID_GlassStrength` | GsIntConfig | `20` | 全局毛玻璃强度（%） |
| `AliceUID_ResourceCacheSeconds` | GsIntConfig | `300` | 资源查询刷新间隔（固定300秒） |
| `AliceUID_UnionCacheSeconds` | GsIntConfig | `180` | 联盟查询缓存秒数 |
| `AliceUID_CardLanguage` | GsStrConfig | `zh-CN` | 卡片文字语言 |
| `AliceUID_CardFont` | GsStrConfig | `factory_default()` | 卡片字体 |
| `AliceUID_GroupWhitelist` | GsListStrConfig | `[]` | 群白名单 |
| `AliceUID_GroupBlacklist` | GsListStrConfig | `[]` | 群黑名单 |
| `AliceUID_UserWhitelist` | GsListStrConfig | `[]` | 用户白名单 |
| `AliceUID_UserBlacklist` | GsListStrConfig | `[]` | 用户黑名单 |
| `AliceUID_MasterQQ` | GsListStrConfig | `[]` | Bot 主 QQ |
| `AliceUID_LoginUrl` | GsStrConfig | `` | 登录页外网地址 |
| `AliceUID_LoginQRCode` | GsBoolConfig | `false` | 登录链接转二维码 |
| `AliceUID_LoginForward` | GsBoolConfig | `true` | 登录/重新登录链接用转发消息，保留已有配置 |
| `AliceUID_HelpForward` | GsBoolConfig | `true` | 帮助图片用转发消息 |
| `AliceUID_RosterForward` | GsBoolConfig | `true` | 完整卡片用转发消息 |
| `AliceUID_UnionForward` | GsBoolConfig | `true` | 出刀图片用转发消息 |
| `AliceUID_ForwardJpegQuality` | GsIntConfig | `95` | 新编码转发图片JPG质量，严格整数0–100，100非无损 |
| `AliceUID_DefaultArea` | GsIntConfig | `81` | 默认区服（旧版兼容） |
| `AliceUID_LoginMode` | GsStrConfig | `browser` | 登录方式 |
| `AliceUID_BrowserChannel` | GsStrConfig | `auto` | 浏览器通道 |
| `AliceUID_Headless` | GsBoolConfig | `true` | 无头浏览器 |
| `AliceUID_Proxy` | GsStrConfig | `` | 浏览器代理 |
| `AliceUID_LoginTTL` | GsIntConfig | `600` | 登录链接有效期（秒） |
| `AliceUID_CacheTTL` | GsIntConfig | `600` | 兼容旧配置；信息/图鉴/持久角色快照不使用该TTL过期 |
| `AliceUID_RemoteRenderEnable` | GsBoolConfig | `false` | 外置渲染开关 |
| `AliceUID_RemoteRenderUrl` | GsStrConfig | `http://127.0.0.1:3000/render` | 外置渲染地址 |
| `AliceUID_RemoteRenderToken` | GsStrConfig | `` | 外置渲染 Token |
| `AliceUID_CardTheme` | GsStrConfig | `random` | 全局卡片主题，已有自定义保留 |
| `AliceUID_CharacterCardStyle` | GsStrConfig | `compact` | 角色练度卡布局 |
| `AliceUID_AIQueryEnabled` | GsBoolConfig | `false` | 允许Core AI只读查询；关闭后立即拒绝，普通命令不受影响 |
| `AliceUID_RenderDpi` | GsIntConfig | `144` | 渲染分辨率 DPI |
| `AliceUID_RenderTimeout` | GsIntConfig | `60` | 外置渲染超时（秒） |
| `AliceUID_CommunitySignTime` | GsStrConfig | `08:33` | 每日签到时间（北京时间HH:MM，保存即重排） |
| `AliceUID_CommunityPaused` | GsBoolConfig | `false` | 暂停所有社区任务 |
| `AliceUID_CommunityRequestRange` | GsStrConfig | `5-15` | 请求随机间隔秒数范围，重启生效 |
| `AliceUID_CommunityAccountRange` | GsStrConfig | `10-120` | 换账号随机等待范围，重启生效 |
| `AliceUID_CommunityDailyRequests` | GsIntConfig | `30` | 社区每日请求上限 |
| `DatabaseWeeklyUpdate` | GsBoolConfig | `true` | 每周自动更新公开数据库 |
| `DatabaseCalendarUpdate` | GsBoolConfig | `true` | 按招募日历静默更新公开数据库 |
| `DatabaseIncludeSkins` | GsBoolConfig | `true` | 数据库包含公开皮肤变体 |
| `DatabaseMaxTasks` | GsIntConfig | `40` | 数据库每批图片任务上限 |
| `DatabaseMaxDownloadMB` | GsIntConfig | `128` | 数据库每批下载预算MiB |
| `DatabaseMaxDiskMB` | GsIntConfig | `2048` | 公共图库存储预算MiB |
| `DatabaseRequestInterval` | GsIntConfig | `2` | 数据库请求间隔秒 |
| `DatabaseFailureCooldown` | GsIntConfig | `3600` | 数据库失败冷却秒 |
| `DatabaseMaxRunMinutes` | GsIntConfig | `30` | 数据库单次后台运行分钟上限 |
| `AliceUID_EnableWriteOps` | GsBoolConfig | `false` | 其他写操作（兼容预留） |

## 13. 测试与开发工具

测试位于版本工作区的 `tests_alice/`。conftest设置独立模式，Core集成由明确的stub/固定Core源码契约测试负责。用MockTransport和构造身份验证接口，不把真实登录、发码或社区写操作作为自动回归。

| 关注点 | 主要测试 |
|---|---|
| 资源成功窗口/失败重试/重发 | test_v103_resources.py、test_v101_resources.py、test_status_cache.py |
| 登录别名与Core匹配 | test_v103_login_aliases.py、test_command_contract.py、test_relogin.py |
| 角色/皮肤/装备/词条 | test_character_*、test_reported_skins.py、test_overload_units.py、test_collections.py |
| 公共资源/预算/徽章 | test_resources.py、test_base_icons.py、test_v102_badges.py、test_database.py |
| 图鉴/刷新/缓存 | test_roster.py、test_roster_refresh.py、test_v102_cards.py |
| 联盟/历史/0刀 | test_union*.py、test_v100_history.py、test_v101_zero_attacks.py |
| 权限/绑定/后台 | test_access_policy.py、test_policy_integration.py、test_unbind.py、test_v100_admin.py |
| 社区幂等与周期 | test_community.py、test_v100_community.py |
| 渲染/主题/字体 | test_character_render.py、test_glass_render.py、test_card_fonts.py、test_v101_glass.py |
| 打包结构与隐私 | test_release_pipeline.py、tools_alice/build_release.py |

运行示例，在版本工作区根执行：

```bash
python -m pytest tests_alice -q
python tools_alice/check_plugin.py AliceUID
python tools_alice/build_release.py --plugin-only --build-tag docs
```

若使用外部开发依赖，将workspace_paths.json中的development_packages加入PYTHONPATH。关闭字节码写入可用PYTHONDONTWRITEBYTECODE=1；临时文件明确指向本轮临时目录。pytest及渲染会重新生成临时文件/图片，生成后按当轮归档规则处理。

仍保留的工具按用途分组：构建/自检 `build_release/check_plugin`；图库 `audit_resources/update_static/prefetch_icons`；渲染与测试共享夹具 `preview_character/preview_roster/preview_help/preview_status`；正式布局验收 `preview_v102/preview_v103_help`；公共资料诊断 `probe_*/verify_database_live`。涉及网络或私人快照的工具不是日常离线测试入口，应先读其输入和授权范围。

2026-10-20清理已将历史预览图、旧一次性工具、测试临时目录移入CodexZone/回收站；测试/构建仍引用的辅助代码、参考样本和core_base_models.py保留。历史证据中的图片路径可在归档清单找到，不需要把旧Base64页面重新加载进会话。

## 14. 变更与发布流程

1. 按当前约定在独立版本目录开发，先读AGENTS及handoff当前进度；共享图库只读复用。
2. 修改命令时同步图文帮助；修改字段时同时检查Builder、资源准备、模板与缓存指纹。
3. 优先运行相关离线测试。涉及布局时验证亮/暗和原生/浏览器，检查完整尺寸、溢出、缺图及空数据。
4. 更新pyproject版本与CHANGELOG。README只维护当前能力和用法；架构/接口变化更新本文件。不再新增RELEASE_版本号.md。
5. 用build_release产生独立新文件名，保持外壳、__nest__.py、模板、字体和六背景；不覆盖旧ZIP。
6. 校验CRC、源包哈希、干净解压、旧模板覆盖和隐私；记录实际通过数与未验证的实机边界。
7. 保存handoff进度、交付说明及包哈希。发布包就绪不等于已部署，不自动操作用户NAS或真实社区账号。

本版本功能回归基线为1188通过、1项Windows符号链接权限跳过；这是修复交付时的记录。本次工作区清理/文档重写不等于重新跑过全部功能测试，新的验证结果以本轮handoff日志为准。

## 15. 源码定位索引

下表为静态装饰器提取结果，可帮助从命令反查处理函数。动态四名单（群黑/白、用户黑/白）在permissions.commands的register循环注册，另见第2节。记录数不是所有别名的总数。

| 模块文件 | 处理函数 | 注册类型 | 命令/匹配表达式 |
|---|---|---|---|
| [AliceUID/nikke_calendar/commands.py](AliceUID/nikke_calendar/commands.py) | `calendar_command` | on_command | `日历` |
| [AliceUID/nikke_character/alias_commands.py](AliceUID/nikke_character/alias_commands.py) | `add_alias` | on_regex | `^(?P<character>.+?)(?:新增\|注册)别名(?P<alias>.+)$` |
| [AliceUID/nikke_character/alias_commands.py](AliceUID/nikke_character/alias_commands.py) | `alias_query_suffix` | on_suffix | `别名查询` |
| [AliceUID/nikke_character/alias_commands.py](AliceUID/nikke_character/alias_commands.py) | `alias_query_command` | on_command | `角色别名查询` |
| [AliceUID/nikke_character/commands.py](AliceUID/nikke_character/commands.py) | `nikke_character_cmd` | on_command | `练度` |
| [AliceUID/nikke_character/commands.py](AliceUID/nikke_character/commands.py) | `nikke_character_suffix_cmd` | on_suffix | `练度` |
| [AliceUID/nikke_character/commands.py](AliceUID/nikke_character/commands.py) | `nikke_character_panel_cmd` | on_command | `面板` |
| [AliceUID/nikke_character/commands.py](AliceUID/nikke_character/commands.py) | `nikke_character_panel_suffix_cmd` | on_suffix | `面板` |
| [AliceUID/nikke_community/commands.py](AliceUID/nikke_community/commands.py) | `community_command` | on_command | `自动社区` |
| [AliceUID/nikke_community/commands.py](AliceUID/nikke_community/commands.py) | `immediate_signin` | on_fullmatch | `签到` |
| [AliceUID/nikke_community/commands.py](AliceUID/nikke_community/commands.py) | `enable_full_signin` | on_command | `开启全量签到` |
| [AliceUID/nikke_community/commands.py](AliceUID/nikke_community/commands.py) | `signin_query` | on_command | `签到查询` |
| [AliceUID/nikke_database/commands.py](AliceUID/nikke_database/commands.py) | `database_update` | on_command | `数据库更新` |
| [AliceUID/nikke_help/commands.py](AliceUID/nikke_help/commands.py) | `nikke_help` | on_command | `帮助` |
| [AliceUID/nikke_login/commands.py](AliceUID/nikke_login/commands.py) | `nikke_login_cmd` | on_command | `["登录", "登陆", "绑定账号"]` |
| [AliceUID/nikke_login/commands.py](AliceUID/nikke_login/commands.py) | `nikke_relogin_cmd` | on_fullmatch | `["重新登录", "重新登陆"]` |
| [AliceUID/nikke_login/commands.py](AliceUID/nikke_login/commands.py) | `nikke_unbind_cmd` | on_fullmatch | `["解绑", "删除绑定"]` |
| [AliceUID/nikke_login/commands.py](AliceUID/nikke_login/commands.py) | `nikke_account_cmd` | on_fullmatch | `["我的账号", "账号信息"]` |
| [AliceUID/nikke_login/commands.py](AliceUID/nikke_login/commands.py) | `nikke_cookie_cmd` | on_command | `["导入cookie", "导入Cookie", "绑定cookie"]` |
| [AliceUID/nikke_login/commands.py](AliceUID/nikke_login/commands.py) | `nikke_public_cmd` | on_fullmatch | `["公开", "公开账号"]` |
| [AliceUID/nikke_login/commands.py](AliceUID/nikke_login/commands.py) | `nikke_private_cmd` | on_fullmatch | `["隐藏", "隐藏账号"]` |
| [AliceUID/nikke_login/commands.py](AliceUID/nikke_login/commands.py) | `nikke_list_cmd` | on_fullmatch | `["账号列表", "绑定列表"]` |
| [AliceUID/nikke_permissions/commands.py](AliceUID/nikke_permissions/commands.py) | `group_query` | on_command | `群查询` |
| [AliceUID/nikke_permissions/commands.py](AliceUID/nikke_permissions/commands.py) | `group_mode` | on_command | `群策略` |
| [AliceUID/nikke_profile/commands.py](AliceUID/nikke_profile/commands.py) | `nikke_profile_cmd` | on_fullmatch | `["信息", "名片", "个人资料"]` |
| [AliceUID/nikke_profile/commands.py](AliceUID/nikke_profile/commands.py) | `nikke_profile_refresh_cmd` | on_fullmatch | `["刷新信息"]` |
| [AliceUID/nikke_resource/commands.py](AliceUID/nikke_resource/commands.py) | `update_resources` | on_fullmatch | `更新资源` |
| [AliceUID/nikke_roster/commands.py](AliceUID/nikke_roster/commands.py) | `card` | on_fullmatch | `["卡片", "阵容卡片", "妮姬卡片"]` |
| [AliceUID/nikke_roster/commands.py](AliceUID/nikke_roster/commands.py) | `refresh` | on_fullmatch | `["刷新面板"]` |
| [AliceUID/nikke_status/commands.py](AliceUID/nikke_status/commands.py) | `nikke_boss_health_cmd` | on_command | `会战血量` |
| [AliceUID/nikke_status/commands.py](AliceUID/nikke_status/commands.py) | `nikke_resource_status_cmd` | on_command | `资源查询` |
| [AliceUID/nikke_uid/commands.py](AliceUID/nikke_uid/commands.py) | `nikke_bind_uid_cmd` | on_command | `["绑定UID", "绑定uid"]` |
| [AliceUID/nikke_uid/commands.py](AliceUID/nikke_uid/commands.py) | `nikke_my_uid_cmd` | on_command | `["我的UID", "我的uid"]` |
| [AliceUID/nikke_uid/commands.py](AliceUID/nikke_uid/commands.py) | `nikke_clear_uid_cmd` | on_command | `["解绑UID", "解绑uid"]` |
| [AliceUID/nikke_union/commands.py](AliceUID/nikke_union/commands.py) | `nikke_union_cmd` | on_command | `["出刀", "查刀", "联盟突袭", "突袭"]` |

与真实Core端点或社区响应发生变化时，优先补充构造回归和明确的字段校验，再更新映射；不要用旧图片、静态图库或猜测值填补缺失的私人数据。

## 16. 1.0.04新增接口与运行约定

- community/schedule.py：valid_time只接受24小时制HH:MM；默认08:33。ValidatedStringConfig在成功保存后调用runtime.apply_sign_schedule，更新原aliceuid-community任务，不新增重复job；修改时间不清空账本。
- community/cycle.py：周期起点08:00；自动执行时刻与周期边界分开。每天cron按Asia/Shanghai，长批次跨周期终止。在途响应跨界（成功/异常）通过carry_boundary_guard保守记录新周期请求与写入约束，不直接生成签到确认。
- community/store.py：新增signin_confirmations（account/day/owner/确认时间/来源）和group_seen（群摘要/聊天用户ID/最近观察时间）。last_day仅表示整轮处理；群查询只有独立确认记录才显示已签到。
- 旧23:00周期迁移没有逐请求时间戳，因此将可能重叠的旧预算与动作保守带入第一个08:00周期，标记legacy，不制造签到确认。服务可做任务状态检查，但不重复结果不确定的写入。
- community/report.py与runtime.report_group：Core Bot主在当前群查询，按bot_id与群作用域筛选AliceBind和近期观察记录，40条分页；不调用社区、不过问成员Cookie。没有Core统一实时群名单时明示范围，不能把绑定群记录称为全群实时成员。
- nikke_user/auth_state.py：known_invalid/mark_invalid/unavailable_message统一失效状态。load_client在解密与缓存命中前检查明确过期或已知无效；客户端只对401/300001写失效标记，403/429不写。标记按owner与cookie_enc摘要隔离，重登新revision不继承。
- 新配置键AliceUID_CommunitySignTime；新聊天命令nk签到查询[页码]。原nk签到改为精确匹配，避免与新查询命令重叠。
- 当前源码工作区的Python解释器、45个依赖包和环境验证入口位于CodexZone/DevelopmentEnvironment。读取environment.json中的相对路径与-I -B参数，具体说明见该目录README；不再依赖GptZone或宿主site-packages。
- 共享数据根现在只有AliceUID主树，新增3个公开元数据JSON；1207张PNG和27项固定装饰图标已核验。旧NikkeUID/private_preview仅归档，用workspace_paths中的legacy_private_preview_root继续做发布隐私检查，不合并到运行账号数据。

1.0.03的1188通过数字是历史功能基线；1.0.04的测试和资源迁移是上一版基线；当前1.0.05以本轮handoff验证记录为准。

## 17. Core原生前缀与旧配置迁移（1.0.13）

`nikke_commands.configure(plugin, config_path)` 必须在所有SV注册与StringConfig读取前执行。使用Core公开的 `plugin_config_store.get/set/save` 接口保留完整权限配置，只迁移前缀字段。已有原生prefix、禁用默认前缀或空前缀配置时优先保留Core设置；未定制时把旧CustomPrefix映射到prefix，把DisableDefaultPrefix映射到disable_force_prefix。保存失败中止初始化且恢复内存，不写成功标记。

迁移记录 `prefix_migration_v112.json` 保存旧的三个前缀值与结果，不复制账户配置或凭据。完成后删除旧WebUI控制项，后续不再重放旧值。1.0.13在任何SV注册前调用公开的 `plugin.set(prefix=..., disable_force_prefix=..., allow_empty_prefix=...)`，同步已存在的Plugins对象；全新安装先建立Core配置记录。fix1参照XWUID，调用Core公开的 `get_plugin_available_prefix(plugin.name)` 读取已同步对象，移除自定义effective_prefixes算法；`command_prefix()` 返回与本次启动注册一致的前缀快照，默认优先nk，禁用默认时使用第一个Core自定义前缀。Core已有配置优先；修改前缀须完整重启，帮助缓存随内容指纹自然失效。

`bind_triggers()` 已移除，不修改 `SV.TL`、不构建 `Trigger`、不调用 `bump_registry_version`。Core原生负责空格解析和注册元数据，四名单包装及 finally 保留。旧版1～12位校验只用于迁移旧数据，不限制Core的新配置。


## 1.0.09：DILDORO实验性推荐与通知隔离

新增 `nikke_solo`，流程与依赖见其 `MAINTENANCE.md`。`owned_account`使用本人已绑定客户端读取保存角色及GetUserInfoNew分享标识，区分登录openid与分享openid；网站端使用独立无Cookie的非持久上下文。生产不执行下载到工作区的参考JS，所有计算仍由网站UI完成。

`nikke_community/notifications.py`新增SQLite表notify_routes与notify_receipts，与既有签到账本共用事务。路由由有效群命令事件记录Bot类型、机器人自身ID、群ID与WS连接；发送使用Core现有target_send和回执。通知唯一键包含Bot类型、自身ID、群ID、签到周期；发送前预留unknown，确认后改delivered，未知不自动重发。同一机器人换WS连接更新路由，不重复发送同周期消息。

调度按账号运行一次，每个账号结束后检查已知群；同群目标仍在途/未执行时不发完成通知。成功依据signin_confirmations，不依据last_day或completed标签；无法确认的结果另列未确认。每群只汇总自己的绑定/近30天命令观察成员，不把未记录成员归入未开启。跨08:00或全局社区暂停停止本轮通知。

`notify_policy.py`的3个配置键仅由签到通知发送路径读取。默认全局开启、两表空；白名单非空即限定范围并覆盖重叠黑名单；白名单为空才按黑名单排除。群号只接受ASCII数字字符串，名单重叠有效；原业务四名单的冲突拒绝规则不变。通知仍检查Core插件/SV开启、群范围和名单，以及AliceUID既有群策略。全局关通知不撤销账号签到授权、不改scheduler、不影响查询。

待实机：网址同步对每个实际区服的响应、网站更新/限流条件、真实推荐完成时长、用户环境的Playwright与QQ通知回执。没有实现自动修改公开设置或自动JSON备用导入。


### candidate2独立主题

个人突袭卡片使用独立的AliceUID_SoloCardTheme（dark默认、light、random），不读取AliceUID_CardTheme。命令可携带亮色/暗色/随机参数，仅覆盖本次渲染；未指定时读取独立配置。色板仍来自nikke_render.theme，随机只选择一次。apply_theme继续捕获全局GlassStrength并生成预模糊场景；hero、notes、shot-panel使用container_glass及共用glass_finish，网站截图在960px内容宽度和原DPI下保持原色，四角遮罩不变。卡片外宽1072px，为截图外增加15px毛玻璃衬边。


### 1.0.09 candidate3：截图裁切与本地缓存

nikke_solo.service.capture_result保留网站左栏原宽，隐藏外围并整体等比放大至960 CSS像素；不再独立拉宽fg-set。使用1.5 DPR、等待字体及头像解码，验证五队/25格/伤害/标题边界，失败不截图。tests_alice/test_v109_crop_fix.py使用冻结的真实CSS和compact卡片DOM还原白色右栏，证明旧实现会混入外围像素，修复在900/1280/1600窗口均不越界。最终亮暗样张共用此裁切链路。

nikke_solo.cache保存本人账号/区服/Bot/凭据修订隔离的PNG和原子元数据。120小时固定有效期，读取不续期；每身份最多8个样式。普通指令优先本地命中，刷新指令强制重新计算，失败不把旧图作为新计算发送。重新登录/解绑清理接入原有_invalidate_replaced，过期回收复用每小时本地清理任务。保存和发送之前复核权限、绑定及已知凭据状态；所有验证使用离线数据，不执行真实账号操作。

## 1.0.10：主线 Hard 关卡显示

`StaticData.stage_name()`补全` HARD BOSS`后缀处理；`48-36 HARD BOSS`归一化为`48-36`。普通关卡、困难普通关卡、分支关卡和未知ID回退保持原有行为。卡片标题、字号和布局不变。

## 1.0.10 fix1：统一账号快照与命令边界

`save_login()`确认数据库写入成功后，经`_start_login_prefetch()`调度`panel_refresh.schedule_login_prefetch()`，初登、重登及Cookie导入共用入口。任务按user_id/bot_id去重并记录panel_identity，登录结果不等待缓存完成。纯登录背景任务无Bot实例，不发消息、不调用图片渲染；1.0.11允许合并其间的手动请求，在任务成功后发送一张信息图。失败不回滚已成功的绑定。

`refresh_panel()`在角色账号锁内获取profile._fetch的五个资料接口；从返回的本人角色列表取name_code，每批最多20个获取详情，每事务最多5个请求，5秒间隔、全局两槽及300秒任务上限。500角色是本地任务保护预算，不代表上游API限制。响应必须覆盖每批全部唯一角色，皮肤字段原样保留。全部成功后在绑定锁内复核绑定、权限、epoch，将profile/roster/details/complete一次性原子写入；失败保留旧完整快照，不自动重试。快照16MiB上限在写前检查。

`ensure_profile()`先等同绑定正在进行的预缓存，再读取完整持久快照；缺失时只补建一次。生产RosterService通过snapshot_provider注入该入口；普通图鉴流程只准备公共图片并按既有指纹复用或渲染。`_profile_data()`同样使用该快照，不再600秒自动取数或使角色缓存失效。1.0.11的`nk刷新信息`与`nk刷新面板`共用queue_refresh，全量重取后输出信息图。

角色查询恢复同一快照的roster/details，持久数据无TTL；只在显式角色更新或缺少该角色详情时访问玩家接口。`nk刷新角色名面板`仅更新目标角色的角色行和详情，同时更新profile.chars中对应行，保留其他角色和个人资料。查询发布复核绑定和权限，图片写入检查快照saved_at，解绑或更新后旧渲染不写回缓存。

1.0.11保留fullmatch“刷新面板”，suffix“面板”遇到完整“刷新/更新”时直接返回；“刷新角色名”去掉开头的“刷新”后调用单角色refresh=True。删除suffix“面板更新”。“刷新信息”只注册一次，委托同一账号队列。旧“练度角色刷新/更新”不执行刷新，仅给新用法。所有前缀由既有nikke_commands配置统一管理。

验证入口：tests_alice/test_v110_account_cache.py、test_character_commands.py、test_roster_refresh.py及test_v110_stage_name.py；完整回归和交付记录位于当前handoff。


## 1.0.11：通用帮助缓存与刷新完成图

`nikke_help.cache.HelpCache`只保留public/owner两组PNG和JSON，缓存键不含个人身份；help.commands不查询AliceBind，help.html不包含commander.html。权限严格整数0才是Bot主，其余为普通图。30天TTL以成功生成时间为起点，命中不写入；首次/过期重建随机选择light/dark，并保存实际主题。每角色级别异步锁保护读-重绘-写入，避免同时请求重复渲染。元数据记录内容/渲染配置指纹及PNG SHA256，先原子写图再写元数据；损坏、不匹配或系统时间回拨均重新生成。升级版本、帮助内容或语言/字体/毛玻璃/DPI变化提前失效；图片失败沿用文字回退。帮助图独立随机主题，不随全局CardTheme每次重绘。

`profile.send_profile_image`由普通信息查询与全量刷新完成共用，直接使用本次返回的数据，不重复获取账号资料。渲染前捕获epoch，发送前在绑定锁内复核绑定修订、epoch及用户/群权限；不发送已过时图片。单角色与图鉴不在全量刷新时渲染。完整快照写入后出图/发送失败明确标注数据已经刷新，不宣称回滚。

`panel_refresh._manual_requests`保存当前账号任务的首次手动通知目标；纯自动预缓存不出图，手动请求加入后成功完成会出图。重复命令合并，仍沿用账号隔离、请求节流、失败保留旧完整缓存、解绑撤销与重登录修订机制。回归入口为test_v111_refresh_help.py、test_character_commands.py及原持久账号缓存测试。


## 1.0.11 fix1：可配置的实际回执等待

新增`AliceUID_ForwardReceiptSeconds`，默认30，整数5～300；Web配置写入验证，运行时坏值回落30。转发前读取一次，当次等待不受之后配置变化干扰。

`nikke_message.receipt`在当前连接的已知Python `target_send`上安装一次包装。常规调用直接执行原函数；AliceUID转发通过ContextVar携带(transport, seconds)，只有同连接且wait_recall=True的本次调用才用FunctionType浅拷贝globals后的原始代码，替换其RECALL_WAIT_TIMEOUT数值。echo序号、Future字典、队列、回执能力探测和finally清理全部沿用Core实现；不改Core文件或全局常量，不绕过原Bot.send及_LiveAccessBot。ContextVar在finally复位，并发其他插件仍使用原等待值。未知Core方法结构无法覆盖时明确记录日志并沿用实际Core等待值，不假称配置生效。

连接暂停固定60秒，继续一次普通回退。如果本次发送将原非False的_supports_recall锁为False，只为该连接保留可重试标记；暂停到期且仍是同一transport时恢复None及计数器，允许下一次正常转发探测。调用前已不支持回执的连接不自动改动。暂停表上限64，随条目淘汰清理重试引用。

离线测试执行冻结Core原函数，控制回执在模拟第20秒/45秒到达，确认实际wait参数为30/60且没有普通回退；验证即时配置变化、并发其他插件10秒隔离、60秒边界恢复、取消清理、权限拒绝和既有完整原图字节。不会因本修复重绘出刀或修改180秒联盟快照。日志只记录时长/确认状态，不重复输出图片Base64。

## 22. AI只读查询（1.0.12）

四个原生to_ai入口：nikke_help、nikke_profile_cmd、nikke_character_cmd、alias_query_command。每个入口提供to_ai描述、covers和aliases；不重复注册ai_tools，不修改Core代码。默认AliceUID_AIQueryEnabled关闭，to_ai描述为空，不注册AI工具。须同时开启插件开关与Core AI并重启完成注册；插件开关可即时关闭调用。普通命令不加载AI引擎；插件仅在Core已创建MockBot时进入AI适配分支。

装饰顺序为 `@sv.on_*(..., to_ai=...)` 在外、`@ai_query(sv)` 在内，确保Core捕获的是已检查权限的函数。原来的启动后Trigger.func包装不能覆盖AI保存的函数引用。AI适配补齐Core命令路径的插件/SV名单、范围、权限以及全局黑名单，再检查AliceUID四名单；每次返回结果时复查。Core权限规则与固定源码handler._sv_authorized做离线等价验证。

资料/练度/别名仅选取显示字段产生摘要，不输出Cookie、Token、openid、原始响应或图片Base64。摘要暂存于当前调用ContextVar，在业务完成绑定核验并提交图片到MockBot时才调用Core ai_return；渲染失败、解绑/换绑定或撤权时不返回暂存摘要。帮助走纯文字指南，避免AI调用转发或等待真实回执。图片由Core资源管理器登记后返回资源ID，最终是否发送由Core AI决定；本插件不绕过Core发送机制。

DILDORO、刷新、登录、解绑、签到等没有to_ai注册。DILDORO代码、模板和缓存均按父版哈希保护；Playwright保留为网站JavaScript交互与真实DOM截图依赖。常规卡片原先已使用render_html_to_bytes，本版不声称新增20倍性能提升。

本版离线契约固定Core `f0fea6f935c34ce05a235352ecdb6f30ba848b43`，源文件与两份官方技能文档的哈希位于开发.references/gscore_v112。测试隔离模型、发送、存储与网络边界，不启动完整Core或调用真实AI服务。实机还需核验Core版本、WebUI迁移、自然语言召回与QQ图片发送。

## 23. 本地Core完整注册链路核对（1.0.13）

依据用户本地仓库提交 `131f64af45c53db879d7f10b6300959a06ac1831`。原始文件及SHA256保存在开发.references/gscore_v113，不修改Core仓库。与前版只分别检查迁移和触发器的方式不同，本版使用原始GsServer.load_plugin/cached_import加载临时plugins/AliceUID，并使用原始PluginConfigStore、Plugins、SV、Event、Trigger和TriggerIndex；这些模块不经AST删改或替身重写。只隔离日志、Bot发送、插件数据库/业务接口和调度等外部边界。

反馈中的“同名Plugins返回对象后不再运行__init__”未在该源码中复现；Python调用现有实例时仍运行其__init__，原始1.0.12两种冷启动已能注册自定义前缀。但1.0.12的configure返回时，帮助快照已更新、对象前缀尚未同步，需要依赖随后SV补载。1.0.13在首次SV之前明确同步这两者。对照测试保留原版真实表现，不把没有复现的冷启动故障写成已证实原因。

后台update_plugin_field使用plugin.set(False, ...)，保存字段不重建Trigger/候选索引。测试先验证保存后仍使用旧触发器，再从磁盘重新加载Core配置与插件，确认新前缀命中、旧前缀退出、服务数量不增加、帮助和登录提示同步。部署者修改前缀后仍须完整重启Core。

测试依赖boltons 26.2.0、msgspec 0.22.0、toml 0.10.2按本地Core的uv.lock固定，仅安装在本版.runtime/core_contract_packages，未修改共享45包环境，不加入插件安装包。测试并非已启动的完整Core服务或QQ实机验收。

### 1.0.13 fix1：与XWUID共用Core的显示前缀接口

XWUID在SV配置加载后调用get_plugin_available_prefix；AliceUID保留迁移兼容和首个SV前同步，在同步完成后调用同一Core接口。仅在启动时取值，避免WebUI保存字段后尚未重建触发器时帮助文案提前切换。用户无需配置新的插件前缀选项，仍在Core插件管理中设置。

已固定XWUID main提交bf74531c9caadbc576613d18bd1cd367bfc93183的相关源码于开发.references/xw_prefix_bf74531。对照测试不执行XWUID数据库、后台循环或迁移操作。新增契约检查验证getter调用时对象已同步，并验证帮助结果确实来自Core接口。


## 1.0.14 收菜提醒

`nikke_harvest`分为planner、store、service、runtime、commands。账号共享进度与会话订阅分离，SQLite位于MAIN_PATH/harvest.sqlite3；从Core共享scheduler注册aliceuid-harvest（30秒本地扫描，max_instances=1/coalesce），只有到期且已授权的账号请求上游。账号锁、持久化租约及原AccountReads共同限制重复请求。

`ResourceStatusService.query(fresh=True)`提供提醒专用新鲜数据入口；默认参数与资源卡300秒图片复用行为不变。资源上下文新增fetched_at_epoch。开启命令单独使用原draw_status渲染同类资源卡，后台fetch不调用渲染器。手动查询通过prepare_image的on_snapshot回调，在数据读取成功、渲染之前更新已开启的共享预测及待执行时间；渲染失败也不丢失已获得的新数据。缓存图片命中不触发回调；旧时间戳被拒绝，提醒模块异常隔离，不影响原资源卡。等待MAX时仅重排那一次检查，手动已查到MAX则取消多余后台查询，不自动授权或恢复停用账号。

nightly表按账号/北京时间日期唯一，23:00～24:00为当晚分批采样窗口；原始100%才算MAX，相邻两个有效夜晚触发AUTO_STOPPED，不能用旧缓存、失败或午夜后的样本补填。关闭账号取消各群/私聊的业务待发消息，一次性停用说明用独立事件收据。重开只恢复命令所在会话。

通知按每会话/轮次唯一，发送前重新验证订阅代次、账号绑定、Core插件/SV权限、全局黑名单、AliceUID四名单、路由和免打扰。群消息是文字与原生at段，私聊无群@；按群最多5人分批，跨群同账号共用一次查询。发送结果不明不自动再次@。收菜免打扰不接管任何全局发送入口。

离线回归：tests_alice/test_v114_harvest.py与test_v114_harvest_integration.py；涵盖状态机、Core真实注册、命令开启卡片、群/私聊路由、去重、午夜、连续两晚停查与关闭竞态。实机范围记录于handoff。


## 1.0.15 本地练度Excel导出

入口 nikke_export.commands：精确命令“练度全量导出”，block=True，避免Core继续分发通用练度命令；通用练度处理器也保留该关键词的无请求退出。遵循原生前缀，无AI工具注册。

流程：本人AliceBind → wait_for_refresh → binding_lock内读取PanelCache完整快照和epoch → 有界asyncio.to_thread生成 → binding_lock内复核本人绑定版本、Core/插件/SV及四名单、saved_at和epoch → MessageSegment.file(bytes, filename)。不开NikkeClient、不ensure资源、不渲染HTML、不写用户成品文件到磁盘。不支持代查或任意UID。缓存仍按panel_identity包含所有者/平台/账号/区服/凭据版本隔离，失效凭据不自动联网，绑定有效且缓存完整即可离线导出。

model.py调用build_character_context与aggregate_options，保留原有Decimal单位和蓄速/命中正向显示。最终攻防生命无经确认字段，输出“未提供”。未知词条保留文字状态。Excel字符串按字面写入，关闭自动公式/URL识别；UID为文本，文件名替换非法字符。

workbook.py：XlsxWriter>=3.2.9,<4，无宏/外部链接，两张工作表。总览A:E/G:K构成六个视觉区域，词条拆成名称/数值/阶数。明细原生Excel Table；隐藏辅助列用IF/AND/OR/COUNTIFS/ROW计算匹配序号，总览用INDEX/MATCH/IFERROR按序读取。默认结果写入公式缓存，设置auto/fullCalcOnLoad；非动态数组、不依赖FILTER或VBA。排序辅助使用当前ROW与固定范围，避免明细排序后引用旧行。所有条件均在文件内操作，全阶段匹配Ⅰ/Ⅱ/Ⅲ。过滤后尾部预留空白区域保留，未使用宏隐藏工作表行。

默认500名角色、12MB文件上限，同时最多2次生成，同一QQ/平台并发请求不重复。生成取消时等待本地线程完成后释放占用。只使用当前bot发原生文件消息，不转发、不换群、不自动切私聊，不建立新的后台任务。失败日志只含异常类型。发送无确认时不宣称已成功收到。

验证：tests_alice/test_v115_export.py、test_v115_export_integration.py；tools_alice/verify_v115_workbook.mjs使用开发工具导入真实导出文件、重算并渲染，不属于插件运行依赖。QQ上传和具体Excel/WPS客户端不在离线验收范围。

local.py只读并验证本地static/cubes、static/collections元数据，通过NoImages与LocalMetadata复用现有equipment_info；绝不调用下载。保留原始等级，SSR珍藏品显示等级按原面板+1规则，适用角色/武器不匹配时不伪造有效等级。元数据缺失时保留ID和原始等级。


## 1.0.16 紧凑表头

仅修改nikke_export/workbook.py的布局与引用。VIEW_FIRST=5（首对角色从第6行开始），冻结前5行，打印重复1～5行。主标题16pt，首行28pt，第2～5行22pt，总计116pt；父版表头210pt，减少约44.8%。

身份信息与时间保留在A2:F2、A3:F3，词条图例A4:F4。G2/G3/G4为爆裂阶段/企业/角色定位；H2/H3/H4为单格下拉；I4:K4显示匹配与导出数量；A5:K5显示原说明或空结果提示。数据明细页维持原有表格/筛选/冻结位置，仅同样缩小主标题。

筛选匹配公式统一引用H2/H3/H4，隐藏选择序号和角色索引逻辑不变。既有test_v115_export中的工作簿契约更新为新坐标，集成测试保留。verify_v116_workbook.mjs使用实际1.0.16示例重算全部筛选与源数据重排并生成预览。


## 1.0.17 属性筛选与可读性

G5/H5新增属性条件，来源为既有build_character_context与_LABELS规范化属性；H5支持全部、燃烧、水冷、铁甲、电击、风压、未知。model.matches增加可选element参数，保留原三参数兼容。明细_match用与其他条件相同的INDEX/ROW固定区间读取属性，联合四条件后由既有_rank/MATCH重新排列总览。

总览I2:K2两行说明（9pt），I3:K3已导出人数，I4:K4动态符合条件人数，I5:K5无匹配时显示提示。第1～5行高度26/28/20/20/20pt，共114pt，继续冻结和打印重复五行，角色从第六行开始。

词条B:D及H:J在每张卡内连续按淡灰F0F2F5/白FFFFFF交替，数值百分比和绝对值格式不变；装备及汇总的合并色块保留。空角色条件格式先于高阶样式，空结果区保持空白；绝对值格式规则用IF保护零索引。明细表显式交替底色，保留原生表格排序与列筛选。

验证包含原导出回归、test_v117_export.py与verify_v117_workbook.mjs；示例全为虚构数据，五种属性、未知、组合、零结果和源行重排均重算验证。Artifact Tool用于开发验证，不是插件依赖。具体Excel/WPS客户端和QQ上传仍需实机验收。


## 1.0.18 签到状态与通知

lifecycle.py为CommunityStore的持久化扩展：signin_runs按账号/凭据所有者/08:00周期保存尝试、结果、下次时间和连续数；accounts新增generation/fail_count/fail_day/auto_disabled。同日失败幂等、相邻周期累加、成功清零。用户授权变更递增generation，旧任务结果按generation和attempts核对后才能提交。自动关闭保留原likes选项；明确手动关闭取消自动恢复资格。

自动任务保留日cron，并在Core共享scheduler添加60秒本地重试/通知检查。只处理已持久化的到期待重试账号，不额外开启任务或提前签到；只读/未发出的连接失败最多3轮，延迟120/600秒，窗口1200秒。所有请求仍计预算/间隔。写请求结果不明保留动作预占，只通过任务列表复核，禁止重复POST；仅ConnectError/ConnectTimeout/PoolTimeout证明未发送时释放该次签到预占。429、403和认证错误本轮不自动重试，不立即关闭账号。跨周期停止，保留原边界保护。

社区专用load_client(community=True)不因历史服务端失效标记直接拒绝正常任务状态读取，仍拒绝本地过期/损坏凭据；社区单次认证异常不写入通用永久失效标记。普通查询入口保持原保护。没有新增保管箱或个人资料探测。

同账号save_login在验证Cookie持久提交后、撤销旧任务前，按旧owner/generation有条件移交授权。签到确认/动作/预算保留，只有原开启或consecutive_failures状态恢复。登录成功状态回复读取持久化恢复说明；恢复失败不伪装登录失败或恢复成功。

notifications.py保留成员详情和每周期分页快照，10人/约1800字符分段；各页发送前预占回执，模糊回执不重发。signin_checked记录日批次曾处理的账号，避免60秒检查在每日定时前发送汇总。系统当天关闭仍计入异常名单。查询状态与群汇总共用本地结果，不加载其他成员客户端。

notify_state.py保存全群初始策略和按bot/self_id/group的覆盖。后台布尔值实际改变时通过持久pending操作准备、配置保存、提交批量代次；中断后按保存的配置恢复或撤销。整页保存同值不清除覆盖；全群命令可显式重复应用同值。旧名单在Core规范化配置前保存备份并导入初始策略，此后移除可编辑入口，不改业务权限四名单。

## 1.0.18 收菜通知修复

通知ID由会话:轮次升级为会话:轮次:normal/bed/full，保留旧回执及明确cycle字段；重启不会重复提醒。normal在90%以上触发，full在99%以上触发，原始容量不被修改。下一次满仓检查为snapshot.full+60秒，低于99%则继续按新预测+60等待，临时MAX读取失败5分钟后再查。免打扰中的满仓事件延到可通知会话的最早结束时间，并重新查询避免用户已收取后的旧提示；手动新鲜查询可提供MAX观察，但不消费满仓通知配额。

旧WAIT_MAX预测时间与旧WAIT_REARM缺失full通知的账户做一次stages_v118迁移，旧通知状态不清空；开启卡已展示的阶段视为当前会话已通知。两晚自动关闭仍按原始100%判断，不把99%容差用于自动关闭。关闭/绑定变化/权限和实际路由复核沿用原实现。

验证使用模拟HTTP、时钟和真实临时SQLite；详见test_v118_upgrade.py及继承回归。运行中真实QQ/社区/后台验收需单独记录。


## 1.1.12 按排名查刀与成员快照

parse_request仅在详情路径将ASCII正整数解析为排名，普通出刀Day1/Day2规则不变。全程只加载发送者本人凭据；target_rank只在已核验本人联盟的完整快照中选成员，不加载目标账号Cookie或访问目标私有面板。排序与速查rows一致（伤害降序、刀数降序、昵称、成员ID），同伤害稳定排序，零刀也可定位。无数字保留本人路径；越界给出现有榜单人数和有效范围。

持久成员库沿用UnionHistory的工会/产品/区服/赛季JSON快照，members保存完整名单，attacks保存所有成员阵容、伤害及外观；不另建重复账号库。内存_guild_cache共享同工会当前快照，_cache只是本人身份租期；进行中同时检查原数据_cached_at，晚到成员不能顺延180秒。已有账号在租期内可读取同工会更新的快照。休赛期已结算数据仍通过现有finalized路径长期复用，本人联盟/当前成员确认保留短TTL；赛季阶段改变、换工会、刷新及凭据变化均触发原有核验。数据源没有任何记录时继续显示真实未知，不把空响应捏造成零刀。

raid_active取官方赛季时间，构建器统一产生status/status_color，所有视图共用；missing_columns均分名单，保证16人8+8，32人16+16。模板只显示选中目标，卡片内容指纹包含排名/成员/快照，避免本人图误用于他人。


## 1.1.13 总览别名修复

nk出刀与nk查刀在同一个on_command四项元组注册到nikke_union_cmd(bot, ev)，默认view=quick，不再通过另一个已装饰函数传入detail_alias关键字。本人/按排名阵容使用nk出刀详情[数字]；别名后参数沿用出刀解析器，查刀1为Day1，不再是伤害第1名。180秒共享数据、休赛期持久快照、阶段配色及双列逻辑未变。

根因：Core SV._on返回wrapper(bot,msg)，旧nikke_union_lookup向这个wrapper传detail_alias=True，触发TypeError；旧边界测试把装饰器模拟为原函数，漏掉了这一差异。本版边界测试执行冻结Core真实_on与Trigger，复现旧失败并验证出刀/查刀、详情、刷新、权限和单次路由。

帮助第1行并列出刀/查刀，第3行仅列出刀详情[排名]，更新帮助缓存版本以替换旧帮助图。滑刀统计仅保留开发笔记，未增加命令、WebUI配置或统计模块。


## 1.1.14 日历驱动数据库更新

calendar_update.py匿名POST固定GetCalendarDetail（请求体{}），仅解析data.character_gacha.items的start_time/end_time/characters.name_code/resource_id。无Cookie/Token，不调用订阅写接口；不运行时下载JS。日历截图路径保持。日历状态保存database/calendar_update.json，事件身份由起止时间和角色集合摘要确定。首次启动忽略已结束事件，当前缺资料角色立即补查；后续新公告、起止边界与改期重排。

Core共享scheduler新增aliceuid-database-calendar，60秒本地检查、启动即检查，max_instances=1/coalesce/replace_existing。无活跃任务时6小时取日历；到边界强制刷新，活跃窗口每小时取日历/资料。所有到期事件合并进同一持久周期，不建立每群/每角色网络任务。与manual/weekly共用DatabaseService所有者锁，busy不算完成或无新增。

等待发现窗口24小时，不因普通资料变化续长。name_code目标全部有角色行、匹配ID映射及技能图标才进入observing；不存在明确目标的旧池结束事件等待新角色编码。获取资料后一小时再次检查规范化角色/ID/技能/头像表摘要，稳定即结束；有变化再观察一小时，截止附近的新资料保留一次后续确认。空响应、网络/格式错误或冷却不作为稳定。源错误持续到截止记录source_unavailable；正常检查但未齐记录timeout。处理过的事件保留去重，完成后重新取日历排期，重启不重复小时检查。

DatabaseService先更新全部7张结构化表，再_plan及原子保存manifest的structured_checked_at/structured_tables，发布structured_ready进度后才处理图片。任一结构化表fallback/cooldown则发布structured_incomplete并保留旧表/队列，停止本轮图库请求。日历判定使用结构化表状态与本地内容，图库错误/旧皮肤队列不冒充角色缺失。沿用原每批/下载字节/磁盘/总时长预算和有效图片复用。

后台DatabaseCalendarUpdate默认True，独立于周检；日历任务不持有Bot、不提供发送回调。只有用户主动数据库更新状态时显示北京时间排期/阶段/上轮结果。该状态文件及运行数据不打包。
