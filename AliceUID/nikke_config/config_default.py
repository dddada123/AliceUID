from ..nikke_commands import command_prefix
from typing import Dict

from gsuid_core.utils.plugins_config.models import (
    GSC,
    GsBoolConfig,
    GsIntConfig,
    GsListStrConfig,
    GsStrConfig,
)

from ..nikke_render.fonts import factory_default, font_options

CONFIG_DEFAULT: Dict[str, GSC] = {
    "AliceUID_AIQueryEnabled": GsBoolConfig(
        "允许AI调用只读查询", "默认关闭；开启后须同时启用Core AI并重启完成注册。开放帮助、本人资料、角色练度和角色别名查询；始终遵守Core与AliceUID权限。关闭后立即拒绝AI调用，普通命令不受影响。", False,
    ),
    "AliceUID_SoloCardTheme": GsStrConfig(
        "个人突袭推荐卡片主题（独立）", "只影响个人突袭推荐卡片，默认暗色；可选亮色或随机，不跟随其他卡片主题。查询时可用亮色/暗色/随机参数临时指定。毛玻璃强度仍使用全局设置。", "dark", options=["light","dark","random"],
    ),
    "AliceUID_SignGroupNotify": GsBoolConfig(
        "签到群通知：全群批量设置", "改变此项时一次性设置全部群，并作为新群默认值；之后可用群内开启/关闭签到群通知单独覆盖。保存同值不重置单群设置；重复应用同值请用全群签到通知命令。只影响签到群通知。", True,
    ),
    "AliceUID_CommunitySignTime": GsStrConfig(
        "每日签到时间（北京时间）", "24小时制HH:MM，精确到分钟，例如08:33；保存后更新每日自动任务。社区周期08:00刷新；仅执行已授权账号，手动签到不受定时时刻限制。", "08:33",
    ),
    "AliceUID_GlassStrength": GsIntConfig(
        "全局毛玻璃强度（%）", "所有毛玻璃卡片共用0～100%，默认20%；0无模糊，100最强，只影响背景，文字和人物保持清晰。下次出图生效，保留已有自定义值。", 20, 100,
    ),
    "AliceUID_ForwardReencode": GsBoolConfig(
        "转发图片转换JPG（可选）", "默认关闭：复用旧标准转发链路，缓存并原样发送完整图片，不分页、不重新编码，无需额外NapCat插件。开启后才对非JPG图片尝试转换，透明图仍保留PNG；不能保证解决上传网络错误。登录二维码和普通发送始终保留原图。", False,
    ),
    "AliceUID_ForwardJpegQuality": GsIntConfig(
        "转发图片JPG编码质量（0–100）", "默认95，整数0～100，仅开启“转发图片转换JPG”后用于新编码图片，下次转发生效。100仍非无损；符合限制的现有JPG直接发送，透明图保留PNG，登录二维码和普通发送保留原图。", 95, 100,
    ),
    "AliceUID_ResourceCacheSeconds": GsIntConfig(
        "资源查询刷新间隔（固定300秒）", "按用户独立限频5分钟；期间复用已渲染图片，显式刷新也不绕过。兼容旧配置键，实际固定300秒。", 300, 300,
    ),
    "AliceUID_UnionCacheSeconds": GsIntConfig(
        "联盟查询缓存秒数", "出刀与会战血量共用同联盟快照并合并在途请求；默认180秒，可设60秒，0表示不缓存。", 180, 3600,
    ),
    "AliceUID_CardLanguage": GsStrConfig(
        "卡片文字语言", "只影响卡片显示；社区数据仍使用繁体中文读取。", "zh-CN", options=["zh-CN", "zh-TW"],
    ),
    "AliceUID_CardFont": GsStrConfig(
        "卡片字体", "读取插件formts目录；新字体放入后刷新本页。字体不可读自动用黑体，列表保留显式兜底项。", factory_default(), options=font_options(),
    ),
    "AliceUID_GroupWhitelist": GsListStrConfig("群白名单", "非空时仅允许这些群查询，再排除群黑名单；空表默认全部", []),
    "AliceUID_GroupBlacklist": GsListStrConfig("群黑名单", "禁止这些群查询；同ID不能同时出现在群白名单", []),
    "AliceUID_UserWhitelist": GsListStrConfig("用户白名单", "非空时仅允许这些用户使用全部命令和账号服务；Bot主同样受限", []),
    "AliceUID_UserBlacklist": GsListStrConfig("用户黑名单", "禁止这些用户使用命令和账号服务；同ID不能同时出现在用户白名单", []),
    "AliceUID_MasterQQ": GsListStrConfig(
        "Bot 主 QQ",
        "填写绑定的主人QQ标记名单；不会提升GsCore服务权限。资源、群名单等维护命令仍须由框架Bot主(pm=0)触发",
        [],
    ),
    "AliceUID_LoginUrl": GsStrConfig(
        "登录页外网地址",
        "填反代/内网穿透地址，例如 https://bot.example.com。"
        "留空则用 core 的 HOST:PORT 拼；局域网/本机可用 http://127.0.0.1:8765",
        "",
        secret=True,
    ),
    "AliceUID_LoginQRCode": GsBoolConfig(
        "登录链接转二维码",
        f"开启后，{command_prefix()} 登录 会同时发送二维码图片，方便手机扫码",
        False,
    ),
    "AliceUID_ForwardReceiptSeconds": GsIntConfig(
        "转发回执等待秒数",
        "仅AliceUID的NapCat转发等待消息ID回执，默认30秒，可设5～300秒；保存后下一次转发生效。等待不包含图片渲染。超时普通回退一次，暂停本连接转发60秒；迟到成功仍可能重复。",
        30, 300,
    ),
    "AliceUID_CDKForward": GsBoolConfig(
        "兑换码查询详情用转发消息",
        "默认开启，仅控制详细列表；速查直发。首条说明内容并显示本人指挥官、区服和UID，转发不带@。保留旧版详情开关设置，关闭或不可用时普通发送。",
        True,
    ),
    "AliceUID_CDKResultForward": GsBoolConfig(
        "兑换结果用转发消息",
        "默认关闭，与查询详情独立。结果仅列逐码状态与统计，报酬在查询详情中查看。开启后，超过600字或12行的结果合并转发，简短回执仍直发。首条显示用途、指挥官、区服和UID，不带@；沿用原回执等待与失败回退。",
        False,
    ),
    "AliceUID_LoginForward": GsBoolConfig(
        "登录链接用转发消息（实验性）",
        "实验性功能，默认开启，首次登录/重新登录共用，二维码独立。NapCat未确认发送时自动回退一次普通消息，并暂停本连接转发60秒。开启后若看不到消息，请关闭此功能回退普通模式。保留已有配置值。",
        True,
    ),
    "AliceUID_HelpForward": GsBoolConfig(
        "帮助图片用转发消息（实验性）",
        "实验性功能，默认开启，使用现有适配器的标准转发，无需额外NapCat插件。成品原图先缓存，标题/说明合并，完整单图不分页。NapCat未确认发送时自动回退一次普通消息，并暂停本连接转发60秒。开启后若看不到消息，请关闭此功能回退普通模式。文字版和错误仍普通发送。",
        True,
    ),
    "AliceUID_RosterForward": GsBoolConfig(
        "完整卡片用转发消息（实验性）",
        f"实验性功能，默认开启，{command_prefix()}卡片复用旧标准转发，无需额外NapCat插件。完整JPG从缓存读取并原样发送，首节点展示指挥官与图鉴标题。NapCat未确认发送时自动回退一次普通消息，并暂停本连接转发60秒。开启后若看不到消息，请关闭此功能回退普通模式。进度/错误仍普通发送。",
        True,
    ),
    "AliceUID_UnionForward": GsBoolConfig(
        "出刀图片用转发消息（实验性）",
        "实验性功能，默认开启，使用现有适配器的标准转发，无需额外NapCat插件。出刀成品原图先缓存，完整单图不分页、不缩放。NapCat未确认发送时自动回退一次普通消息，并暂停本连接转发60秒。开启后若看不到消息，请关闭此功能回退普通模式。会战血量等短卡片不变。",
        True,
    ),
    "AliceUID_DefaultArea": GsIntConfig(
        "默认区服（旧版兼容）",
        f"仅保留兼容旧配置。新登录须用 {command_prefix()}登录日服/国际服/北美服/韩服/东南亚服 选择；不会自动切换区服。港澳台登录暂未支持",
        81,
        91,
    ),
    "AliceUID_LoginMode": GsStrConfig(
        "登录方式",
        "browser=网页账号密码登录；邮箱验证码选项暂不开放。cookie=仅私聊手动导入Cookie，不开放网页登录。",
        "browser",
        options=["browser", "cookie"],
    ),
    "AliceUID_BrowserChannel": GsStrConfig(
        "浏览器通道",
        "auto=优先内置 Chromium，失败回退 Edge；Docker 里一般用 chromium",
        "auto",
        options=["auto", "chromium", "msedge"],
    ),
    "AliceUID_Headless": GsBoolConfig(
        "无头浏览器",
        "Docker/服务器保持开启；本机调试可关掉看画面",
        True,
    ),
    "AliceUID_Proxy": GsStrConfig(
        "浏览器代理",
        "只覆盖网页登录浏览器，例如 http://127.0.0.1:7890；留空直连。代理池仅预留接口，尚未分配每用户IP",
        "",
        secret=True,
    ),
    "AliceUID_LoginTTL": GsIntConfig(
        "登录链接有效期（秒）",
        "一次性登录链接的过期时间",
        600,
        1800,
    ),
    "AliceUID_CacheTTL": GsIntConfig(
        "查询缓存（秒）",
        "同一账号的角色列表/资料缓存时间，避免触发上游限流",
        600,
        3600,
    ),
    "AliceUID_RemoteRenderEnable": GsBoolConfig(
        "外置渲染开关",
        "开启后优先把HTML发到外置服务，失败回退GsCore原生渲染接口",
        False,
    ),
    "AliceUID_RemoteRenderUrl": GsStrConfig(
        "外置渲染地址",
        "外置渲染服务的 API 地址，例如 http://127.0.0.1:3000/render",
        "http://127.0.0.1:3000/render",
        secret=True,
    ),
    "AliceUID_RemoteRenderToken": GsStrConfig(
        "外置渲染 Token",
        "可选。填写后请求头带 Authorization: Bearer <token>",
        "",
        secret=True,
    ),
    "AliceUID_CardTheme": GsStrConfig(
        "全局卡片主题", "默认random随机亮暗；dark暗色、light亮色。只在新渲染时随机，已有缓存图片直接复用，保留已有自定义值", "random", options=["dark", "light", "random"],
    ),
    "AliceUID_CharacterCardStyle": GsStrConfig(
        "角色练度卡布局", "compact=紧凑分栏（portraits）；旧布局已备份移除，保留此接口供未来注册新布局", "compact", options=["compact"],
    ),
    "AliceUID_RenderDpi": GsIntConfig(
        "渲染分辨率 DPI",
        "96=1x，144=1.5x，192=2x。模板按 1000px 宽设计",
        144,
        288,
    ),
    "AliceUID_RenderTimeout": GsIntConfig(
        "外置渲染超时（秒）",
        "外置渲染请求超时，超时后回退本地渲染",
        60,
        180,
    ),
    "AliceUID_CommunityPaused": GsBoolConfig(
        "暂停所有社区任务",
        f"紧急暂停全部社区请求。账号自动社区始终默认关闭，用户须用 {command_prefix()}自动社区 开启 单独授权",
        False,
    ),
    "AliceUID_CommunityRequestRange": GsStrConfig(
        "社区单次请求随机间隔（秒）", "最小值-最大值，默认5-15，可填2-5或15-15，允许1～3600秒及最多三位小数。全账号串行，保存后重启生效。", "5-15",
    ),
    "AliceUID_CommunityAccountRange": GsStrConfig(
        "社区换账号随机等待（秒）", "最小值-最大值，默认10-120。下一账号首次请求需同时满足请求间隔与上一账号最后响应后的换号等待；取较晚时刻，不叠加。重启生效。", "10-120",
    ),
    "AliceUID_CommunityDailyRequests": GsIntConfig(
        "社区每日请求上限",
        "每账号北京时间08:00开始的周期最多30次（含查询与失败请求），可调低，修改后重启生效",
        30,
        30,
    ),
    "DatabaseWeeklyUpdate": GsBoolConfig(
        "每周自动更新公开数据库", "每周五北京时间02:33增量检查公开角色资料与基础图库；不使用用户Token，关闭后仍可手动更新", True,
    ),
    "DatabaseIncludeSkins": GsBoolConfig(
        "数据库包含公开皮肤变体", "默认纳入公开清单皮肤的SI/MI/full，关闭则只补基础图；资源清单不证明账号拥有，展示按本人接口报告", True,
    ),
    "DatabaseMaxTasks": GsIntConfig(
        "数据库每批图片任务上限", "后台分批执行并持久保存剩余队列，避免一次占用过多资源", 40, 500,
    ),
    "DatabaseMaxDownloadMB": GsIntConfig(
        "数据库每批下载预算MiB", "达到后保存进度并以新批次续传；未完成不会报告全部成功", 128, 1024,
    ),
    "DatabaseMaxDiskMB": GsIntConfig(
        "公共图库存储预算MiB", "不主动删除旧图，空间预算不足时停止并保留队列", 2048, 16384,
    ),
    "DatabaseRequestInterval": GsIntConfig(
        "数据库请求间隔秒", "默认2秒，内部硬下限1.5秒；仅影响公开资料/图库请求", 2, 60,
    ),
    "DatabaseFailureCooldown": GsIntConfig(
        "数据库失败冷却秒", "公开源拒绝/限流或失败后持久冷却，不自动切IP或发送账号凭据", 3600, 86400,
    ),
    "DatabaseMaxRunMinutes": GsIntConfig(
        "数据库单次后台运行分钟上限", "后台连续补全的时间预算，达到后保存剩余任务，可手动继续或等下次周检", 30, 180,
    ),
    "AliceUID_EnableWriteOps": GsBoolConfig(
        "允许本人CDK兑换",
        f"默认关闭；开启后，{command_prefix()}兑换码 对绑定用户自动兑换，带码及单源命令也可兑换。{command_prefix()}查询兑换码 始终只读；8小时汇总仅维护目录。与自动社区授权、签到预算独立。",
        False,
    ),
}
