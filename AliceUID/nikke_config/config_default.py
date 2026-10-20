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
    "AliceUID_CustomPrefixEnabled": GsBoolConfig(
        "启用自定义唤醒指令", "保存后重启Core生效。默认仍使用nk；自定义指令与原有权限检查共用。", False,
    ),
    "AliceUID_CustomPrefix": GsStrConfig(
        "自定义唤醒指令", "1～12个中英文字母或数字，可用_、-；不能含空格、正则或标记。例alice或妮姬，保存后重启Core生效。", "alice",
    ),
    "AliceUID_DisableDefaultPrefix": GsBoolConfig(
        "自定义时禁用默认nk", f"仅启用自定义指令时有效。关闭：{command_prefix()}和自定义均可，帮助仍用nk；开启：仅自定义可用，帮助/提示同步替换。重启Core生效。", False,
    ),
    "AliceUID_CommunitySignTime": GsStrConfig(
        "每日签到时间（北京时间）", "24小时制HH:MM，精确到分钟，例如08:33；保存后更新每日自动任务。社区周期08:00刷新；仅执行已授权账号，手动签到不受定时时刻限制。", "08:33",
    ),
    "AliceUID_GlassStrength": GsIntConfig(
        "全局毛玻璃强度（%）", "所有毛玻璃卡片共用0～100%，默认20%；0无模糊，100最强，只影响背景，文字和人物保持清晰。下次出图生效，保留已有自定义值。", 20, 100,
    ),
    "AliceUID_ForwardJpegQuality": GsIntConfig(
        "转发图片JPG编码质量（0–100）", "默认95，整数0～100，下次转发生效。数值越高通常越清晰、文件越大；100仍非无损。用于新编码的转发图片；符合限制的现有JPG直接发送，透明图保留PNG，登录二维码和普通发送保留原图。", 95, 100,
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
    "AliceUID_LoginForward": GsBoolConfig(
        "登录链接用转发消息（实验性）",
        "实验性功能，默认开启，首次登录/重新登录共用，二维码独立。NapCat未确认发送时自动回退一次普通消息，并暂停本连接转发5分钟。开启后若看不到消息，请关闭此功能回退普通模式。保留已有配置值。",
        True,
    ),
    "AliceUID_HelpForward": GsBoolConfig(
        "帮助图片用转发消息（实验性）",
        "实验性功能，默认开启，帮助标题/图片/说明一起转发，长图采用高质量JPEG分页。NapCat未确认发送时自动回退一次普通消息，并暂停本连接转发5分钟。开启后若看不到消息，请关闭此功能回退普通模式。文字版和错误仍普通发送。",
        True,
    ),
    "AliceUID_RosterForward": GsBoolConfig(
        "完整卡片用转发消息（实验性）",
        f"实验性功能，默认开启，{command_prefix()}卡片及别名长图转发，首节点展示指挥官与图鉴标题。NapCat未确认发送时自动回退一次普通消息，并暂停本连接转发5分钟。开启后若看不到消息，请关闭此功能回退普通模式。进度/错误仍普通发送。",
        True,
    ),
    "AliceUID_UnionForward": GsBoolConfig(
        "出刀图片用转发消息（实验性）",
        "实验性功能，默认开启，出刀总览/速查/详情/缺刀/尾刀共用，长图采用高质量JPEG分页。NapCat未确认发送时自动回退一次普通消息，并暂停本连接转发5分钟。开启后若看不到消息，请关闭此功能回退普通模式。会战血量等短卡片不变。",
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
        "browser=网页默认账号密码，可切换邮箱验证码；cookie=仅私聊手动导入Cookie，不开放两种网页登录",
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
        "其他写操作（兼容预留）",
        f"预留给后续CDK等功能；当前自动社区由 {command_prefix()}自动社区 开启 按账号授权，整体暂停请用暂停所有社区任务",
        False,
    ),
}
