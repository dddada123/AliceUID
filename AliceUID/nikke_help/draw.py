"""Role-aware help content and standalone HTML rendering, without network IO."""
from __future__ import annotations
from ..version import VERSION, BUILD
from ..nikke_commands import command_prefix

import base64
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from ..nikke_render.theme import apply_theme

PACKAGE = Path(__file__).resolve().parent.parent
_ENV = Environment(loader=FileSystemLoader(str(PACKAGE / 'templates')), autoescape=select_autoescape(['html']))


@lru_cache(maxsize=1)
def _hero_art() -> str:
    from ..nikke_resource.media import media_path
    path = media_path('assets/ICON.png')
    return 'data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode() if path.is_file() else ''


def build_help_context(permission: int = 6, *, login_mode='browser') -> dict:
    from ..nikke_community.runtime import configured_sign_time
    sign_time = configured_sign_time()
    if type(permission) is not int or not 0 <= permission <= 6:
        permission = 6
    permission = 0 if permission == 0 else 6
    sections = [
        {'title': '账号与 UID', 'tag': '本人账号', 'description': '登录绑定、凭据维护与 UID 登记（仅操作本人）。', 'items': [
            {'command': f'{command_prefix()}我的账号', 'description': '查看绑定区服与 Cookie 有效期'},
            {'command': f'{command_prefix()}重新登录 / {command_prefix()}重新登陆', 'description': '更新本人 Cookie 并在同步后自动发送名片'},
            {'command': f'{command_prefix()}导入cookie 日服 Cookie内容', 'description': '高级导入（仅限私聊，需指定区服）'},
            {'command': f'{command_prefix()}解绑', 'description': '退出登录绑定并停止自动社区'},
            {'command': f'{command_prefix()}绑定UID', 'description': '查看社区标识 / 游戏 UID / 分享链接绑定用法'},
            {'command': f'{command_prefix()}我的UID / {command_prefix()}解绑UID', 'description': '查看或清除本地 UID 登记'},
        ]},
        {'title': '社区功能', 'tag': '社区日常', 'description': 'Blablalink 自动与手动签到、浏览及点赞。', 'items': [
            {'command': f'{command_prefix()}签到', 'description': '立即为本人执行本周期社区签到'},
            {'command': f'{command_prefix()}开启全量签到', 'description': '开启本人每日签到、浏览及点赞并立即执行'},
            {'command': f'{command_prefix()}自动社区 状态', 'description': '查看自动社区开关与上次完成日期'},
            {'command': f'{command_prefix()}自动社区 开启', 'description': f'授权自动签到与浏览（每天 {sign_time} 开始）'},
            {'command': f'{command_prefix()}自动社区 关闭', 'description': '停止自动签到、浏览与点赞'},
            {'command': f'{command_prefix()}自动社区 点赞开启', 'description': '单独开启社区自动点赞'},
            {'command': f'{command_prefix()}自动社区 点赞关闭', 'description': '关闭社区自动点赞'},
        ]},
        {'title': '官网妮姬隐私', 'tag': '本人账号', 'full_width': True, 'description': '控制 Blablalink 官网个人妮姬资料的公开范围。', 'items': [
            {'command': f'{command_prefix()}妮姬公开', 'description': '将官网妮姬资料设为所有人可见'},
            {'command': f'{command_prefix()}妮姬隐藏', 'description': '隐藏官网妮姬资料'},
            {'command': f'{command_prefix()}妮姬公开状态', 'description': '查看官网当前公开状态'},
        ]},
        {'title': '攻略查询', 'tag': '无需登录', 'description': 'Blablalink 攻略长图与联盟战攻略查询，支持自动中文翻译。', 'items': [
            {'command': f'{command_prefix()}<角色/关键词>攻略', 'description': '查询角色、单突或机制攻略并转发长图与正文'},
            {'command': f'{command_prefix()}攻略查询 [筛选/全部]', 'description': '查看最新 10 篇攻略并检查新帖（可按分类筛选）'},
            {'command': f'{command_prefix()}查询1 ～ {command_prefix()}查询10', 'description': '收到攻略列表后 60 秒内回复编号获取对应攻略'},
            {'command': f'{command_prefix()}会战攻略 / {command_prefix()}会战阵容', 'description': '获取当期或最近一期联盟战攻略与阵容长图'},
        ]},
        {'title': '联盟查询', 'tag': '联盟与会战', 'description': '联盟突袭出刀统计、个人详情与 BOSS 血量。', 'items': [
            {'command': f'{command_prefix()}出刀 / {command_prefix()}查刀', 'description': '查看联盟出刀统计、伤害与击杀前三'},
            {'command': f'{command_prefix()}出刀速查 Day2 / {command_prefix()}出刀 Day1', 'description': '按指定会战阶段统计出刀与击杀进度'},
            {'command': f'{command_prefix()}出刀详情 [排名]', 'description': f'查本人或指定排名的出刀详情（如 {command_prefix()}出刀详情10）'},
            {'command': f'{command_prefix()}会战血量 [刷新]', 'description': '查看联盟当前阶段与 BOSS 血量'},
        ]},
        {'title': '个人查询', 'tag': '本人面板与公开工具', 'full_width': True, 'description': '指挥官名片、角色练度、图鉴、练度导出、活动日历与别名查询。', 'items': [
            {'command': f'{command_prefix()}信息 / {command_prefix()}名片', 'description': '展示指挥官名片、战役爬塔与主推立绘'},
            {'command': f'{command_prefix()}信息刷新 / {command_prefix()}刷新信息', 'description': '快速刷新本人名片资料并出图'},
            {'command': f'{command_prefix()}爱丽丝练度 / {command_prefix()}爱丽丝面板', 'description': '查看指定角色立绘、装备与技能练度'},
            {'command': f'{command_prefix()}刷新爱丽丝面板', 'description': '替换角色名，刷新该角色最新面板并出图'},
            {'command': f'{command_prefix()}卡片 / {command_prefix()}阵容卡片', 'description': '生成主力妮姬卡片（任一技能 ≥ Lv.7）'},
            {'command': f'{command_prefix()}图鉴 / {command_prefix()}妮姬图鉴', 'description': '生成全量图鉴（含灰阶未解锁妮姬展示）'},
            {'command': f'{command_prefix()}刷新面板', 'description': '全量刷新本人资料与全部角色练度并出图'},
            {'command': f'{command_prefix()}练度全量导出', 'description': '导出原始练度 Excel（支持公开链接）'},
            {'command': f'{command_prefix()}400练度全量导出[json] [链接]', 'description': '导出原始与指定等级模拟对照（400 可替换）'},
            {'command': f'{command_prefix()}练度全量导出json / JSON', 'description': '导出实际等级 JSON，便于分析'},
            {'command': f'{command_prefix()}日历 [帮助]', 'description': '生成官网当期活动日历与卡池排期图（无需登录）'},
            {'command': f'{command_prefix()}<角色>别名查询 / {command_prefix()}角色别名查询 <名称>', 'description': '查询角色官方名称与可用别名（无需登录）'},
        ]},
        {'title': '收菜与个人突袭', 'tag': '本人助手', 'description': '前哨基地收菜提醒与个人突袭智能配队推荐。', 'items': [
            {'command': f'{command_prefix()}资源查询 [刷新]', 'description': '查看本人收菜进度与 90%/满仓预计时间，每 5 分钟可查询一次'},
            {'command': f'{command_prefix()}开启收菜提醒 / {command_prefix()}关闭收菜提醒', 'description': '开关当前会话的收菜提醒（连续两晚满仓自动暂停）'},
            {'command': f'{command_prefix()}收菜提醒状态', 'description': '查看收菜提醒状态、当前进度与下次检查时间'},
            {'command': f'{command_prefix()}收菜免打扰 00:00-08:00', 'description': '设置收菜免打扰时段（北京时间，输入关闭取消）'},
            {'command': f'{command_prefix()}个人突袭推荐[火/水/风/电/铁] [主题]', 'description': '实验性：按弱点属性生成个人突袭配队推荐'},
            {'command': f'{command_prefix()}个人突袭推荐[属性]刷新 [主题]', 'description': '重新计算指定属性配队（主题可选亮色/暗色/随机）'},
        ]},
        {'title': '兑换码', 'tag': 'CDK', 'description': '官方、GameWith 与成员兑换码整合查询及自动兑换。', 'items': [
            {'command': f'{command_prefix()}查询兑换码', 'description': '查看当前可用兑换码与奖励详情（无需绑定，不兑换）'},
            {'command': f'{command_prefix()}兑换码速查', 'description': '快速列出当前兑换码（无需绑定，不兑换）'},
            {'command': f'{command_prefix()}兑换码', 'description': '列出当前码并为已绑定用户自动兑换未领取项'},
            {'command': f'{command_prefix()}兑换码ABCDEFG', 'description': '兑换单个指定兑换码（仅操作本人）'},
            {'command': f'{command_prefix()}兑换官方兑换码 / {command_prefix()}第三方兑换码', 'description': '仅兑换对应来源的当前可用兑换码'},
            {'command': f'{command_prefix()}增加兑换码ABCDEFG', 'description': '提交并核验新兑换码，有效时自动为开启者兑换'},
            {'command': f'{command_prefix()}自动兑换码 / {command_prefix()}关闭自动兑换码', 'description': '开关本人新兑换码自动兑换'},
        ]}
    ]
    if permission == 0:
        sections.extend([
            {'title': '数据库与全局管理', 'tag': '仅 Bot 主', 'description': '公开数据库、账号权限、角色别名与全局外观维护。', 'items': [
                {'command': f'{command_prefix()}数据库更新 [状态/帮助]', 'description': '增量更新角色资料与图库，或查看日历调度状态'},
                {'command': f'{command_prefix()}攻略重索引 [清空]', 'description': 'Bot主重新回溯全量攻略索引；追加“清空”可重置后重建'},
                {'command': f'{command_prefix()}日志导出[分钟数]', 'description': f'导出最近 1～1440 分钟脱敏诊断日志（如 {command_prefix()}日志导出10）'},
                {'command': f'{command_prefix()}刷新兑换码', 'description': '立即检查并同步最新官方/第三方兑换码'},
                {'command': f'{command_prefix()}启用自动兑换码 / {command_prefix()}停用自动兑换码', 'description': '控制全插件自动兑换码总开关'},
                {'command': f'{command_prefix()}全员自动兑换码 / {command_prefix()}关闭全员自动兑换码', 'description': '批量开关全部已绑定用户的自动兑换'},
                {'command': f'{command_prefix()}账号列表', 'description': '查看已绑定账号摘要（不含凭据）'},
                {'command': f'{command_prefix()}用户黑名单 / {command_prefix()}用户白名单', 'description': '添加或移除 QQ 号以控制全局使用权限'},
                {'command': f'{command_prefix()}<角色名>新增别名<别名>', 'description': f'添加全局角色别名（如 {command_prefix()}红莲暗影新增别名黑莲）'},
                {'command': f'{command_prefix()}注销别名 <别名> / {command_prefix()}别名导出', 'description': '屏蔽指定别名或导出完整别名表 Markdown'},
                {'command': '后台：每日签到 / 外观 / 绑定管理', 'description': '在 GsCore 网页后台调整签到时间、主题语言、立绘样式与绑定管理'},
            ]},
            {'title': '群组查询与管理', 'tag': '仅 Bot 主', 'full_width': True, 'description': '群查询开关、签到通知、自动兑换与群名单维护。', 'items': [
                {'command': f'{command_prefix()}群查询 开启 / 关闭 / 状态', 'description': '管理本群查询权限及当前状态'},
                {'command': f'{command_prefix()}签到查询 [页码]', 'description': '查看本群成员本周期本地签到记录'},
                {'command': f'{command_prefix()}签到群通知 开启/关闭/状态', 'description': '设置当前群的每日签到汇总通知'},
                {'command': f'{command_prefix()}全群签到通知 开启/关闭/状态', 'description': '批量设置所有群的签到通知开关'},
                {'command': f'{command_prefix()}群黑名单 / {command_prefix()}群白名单', 'description': f'添加或移除群号，查看 {command_prefix()}群策略 状态'},
                {'command': f'{command_prefix()}全群自动兑换码 / {command_prefix()}关闭全群自动兑换码', 'description': '批量设置本群已绑定成员的自动兑换开关'},
            ]}
        ])
    steps = [
        {'number': '01', 'command': f'{command_prefix()}登录', 'description': '登录/登陆均可，先选择角色所在区服'},
        {'number': '02', 'command': '打开登录链接', 'description': '支持账号密码或 Cookie 导入'},
        {'number': '03', 'command': f'{command_prefix()}信息', 'description': '回到聊天获取指挥官名片与练度'},
    ]
    if login_mode == 'cookie':
        steps[1] = {'number': '02', 'command': '网页导入 Cookie', 'description': '当前仅 Cookie 模式，粘贴内容或上传 cookies.txt'}
    return {
        'role': 'Bot 主' if permission == 0 else '群管理员' if permission <= 3 else '普通用户',
        'regions': [f'{command_prefix()}登录日服', f'{command_prefix()}登录国际服', f'{command_prefix()}登录北美服', f'{command_prefix()}登录韩服', f'{command_prefix()}登录东南亚服'],
        'steps': steps, 'sections': sections, 'hero_art': _hero_art(),
        'cookie_hint': f'请使用已有游戏邮箱；凭据失效直接发送 {command_prefix()}重新登录 即可更新，切勿在群聊发送密码或 Cookie。',
        'limit_hint': '社区签到以北京时间 08:00 为周期分界，每日最多 30 次请求，连续三天异常将自动暂停；UID 登记不提供匿名练度授权。',
        'database_hint': '公共资料库每周五 02:33 增量检查，攻略索引每天 04:15 / 14:15 自动检查新帖；皮肤显示以本人账号接口为准。',
        'version': VERSION, 'build': BUILD,
        'footer': f'选错区服或换号：先 {command_prefix()}解绑 再重新登录。暂不支持港澳台服登录流程。',
    }


def help_text(context: dict) -> str:
    lines = [f"AliceUID {VERSION}（构建{BUILD}）指令指南 · {context['role']}", '快速开始：' + ' → '.join(step['command'] for step in context['steps']),
             '区服命令：' + ' / '.join(context['regions']),
             f'登录/登陆均可，例如{command_prefix()}登陆日服；{command_prefix()}重新登录/{command_prefix()}重新登陆同样可用。']
    for section in context['sections']:
        lines.append('\n' + section['title'])
        lines.extend(f"{item['command']}：{item['description']}" for item in section['items'])
    lines.extend(['\n' + context['cookie_hint'], context['limit_hint'], context['database_hint'], context['footer'], f'{command_prefix()}帮助：图片指南；{command_prefix()}帮助 文字：可复制的文字版。'])
    return '\n'.join(lines)


def section_bands(sections: list[dict]) -> list[list[dict]]:
    """Half-width small modules; wide modules contain left-to-right item pairs."""
    bands, pending = [], []
    for section in sections:
        items = section['items']
        if not items:
            continue
        wide = len(items) > 7 or section.get('full_width', False)
        columns = 2 if wide else 1
        prepared = dict(section, wide=wide,
                        rows=[items[i:i + columns] for i in range(0, len(items), columns)])
        if wide:
            if pending:
                bands.append(pending)
                pending = []
            bands.append([prepared])
        else:
            pending.append(prepared)
            if len(pending) == 2:
                bands.append(pending)
                pending = []
    if pending:
        bands.append(pending)
    return bands


def render_help_html(context: dict) -> str:
    from datetime import datetime, timedelta, timezone
    from ..nikke_render.fonts import apply_font_html
    from ..nikke_render.theme import v2_theme_tokens
    items=sum(len(section.get('items',[])) for section in context.get('sections',[]))
    scene_height=max(2200,900+items*90)
    prepared = dict(context, section_bands=section_bands(context['sections']))
    themed = apply_theme(prepared, context.get("card_theme"),scene_height=scene_height)
    themed.update(v2_theme_tokens(None, themed['card_theme']))
    themed['font_family'] = 'MiSans'
    themed['credit_timestamp'] = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d·%H:%M')
    return apply_font_html(_ENV.get_template('help.html').render(**themed), embed=False)


async def draw_help(context: dict) -> bytes:
    from ..nikke_render.render import render_html
    return await render_html(render_help_html(context), root_width=1000)
