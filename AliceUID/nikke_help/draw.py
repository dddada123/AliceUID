"""Role-aware help content and standalone HTML rendering, without network IO."""
from __future__ import annotations
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
    path = PACKAGE.parent / 'assets/ALICEUID_Login_liberalio_.jpg'
    return 'data:image/jpeg;base64,' + base64.b64encode(path.read_bytes()).decode() if path.is_file() else ''


def build_help_context(permission: int = 6, *, login_mode='browser') -> dict:
    from ..nikke_community.runtime import configured_sign_time
    sign_time = configured_sign_time()
    if type(permission) is not int or not 0 <= permission <= 6:
        permission = 6
    permission = 0 if permission == 0 else 6
    sections = [
        {'title': '账号与 UID', 'tag': '本人账号', 'description': '登录绑定、凭据维护与UID登记；仅操作本人。', 'items': [
            {'command': f'{command_prefix()}我的账号', 'description': '查看登录绑定、区服与Cookie有效期'},
            {'command': f'{command_prefix()}重新登录 / {command_prefix()}重新登陆', 'description': '同账号同区服更新Cookie；失败保留原绑定，成功后需重新开启自动社区'},
            {'command': f'{command_prefix()}导入cookie 日服 Cookie内容', 'description': '高级导入仅限私聊，区服必须明确选择'},
            {'command': f'{command_prefix()}公开 / {command_prefix()}隐藏', 'description': '设置公开标记；本版尚无群排行'},
            {'command': f'{command_prefix()}解绑', 'description': '退出登录绑定，撤销自动社区并使旧链接失效'},
            {'command': f'{command_prefix()}绑定UID', 'description': '查看社区标识 / 游戏UID / 分享链接三种登记用法'},
            {'command': f'{command_prefix()}我的UID / {command_prefix()}解绑UID', 'description': '查看或清除UID登记；不代表登录或账号归属'},
        ]},
        {'title': '社区功能', 'tag': '社区日常', 'description': '签到、浏览及点赞；保持原有授权、周期与预算规则。', 'items': [
            {'command': f'{command_prefix()}签到', 'description': '立即为本人签到；已开启全量时按该模式执行。本周期已成功则不发社区请求'},
            {'command': f'{command_prefix()}开启全量签到', 'description': '仅为本人开启每日签到、浏览及点赞，立即执行并返回结果；不自动评论'},
            {'command': f'{command_prefix()}自动社区 状态', 'description': '查看开关、暂停原因和上次完成日期'},
            {'command': f'{command_prefix()}自动社区 开启', 'description': f'授权签到与浏览；每天北京时间{sign_time}开始，08:00为周期分界'},
            {'command': f'{command_prefix()}自动社区 关闭', 'description': '停止自动签到、浏览与点赞'},
            {'command': f'{command_prefix()}自动社区 点赞开启', 'description': '单独授权点赞，不会自动评论'},
            {'command': f'{command_prefix()}自动社区 点赞关闭', 'description': '只撤销点赞；已暂停的任务保持暂停'},
        ]},
        {'title': '个人查询', 'tag': '本人功能', 'description': '资料、角色练度、收菜与个人突袭；日历和别名查询无需绑定。', 'items': [
            {'command': f'{command_prefix()}信息 / {command_prefix()}名片', 'description': '读取本人资料缓存；展示战役爬塔、主立绘与当前皮肤'},
            {'command': f'{command_prefix()}爱丽丝练度 / {command_prefix()}爱丽丝面板', 'description': '本人立绘、装备与技能；已有本地数据和图片优先复用'},
            {'command': f'{command_prefix()}信息刷新 / {command_prefix()}刷新信息', 'description': '轻量更新本人名片资料并回图，不读取全部角色装备详情'},
            {'command': f'{command_prefix()}刷新爱丽丝面板', 'description': '替换角色名，更新该角色数据并渲染卡片；至少间隔5秒'},
            {'command': f'{command_prefix()}卡片', 'description': '读取本人角色与皮肤缓存；每行10个头像，含星级/核心角标'},
            {'command': f'{command_prefix()}练度全量导出', 'description': '本人全角色练度导出Excel；本地缓存、双角色并排、表内爆裂/定位/企业筛选'},
            {'command': f'{command_prefix()}刷新面板', 'description': '全量更新本人资料、全部角色练度与皮肤；完成后发送信息图'},
            {'command': f'{command_prefix()}资源查询 [刷新]', 'description': '无可用图时同步本人收菜并出图；成功出图后复用5分钟，失败仅短暂冷却；显示90%和回满预计时间'},
            {'command': f'{command_prefix()}开启收菜提醒 / {command_prefix()}关闭收菜提醒', 'description': '当前群聊或私聊独立开关；开启发一次资源卡，后续纯文字；连续两晚23点MAX自动停查'},
            {'command': f'{command_prefix()}个人突袭推荐 [亮色/暗色/随机]', 'description': '实验性：DILDORO本人编队推荐，本地缓存5天；独立亮暗主题，默认暗色'},
            {'command': f'{command_prefix()}收菜提醒状态', 'description': '查看本会话订阅、共享快照和下一检查；不请求游戏接口'},
            {'command': f'{command_prefix()}个人突袭推荐刷新 [亮色/暗色/随机]', 'description': '练度变化时重新导入并计算，成功后更新本人五天缓存'},
            {'command': f'{command_prefix()}收菜免打扰 00:00-08:00', 'description': '仅收菜提醒，北京时间；支持跨午夜，输入关闭取消；不影响签到及其他业务'},
            {'command': f'{command_prefix()}红莲暗影别名查询 / {command_prefix()}黑莲别名查询', 'description': '头像卡片展示角色本名与别名；支持简繁和省略符号'},
            {'command': f'{command_prefix()}日历', 'description': '官网默认活动日历截图，附来源和拍摄时间'},
            {'command': f'{command_prefix()}角色别名查询 红莲：暗影', 'description': '另一种别名查询写法，不要求登录'},
            {'command': f'{command_prefix()}日历 帮助', 'description': '查看截图范围与缓存说明；暂不支持历史月份'},
        ]},
        {'title': '联盟查询', 'tag': '联盟与会战', 'description': '联盟出刀、缺刀、尾刀及会战血量。', 'items': [
            {'command': f'{command_prefix()}出刀 / {command_prefix()}查刀', 'description': '出刀、输出与击杀前三；当期共享180秒，休赛期复用已结算记录并检测新赛季'},
            {'command': f'{command_prefix()}出刀速查 Day2 / {command_prefix()}出刀 Day1', 'description': '选择会战阶段；Day1只统计BOSS击杀进度'},
            {'command': f'{command_prefix()}出刀详情 [排名]', 'description': '不带数字查本人；如出刀详情10，查本工会伤害第10名；缺刀/尾刀保留'},
            {'command': f'{command_prefix()}会战血量 [刷新]', 'description': '联盟阶段与BOSS血量；休赛期展示上一期，卡片注明赛季与状态'},
        ]},
        {'title': '兑换码', 'tag': 'CDK', 'description': '官方、GameWith与成员验证码，同码合并；只操作本人，查询始终不兑换。', 'items': [
            {'command': f'{command_prefix()}查询兑换码', 'description': '无需绑定，分块列出当前码、来源和报酬详情，始终不兑换'},
            {'command': f'{command_prefix()}兑换码速查', 'description': '无需绑定，只列当前兑换码，不显示报酬，不执行兑换'},
            {'command': f'{command_prefix()}兑换码', 'description': '列出当前码；已绑定用户自动兑换本人未领取项，需Bot主开启CDK兑换'},
            {'command': f'{command_prefix()}兑换码ABCDEFG', 'description': '将ABCDEFG换成单个兑换码；只操作本人，成功附可用的第三方报酬说明'},
            {'command': f'{command_prefix()}兑换官方兑换码 / {command_prefix()}第三方兑换码', 'description': '仅兑换对应来源的当前码；第三方历史区不参与'},
            {'command': f'{command_prefix()}增加兑换码ABCDEFG', 'description': '成员可用：成功/官方明确已领取入库，48小时内可补录'},
        ]}
    ]
    if permission == 0:
        sections.extend([
            {'title': '数据库与全局管理', 'tag': '仅 Bot 主', 'description': '公开数据库、账号与用户权限，以及全局外观维护。', 'items': [
                {'command': f'{command_prefix()}数据库更新', 'description': '先角色资料后图库；招募日历静默更新，保留周检'},
                {'command': f'{command_prefix()}刷新兑换码', 'description': '手动维护官方+GameWith共享缓存；不兑换。00/08/16点静默更新，按需缓存4小时'},
                {'command': f'{command_prefix()}数据库更新 状态 / 帮助', 'description': '查看日历排期、小时补查及24小时结果、图库队列'},
                {'command': '后台：每日签到时间', 'description': '北京时间HH:MM，默认08:33；保存后更新调度，手动签到仍可立即执行'},
                {'command': f'{command_prefix()}更新资源', 'description': '兼容旧命令，同样进入增量数据库任务'},
                {'command': f'{command_prefix()}用户黑名单 / {command_prefix()}用户白名单', 'description': '添加 / 移除 QQ号；黑用户禁全部Nikke指令与登录'},
                {'command': f'{command_prefix()}红莲：暗影新增别名黑莲', 'description': f'添加全局角色别名；可省略符号，如 {command_prefix()}红莲暗影新增别名黑莲'},
                {'command': f'{command_prefix()}账号列表', 'description': '查看绑定摘要，不展示账号凭据'},
                {'command': f'{command_prefix()}红莲暗影注册别名黑莲', 'description': '与新增别名相同；旧的「角色名别名别名」写法已停用'},
                {'command': '后台：AliceUID 用户绑定管理', 'description': '查看绑定摘要与脱敏导出；修改凭据需通过登录流程，解绑走专用接口'},
                {'command': '后台：主题与卡片语言', 'description': '亮色/暗色/随机毛玻璃，简繁可选；出刀缓存按秒调整'},
                {'command': '后台：全局毛玻璃强度', 'description': '0～100%，默认20%；只模糊背景，修改后下次出图生效'},
            ]},
            {'title': '群组查询', 'tag': '仅 Bot 主', 'description': '群查询状态、签到记录与通知，以及群名单维护。', 'items': [
                {'command': f'{command_prefix()}群查询 状态', 'description': '查看本群实际查询权限，不能绕过Bot主名单'},
                {'command': f'{command_prefix()}签到查询 [页码]', 'description': '本群绑定/近期使用账号的本周期签到记录；本地确认结果，非实时全员名单'},
                {'command': f'{command_prefix()}群查询 开启 / 关闭', 'description': 'Bot主操作本群名单；白名单非空仍须在内'},
                {'command': f'{command_prefix()}签到群通知 开启/关闭/状态', 'description': 'Bot主设置当前群通知，仅本群生效，不影响签到执行'},
                {'command': f'{command_prefix()}群策略 状态', 'description': '两表空默认允许；白名单先限定再判黑'},
                {'command': f'{command_prefix()}开启签到群通知 / 关闭签到群通知', 'description': 'Bot主在群内单独开关通知，其他群不受影响'},
                {'command': f'{command_prefix()}群黑名单 / {command_prefix()}群白名单', 'description': '添加 / 移除 群号；同群号跨两表拒绝保存'},
                {'command': f'{command_prefix()}全群签到通知 开启/关闭/状态', 'description': '一次性批量应用全部群，之后仍可单独修改各群'},
            ]}
        ])
    steps = [
        {'number': '01', 'command': f'{command_prefix()}登录', 'description': '登录/登陆均可；先看区服选项，再选角色所在区服'},
        {'number': '02', 'command': '打开登录链接', 'description': '默认账号密码，也可切换邮箱验证码'},
        {'number': '03', 'command': f'{command_prefix()}信息', 'description': '回到聊天，获取个人名片或角色练度'},
    ]
    if login_mode == 'cookie':
        steps[1] = {'number': '02', 'command': '私聊导入 Cookie', 'description': '当前仅Cookie模式；按区服命令返回的用法操作'}
    return {
        'role': 'Bot 主' if permission == 0 else '群管理员' if permission <= 3 else '普通用户',
        'regions': [f'{command_prefix()}登录日服', f'{command_prefix()}登录国际服', f'{command_prefix()}登录北美服', f'{command_prefix()}登录韩服', f'{command_prefix()}登录东南亚服'],
        'steps': steps, 'sections': sections, 'hero_art': _hero_art(),
        'cookie_hint': f'请使用已有游戏邮箱；凭据失效用{command_prefix()}重新登录/重新登陆，无需先解绑。不要在群里发送密码、验证码或Cookie。',
        'limit_hint': '社区请求默认随机5～15秒，换号随机等待10～120秒，Bot主可在后台自定义；08:00划分周期，每周期最多30次请求；成功不重复，短期故障有限重试，连续三天失败自动关闭。UID登记不提供匿名练度授权。',
        'database_hint': '公共库每周五02:33（北京时间）增量检查，仅Bot主维护；皮肤显示按本人接口，静态清单不代表拥有。',
        'footer': f'选错区服或换号：先 {command_prefix()}解绑，再选区服重新登录。港澳台登录流程暂未支持。',
    }


def help_text(context: dict) -> str:
    lines = [f"AliceUID 指令指南 · {context['role']}", '快速开始：' + ' → '.join(step['command'] for step in context['steps']),
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
        wide = len(items) > 7
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
    items=sum(len(section.get('items',[])) for section in context.get('sections',[]))
    scene_height=max(2200,900+items*90)
    prepared = dict(context, section_bands=section_bands(context['sections']))
    return _ENV.get_template('help.html').render(**apply_theme(prepared, context.get("card_theme"),scene_height=scene_height))


async def draw_help(context: dict) -> bytes:
    from ..nikke_render.render import render_html
    return await render_html(render_help_html(context), root_width=1000)
