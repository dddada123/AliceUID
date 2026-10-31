# 资源与会战状态卡（1.0.04）

## 当前版本 1.1.03（覆盖下方旧缓存描述）

- 私人查询在缓存之前检查本地过期与已知失效凭据版本；HTTP401/业务登录失效统一提示nk重新登录/重新登陆。403和429保留拒绝/限流含义，未当成Cookie必然过期。

- nk资源查询按发命令用户+bot+游戏账号+区服+凭据版本隔离；只有成功生成并校验图片后才起算300秒复用窗口，显式刷新不绕过。没有成功图或图被淘汰时重新获取数据并渲染，不因上一次失败锁5分钟。普通故障冷却5秒，403/429冷却60秒，均独立于成功窗口。ResourceCacheSeconds仅保留兼容。
- prepare_image工作锁覆盖取数与渲染，_ready字节内存总上限24MiB；命中不续期，包含风格校验。发送失败保留已生成图片供下次重发；取数/渲染/图片校验失败不提交_ready。invalidation epoch阻止旧在途数据/图片再次提交。
- 首次/到期读取本人basic、outpost、daily，复用账号串行、每请求5秒间隔；正在进行其他本人查询时等候该节流窗口，不因为刚发过nk信息就直接失败。1302127、临时网络/超时及HTTP5xx按整次查询最多三次静默尝试，已成功端点不重复请求；三次均失败才提示可能为网络原因、稍后重试。Cookie失效立即要求重新登录，403/429不自动补查。每次请求前复核绑定与权限；失败不画旧数据或零，未确认1302127官方含义。
- 数据与PNG均按凭据版本隔离，磁盘缓存为私有cache/resource_images；解绑/换Cookie清理，旧在途图片不得回写。新强度进入图片指纹，图片命中先于随机主题。
- 保管箱>70%橙、>90%红、100%MAX；24小时周期从快照按北京时间估算90%与100%，只显示今天/明天HH:mm，未知不推算；不是自动领取，也不是实时推送。
- 阶段标签自适应并横纵居中，状态背景保持比例cover铺满，避免底部白条。全卡强度按0～100%全局设置，只处理背景。
- 流程证据见开发目录docs/research/resource_sync/接口结论.md，自动回归使用构造数据/MockTransport，真实1302127恢复需用户实机确认。

下方保留0.6.0历史接口/素材证据；60秒缓存等旧数值已由上文300秒替换。

指令：nk资源查询 [刷新]、nk会战血量 [刷新]。注册在主入口统一权限包装之前；仅使用发命令者本人登录绑定，忽略@他人。渲染前与发送锁内均检查绑定版本和用户/群权限，Cookie变更或解绑后不发送旧图。

官方来源：
- [主页分包](https://www.blablalink.com/assets/nikke/version/default/assets/home-uhgwaVzg.js)。
- [资料/联盟分包](https://www.blablalink.com/assets/nikke/version/default/assets/union-P4IXFV-5.js)。
- [货币枚举](https://www.blablalink.com/assets/nikke/version/default/assets/setting-D00Crjk3.js)。
- [共享查询store](https://www.blablalink.com/assets/nikke/version/default/assets/index-CGPU0lk3.js)。

开发参考保存在工作区 .references/community/home-v051，source.json有URL、字节数及SHA256；不进入插件安装包。没有使用网页里的其他玩家openid，更没有借其他Cookie。

资源API：客户端既有 GetUserProfileBasicInfo 返回 basic_info.currencies；GetUserDailyContentsProgress 返回 daily_progress[0].outpost_battle_storage_fullness。货币类型：付费98、免费99、信用点2000、黄金积分券12000、白银积分券11000、战斗数据1000、芯尘3000、招募券5100、高级招募券5200。钻石合计98+99；任一组成缺失则未知，不猜成零。容量原始值0～1，显示乘100；隐藏标识-1/-99/-9999或字段缺失不按0处理。

会战API：GetUnionRaidLevelInfo 的 level_info[0]，按官方主页选择首项；difficulty=1普通/2困难，level为阶段。boss_info含boss_id、name_localvalues、max_hp、current_hp。保留大整数精度，剩余比例用整数运算截取两位；max_hp=0为无限血量，不除零或假设100%。总进度按有限血量总和的已削减比例，不当成剩余血量。空结果明确暂不可用，当前接口未标明赛季时不伪造赛季或直播状态。

缓存：UnionService在同一快照保留level_payload，出刀/血量共享账号与已验证联盟缓存及在途锁；先由本人账号确认联盟与成员身份，跨联盟/区服不共享。180秒默认、源时间不滑动续长。资源独立本人/游戏/服/凭据版本快照，默认60秒，在途合并；实际请求走已有AccountReads串行、每次请求间隔5秒、全局两槽。强刷仍遵守冷却，API拒绝/认证失效不自动重试，不以旧数据冒充刷新成功。

图片复用：数据/身份/语言/字体/主题模式/版本入hash；同快照先查图片，再选择随机主题；正在渲染的相同请求共享任务。图片内存LRU上限24MiB，完成任务清除，失败不缓存。纯数据和图片均不写入发布包。

界面：status.html 与其他卡片共享主题token、整页拼接模糊照片及透明色玻璃；子模块没有单独背景照片。新增显式h1/h2/金额颜色，避免原生引擎继承差异导致暗色黑字。底部保留查询时间、来源、缓存秒数及中间署名。资源八图放外壳assets/status，来源哈希经开发工具核对；好感红心是程序绘制的通用几何背景，数字仍用选定字体。

回归：tests_alice/test_status.py；tools_alice/preview_status.py生成亮暗、未知资源、无限血量和未开放状态共10例，每例原生/真实浏览器截图，网络请求为0；暗色金额同时做原生像素检查。完整套件按交付记录为准，构造预览不可标为真实当前玩家数据。
