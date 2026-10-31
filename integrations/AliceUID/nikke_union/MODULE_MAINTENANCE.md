# 1.1.13 更新（优先于历史说明）

nk出刀和nk查刀在同一个on_command元组注册到同一个总览handler；详情及排名仅推荐nk出刀详情[数字]。禁止对Core已装饰函数传detail_alias等额外关键字，真实装饰器wrapper只收bot,msg。真实Core_on/Trigger回归见test_v1113_union_alias.py和test_union_commands.py。缓存/赛季/模板/配色逻辑保持。滑刀仅留笔记。

# 1.1.12 更新

出刀详情可追加本工会伤害排名，无数字查本人；快照排名与阵容同源，0刀显示选中成员及状态。仅用发送者本人登录，工会/区服/赛季隔离，成员及阵容持久化沿用UnionHistory。进行中共享数据默认180秒，晚到查询不延长原快照；休赛期finalized长期保存但仍核验当前工会与名单。进行中：完成绿、未出完蓝、0刀待出刀黄；休赛期保留完成绿/未出完黄/漏刀红。缺刀名单均分两列。

# 联盟查刀模块维护

## 1.0.01 更新（优先于下方旧基线）

支持官方上一期历史接口并标赛季/状态；有赛季名单快照优先使用，没有时保留刚取得的完整当前名单进行对照，补出0/3本人/漏刀并明确新成员历史归属不确定。历史攻击者离会仍保留，不借Cookie或伪造名单。members_reference写入快照，避免当前对照名单被误当历史成员证据。

仅正式历史路由取到非空出刀与血量后标finalized；休赛期重查本人联盟和成员即可复用此快照，不反复拉取不变的赛季记录。仍在每次选择数据前查询公开赛季表（本地60秒缓存），赛季/区服/联盟发生变化时绕过旧数据；未结算数据继续短TTL，手动刷新可重拉。没有名单或数据时保留未知，401/403/429不能靠缓存绕过。

验证：test_v101_zero_attacks.py、test_v101_offseason_cache.py、test_v100_history.py；全套及预览见当前版本handoff记录。下方0.5.0说明仅历史，包含“没有历史”等旧描述时不代表当前功能。

本模块属于 **联盟突袭 Union Raid**，不提供单人突袭、历史赛季查询、社区写入、自动续期或跨账号借Cookie。只加载命令发送者本人已绑定的Cookie；本次工作区没有NAS Cookie/DB，全部业务验收为脱敏构造数据，未读取真实Day2。历史构造名单与刀数不是当前账号结果。

## 0.5.0 行为

实际成员数量来自完整名单，无固定30/32人上限。quick视图增加龙傲天总输出前三、活菩萨击杀前三；击杀相同按仅尾刀伤害降序，稳定处理完全同值，不让0击杀占位。先核对本人联盟，再按game_id/area_id/guild_id合并在途抓取与共享快照；默认180秒，WebUI按秒调整，0禁用。各成员复用时保持原始获取时间，到期重新查，不用旧数据冒充当前状态。本人详情仍仅显示本人。

页面照片只在union-page底层，hero/panel/notice等使用主题底色，不在长表中拉伸模糊照片。新验收预览使用明确标注的32人构造名单；不是当前真实联盟抓取。

## 父集成接口

- 从 `nikke_union.commands` 导入 `sv_union`；pm=6、priority=3。一个 `on_command(('出刀','联盟突袭','突袭'))` 装饰器把三个互不重叠的前缀注册到同一handler，内部解析速查、Day1/Day2、详情、缺刀、尾刀、刷新。不要另加“出刀速查”前缀Trigger。
- 可调用 `set_before_send(callback)`。callback签名为 `async (bot, event) -> bool`，唯一回复发送前重新调用；False不发送，已经取得的结果也不发。父root全局用户黑白hook仍应在命令开始前负责拦截；本模块不自行读取或推测父全局配置。
- `union_queries.query(client, bind, *, view='quick', day=None, refresh=False, static=None, character_map=()) -> dict`。day是backend编号：0=Day1，1=Day2；None自动选择（有Day2记录即Day2，否则Day1）。view支持quick/detail/missing/tails；详情仅本人Day2。`invalidate(bind)`只清该加密绑定版本缓存。
- 默认 `nk出刀`；显式 `nk出刀速查 Day2`；本人 `nk出刀详情`；同handler还有 `nk出刀缺刀` / `nk出刀尾刀`。`nk联盟突袭详情`与`nk突袭`共用handler。暂不实现跨成员查询、分页、Boss筛选或独立“nk缺刀”命令；完整成员表一次显示。
- 由父root完成SV引入、help和source缓存维护，本模块没有修改它们，也没有修改现有api/client。

## 已核实请求与口径

1. `POST /api/game/proxy/Game/GetMyGuildInfo {}`，严格消费 `data.card.guild_id`。公开公会store链路、原文哈希与有界摘录保存在 `.references/community/union-source/guild-wrapper.md`；未知wrapper拒绝，不尝试guild_info/top-level等猜测。
2. `POST .../GetGuildMembers {guild_id, nikke_area_id}`，严格 `data.items`，member_id与出刀openid做差集。名单业务端点非鉴权/限流错误时降级只显示已出刀人，并明确“0刀未知，不判断全员完成”；非法items、重复member_id拒绝，不伪造零刀。
3. `POST .../GetUnionRaidData {guild_id, intl_open_id, nikke_area_id}`；无可确认guild_id时不臆造，仍只读本人当前接口。严格 `data.participate_data`，一条一次刀，不对内容相同的记录擅自去重。客户端返回的day仅接受0/1；超过3刀原样保留、标异常。伤害只接受非负整数/十进制整数字符串，计算与输出全程不用float。
4. `POST .../GetUnionRaidLevelInfo` 同当前请求字段，校验level_info/boss_info与非负current_hp/max_hp关系。未确认level_info的day与关卡全集时不猜测它属于Day1；Day1卡片依据当前记录的Boss击杀等级。Day2存在或完整五Boss×1..10级击杀证明Day1已通关，否则明确“未确认通关”，不从部分记录推断总等级或剩余数量。

Day1不输出个人排行/漏刀/尾刀。Day2个人3刀；尾刀仅Day2的is_final_hit。赛季ID未从当前API得到证据，因此标题标“社区当前可用记录·赛季未知”，不擅自请求历史。获取时间写UTC完整日期时间，缓存命中保留原获取时间。

## 权限、缓存、错误

`load_client(ev.user_id, ev.bot_id)`只用发送者，不解释@目标。GroupPolicy在加载Cookie前执行。缓存独立于profile/source，TTL=300秒；账号键为game_id/openid/area_id，缓存额外含加密Cookie的SHA256版本。每账号锁串行，同账号远端请求起始至少间隔5秒；批次内等候，失败/强刷后不足5秒明确冷却，不自动密集刷新。并发相同绑定复用刚生成缓存。新绑定版本不会读旧缓存，账号锁与冷却仍共用。

401/403/429/300001立即停止批次，不降级名单继续请求；300001和鉴权拒绝清当前版本缓存。未知API错误只输出错误码，异常日志只含阶段/异常类型/错误码，无响应正文、Cookie、Token或账号标识。客户端close失败单独记录stage=close且保留成功结果，最多一条回复。

## 角色与图片

详情严格 `squad[].tid -> character_id_map.json.id -> name_code/resource_id`，使用现有资源服务数据库表，不拿tid排序或除100猜角色身份。静态缺表/缺ID显示“未知角色(tid …)”。已映射角色只使用公共基础SI头像skin=0；不将costume_id猜成skin_index。HTML自动转义昵称/Boss/角色名；本人三队保留完整整数伤害、Boss等级、尾刀、角色等级和战力。

## 离线验收

运行 `python -m pytest tests/test_union.py tests/test_union_commands.py -q`（使用现有Python及.runtime/packages）。当前55项通过。

- 32成员、50条Day1、91条Day2、10次Day2尾刀的构造fixture；29人3刀、2人2刀、1人0刀。样本昵称和ID均为mock，明确不是当前数据。
- Day1不统计个人刀/尾刀、Day2差集0刀、缺名单未知、4刀异常不夹断、超2^53伤害精确、tid准确映射与未知兜底/HTML转义。
- httpx.MockTransport真实NikkeClient：仅四个已证实只读POST、精确请求字段、远端间隔、5min缓存、账号锁、绑定版本隔离/身份不一致拒绝、鉴权/限流/未知API异常、错误结构拒绝。
- 固定公开GsCore真实Trigger：SV别名按真实SV规则展开、同handler每条输入仅一次查询/回复，sender绑定加载、GroupPolicy先拦截、恢复提示、错误日志脱敏、close错误不吞结果、父发送权限再次判断。

部署后需在用户已登录环境人工对照当前社区页面验收。真实数据尚未验证，不应把本测试通过描述成“已读到真实Day2”或“当前本人0刀”。
