"""Dual-style user notice templates: '爱丽丝风格' (default) and '默认说明文'."""
from __future__ import annotations

NOTICE_STYLE_KEY = 'AliceUID_NoticeStyle'
SIGN_FORWARD_KEY = 'AliceUID_SignNoticeForward'
NOTICE_STYLES = ('爱丽丝风格', '默认说明文')
_LEGACY_STYLE_MAP = {
    'alice': '爱丽丝风格',
    'plain': '默认说明文',
    'default': '默认说明文',
    '说明文': '默认说明文',
    '爱丽丝': '爱丽丝风格',
}


def normalize_notice_style(value) -> str:
    text = str(value or '').strip()
    if text in NOTICE_STYLES:
        return text
    if text in _LEGACY_STYLE_MAP:
        return _LEGACY_STYLE_MAP[text]
    return '爱丽丝风格'


def get_notice_style() -> str:
    try:
        from ..nikke_config.config import AliceUIDConfig
        raw = AliceUIDConfig.get_config(NOTICE_STYLE_KEY).data
        return normalize_notice_style(raw)
    except (ImportError, AttributeError, KeyError, TypeError, ValueError, RuntimeError):
        return '爱丽丝风格'


def is_alice_style(style: str | None = None) -> bool:
    resolved = normalize_notice_style(style) if style is not None else get_notice_style()
    return resolved == '爱丽丝风格'


def sign_notice_forward_enabled() -> bool:
    try:
        from ..nikke_config.config import AliceUIDConfig
        return bool(AliceUIDConfig.get_config(SIGN_FORWARD_KEY).data)
    except (ImportError, AttributeError, KeyError, TypeError, ValueError, RuntimeError):
        return True


def titled(tag: str, body: str) -> str:
    """Format a structured message with a unified [AliceUID·tag] header."""
    return f'[AliceUID·{tag}]\n{body}'


def with_tail_at(payload, user_id, *, is_group: bool, newline: bool = False, sep: str | None = None):
    """Append @user_id to the tail of text/mixed group replies; leave single images and DMs untouched."""
    if not is_group or not user_id:
        return payload
    uid = str(user_id).strip()
    if not uid:
        return payload
    try:
        from gsuid_core.segment import MessageSegment
    except ImportError:
        return None
    if not (hasattr(MessageSegment, 'text') and hasattr(MessageSegment, 'at')):
        return None
    resolved_sep = ('\n' if newline else ' ') if sep is None else sep
    if isinstance(payload, str):
        return [MessageSegment.text(payload + resolved_sep), MessageSegment.at(uid)]
    if isinstance(payload, list):
        if len(payload) == 1 and getattr(payload[0], 'type', None) == 'image':
            return payload
        items = [MessageSegment.text(x) if isinstance(x, str) else x for x in payload]
        if resolved_sep:
            items.append(MessageSegment.text(resolved_sep))
        items.append(MessageSegment.at(uid))
        return items
    if getattr(payload, 'type', None) == 'image':
        return payload
    items = [payload]
    if resolved_sep:
        items.append(MessageSegment.text(resolved_sep))
    items.append(MessageSegment.at(uid))
    return items


async def send_reply(bot, ev, payload, *, at_sender: bool = True, newline: bool = False, sep: str | None = None):
    """Send a reply with @sender placed at the tail in group chats and at_sender=False."""
    is_group = bool(getattr(ev, 'group_id', None))
    uid = getattr(ev, 'user_id', None)
    if at_sender and is_group and uid:
        tailed = with_tail_at(payload, uid, is_group=True, newline=newline, sep=sep)
        if tailed is None:
            _log_plain_send(is_group, at_sender=True, payload=payload)
            return await bot.send(payload, at_sender=True)
        payload = tailed
    _log_plain_send(is_group, at_sender=False, payload=payload)
    return await bot.send(payload, at_sender=False)


def _log_plain_send(is_group: bool, *, at_sender: bool, payload) -> None:
    try:
        from gsuid_core.logger import logger
        from ..nikke_logs.store import describe_payload
    except ImportError:
        return
    try:
        logger.info(
            f'[AliceUID] 发送结构 route={"group" if is_group else "dm"} mode=plain '
            f'at_sender={at_sender} segments={describe_payload(payload)}'
        )
    except Exception:
        pass


# --- 1. 收菜提醒 (nikke_harvest) ---

def harvest_body(kind: str, pct: str, full_moment: str, *, style: str | None = None) -> str:
    if is_alice_style(style):
        if kind == 'stop':
            return '兔子先生连续两天晚上都没来收菜，保管箱一直是满的（MAX），爱丽丝先帮您把收菜提醒静悄悄关掉啦，不打扰您休息。'
        if kind == 'full':
            return '啊，兔子先生！资源保管箱已经装得满满的（MAX）啦，再不收就要溢出来咯，快上线查收吧！'
        if kind == 'bed':
            return f'嗯……兔子先生，保管箱当前容量是{pct}%，预计{full_moment}就会装满（MAX）哦。'
        return f'兔子先生，资源保管箱容量已经达到{pct}%啦，预计{full_moment}达到MAX，有空记得上线把资源收走哦～'
    if kind == 'stop':
        return '指挥官，您的资源保管箱在连续两天23点检查时均为MAX，已自动关闭该账号在所有会话中的收菜提醒，并停止后台检查。'
    if kind == 'full':
        return '指挥官，您的资源保管箱容量已达到MAX，请及时上线收取资源。'
    text = f'指挥官，您的资源保管箱{"当前容量为" if kind == "bed" else "容量已达到"}{pct}%，预计{full_moment}达到MAX'
    return text + ('。' if kind == 'bed' else '，请及时上线收取资源。')


def harvest_footer(kind: str, quiet_period: str, prefix: str, *, style: str | None = None) -> str:
    if kind == 'stop':
        if is_alice_style(style):
            return f'想重新开启时，在群聊或私聊里发送“{prefix}开启收菜提醒”叫爱丽丝就可以啦。'
        return f'如需恢复，请在需要接收提醒的群聊或私聊中发送“{prefix}开启收菜提醒”。'
    if kind == 'bed':
        base = f'收菜提醒免打扰时段：北京时间{quiet_period.replace("-", "—")}。\n建议睡前上线收取资源。'
        return base + ('嘿嘿，兔子先生今晚也要做个好梦哦～' if is_alice_style(style) else '')
    return ''


def harvest_enable_text(where: str, created: bool, *, at_str: str = '', pct: str = '',
                        is_full: bool = False, t90_str: str = '', full_str: str = '',
                        quiet_str: str = '关闭', style: str | None = None) -> str:
    if not created:
        if is_alice_style(style):
            return f'[AliceUID·收菜提醒已开启]\n兔子先生，{where}的收菜提醒已经开着啦，爱丽丝正替您盯着呢。'
        return f'[AliceUID·收菜提醒已开启]\n指挥官，{where}已开启，无需重复操作。'
    if is_alice_style(style):
        detail = ('资源保管箱已经达到满仓提醒线（99%及以上）啦，快去收一下吧！\n' if is_full else
                  f'预计{t90_str}达到90%，{full_str}装满（MAX）。\n')
        return (
            f'[AliceUID·收菜提醒已开启]\n'
            f'遵命！爱丽丝会在{where}替兔子先生看管保管箱的。\n'
            f'当前容量（{at_str}）：{pct}%。\n'
            + detail
            + f'免打扰时段：{quiet_str}（北京时间）。\n'
            + '到90%和装满时爱丽丝都会提醒您（如果连续两晚都没来收取，会自动帮您暂停提醒）。'
        )
    detail = ('资源保管箱已达到满仓提醒阈值（99%及以上）。\n' if is_full else
              f'预计{t90_str}达到90%，{full_str}达到MAX。\n')
    return (
        f'[AliceUID·收菜提醒已开启]\n指挥官，已在{where}开启您的收菜提醒。\n'
        f'最近查询容量（{at_str}）：{pct}%。\n'
        + detail
        + f'收菜提醒免打扰时段：{quiet_str}（北京时间）。\n'
        + '将在90%和满仓时分别提醒一次（连续两晚未收取将自动暂停提醒）。'
    )


def harvest_disable_text(where: str, all_stopped: bool, *, style: str | None = None) -> str:
    if is_alice_style(style):
        text = f'[AliceUID·收菜提醒已关闭]\n好，爱丽丝已经帮兔子先生关掉{where}的收菜提醒啦（其他会话里的提醒不受影响）。'
        if all_stopped:
            text += '\n目前所有会话都已关闭，爱丽丝先停下后台检查咯。'
        return text
    text = f'[AliceUID·收菜提醒已关闭]\n指挥官，已关闭{where}中的收菜提醒，您在其他会话中开启的提醒不受影响。'
    if all_stopped:
        text += '\n该账号已无开启的提醒会话，后台检查已停止。'
    return text


def harvest_quiet_text(period: str | None, *, style: str | None = None) -> str:
    val = period or '关闭'
    if is_alice_style(style):
        return f'[AliceUID·收菜免打扰已设置]\n遵命！当前会话免打扰已设为：{val}（北京时间），休息时间爱丽丝不会吵醒兔子先生的。'
    return f'[AliceUID·收菜免打扰已设置]\n当前会话：{val}（北京时间）。仅影响收菜提醒。'


# --- 2. 兑换码 (nikke_cdk) ---

def cdk_already_redeemed_text(code: str, when: str, *, style: str | None = None) -> str:
    if is_alice_style(style):
        return (
            f'[AliceUID·兑换结果]\n嘿嘿，兔子先生，这个兑换码（{code}）爱丽丝已经在 {when} 帮你悄悄兑好啦！'
            '礼物已经在游戏邮箱里乖乖等着你，快上线查收吧～'
        )
    return f'[AliceUID·兑换结果]\n兑换码 {code} 已于 {when}（北京时间）兑换过，请前往游戏邮箱查收。'


def cdk_all_claimed_note(*, style: str | None = None) -> str:
    if is_alice_style(style):
        return '兔子先生，当前所有有效兑换码爱丽丝都帮你领完啦，快去游戏邮箱看看吧～'
    return '当前所有有效兑换码均已领取，请前往游戏邮箱查看。'


def cdk_auto_start_notice(source_text: str, codes: str, *, only_user: bool = False, style: str | None = None) -> str:
    if only_user:
        if is_alice_style(style):
            return titled('自动兑换', '好，检测到兔子先生刚绑定好账号，爱丽丝正在帮您核对当前全部有效的兑换码哦～')
        return titled('自动兑换', '新绑定账号，正在核对当前有效兑换码。')
    if is_alice_style(style):
        return titled(
            '自动兑换',
            f'啊，兔子先生！爱丽丝在 {source_text} 发现了新的兑换码小礼物：\n{codes}\n正在帮大家执行自动兑换任务，稍微等我一下哦～',
        )
    return titled('自动兑换', f'在 {source_text} 发现新增兑换码：\n{codes}\n正在执行自动兑换任务。')


def cdk_auto_group_summary(total: int, bad_count: int, *, only_user: bool = False, style: str | None = None) -> str:
    ok_count = total - bad_count
    if only_user:
        if is_alice_style(style):
            head = '嘿嘿，兔子先生，新绑定账号的兑换码爱丽丝已经帮您核对完啦～' if not bad_count else '兔子先生，新绑定账号的兑换码核对未全部完成。'
            return titled('自动兑换结果', f'{head}（成功{ok_count}人｜未完成{bad_count}人）')
        head = '新绑定账号兑换码核对完成。' if not bad_count else '新绑定账号兑换码核对未全部完成。'
        return titled('自动兑换结果', f'{head}\n成功{ok_count}人｜未完成{bad_count}人')
    if is_alice_style(style):
        if not bad_count:
            return titled('自动兑换结果', f'嘿嘿，兔子先生，这次的新兑换码爱丽丝已经帮本群全员成功领好啦，记得去游戏邮箱查收礼物哦～（成功{ok_count}人｜未完成0人）')
        return titled('自动兑换结果', f'兔子先生，新增兑换码自动兑换已结束，部分用户未能完成（成功{ok_count}人｜未完成{bad_count}人）。')
    head = ('本群参与本次自动兑换的绑定用户已全员成功兑换（含已领取）。' if not bad_count else
            '新增兑换码自动兑换已结束，部分用户未能完成。')
    return titled('自动兑换结果', f'{head}\n成功{ok_count}人｜未完成{bad_count}人')


# --- 3. 社区签到 (nikke_community) ---

def community_enable_text(sign_time: str, prefix: str, *, style: str | None = None) -> str:
    if is_alice_style(style):
        return titled(
            '自动社区',
            f'遵命！爱丽丝每天北京时间{sign_time}起会替兔子先生自动签到与浏览社区帖子。'
            f'（如需自动点赞，可另发 {prefix}自动社区 点赞开启；连续三天失败会自动暂停）',
        )
    return titled(
        '自动社区',
        f'已授权当前账号每日自动签到及浏览；每天北京时间{sign_time}开始按账号依次执行。'
        f'如需点赞可另发 {prefix}自动社区 点赞开启；连续三个签到周期失败后自动关闭。',
    )


def community_group_summary_header(counts, day: str, today: bool, complete: bool, *, style: str | None = None) -> str:
    status_icon = '✅' if complete else '⚠️'
    scope_day = '今天' if today else f'{day}周期'
    if is_alice_style(style):
        text = f'[AliceUID·社区自动签到] {status_icon}'
        if complete:
            text += f'\n嘿嘿，兔子先生，{scope_day}的社区签到爱丽丝已经帮大家办好啦～（本群签到成功{counts["成功"]}人，签到失败{counts["失败"]}人，{counts["未开启"]}人尚未开启自动签到）'
        else:
            text += f'\n兔子先生，{scope_day}自动签到已处理完毕（本群签到成功{counts["成功"]}人，签到失败{counts["失败"]}人，{counts["未开启"]}人尚未开启自动签到）。'
        return text
    text = f'[AliceUID·社区自动签到] {status_icon}'
    prefix = '' if today else f'{day}周期'
    text += f'\n{prefix}本群共签到成功{counts["成功"]}人，共签到失败{counts["失败"]}人，{counts["未开启"]}人尚未开启自动签到。'
    return text


# --- 4. 耗时等待提示 (roster / export / profile / character) ---

def wait_roster_generating(*, merged: bool = False, mode: str = 'main', style: str | None = None) -> str:
    tag = '主力妮姬' if mode == 'main' else '图鉴展示'
    noun = '主力妮姬卡片' if mode == 'main' else '完整图鉴卡片'
    if is_alice_style(style):
        if merged:
            return titled(tag, f'兔子先生，{noun}正在为您加紧绘制中，稍微等爱丽丝一小会儿哦～')
        return titled(tag, f'好~，爱丽丝正在核对兔子先生的阵容并绘制{noun}，首次准备头像可能会稍久一点哦～')
    if merged:
        return titled(tag, f'你的{noun}正在生成，请稍候。')
    return titled(tag, f'正在核对本人阵容并生成{noun}，首次准备肖像可能稍久。')


def wait_export_running(*, style: str | None = None) -> str:
    if is_alice_style(style):
        return titled('练度导出', '兔子先生，您的练度表正在整理发送中，请稍微等爱丽丝一下哦～')
    return titled('练度导出', '你的练度表正在生成或发送，请稍候；本次不会重复导出。')


def wait_panel_refresh(*, merged: bool = False, style: str | None = None) -> str:
    if is_alice_style(style):
        if merged:
            return titled('刷新面板', '兔子先生，资料和角色数据已经在努力缓存中啦，稍微等爱丽丝一下哦～')
        return titled('刷新面板', '遵命！爱丽丝正在帮兔子先生重新整理本人资料、全部角色练度与皮肤缓存，完成后立刻把最新的信息图送过来哦～')
    if merged:
        return titled('刷新面板', '本人资料与角色数据正在缓存，请稍候；已合并重复请求。')
    return titled('刷新面板', '正在刷新本人资料、全部角色练度与皮肤缓存；完成后发送最新信息图。')


def wait_character_single_query(role_name: str, *, style: str | None = None) -> str:
    if is_alice_style(style):
        return titled('角色面板', f'本地名单里暂时没看到「{role_name}」，爱丽丝正在帮兔子先生单独去查一下，稍微等我一下哦～')
    return titled('角色面板', f'本地记录未持有「{role_name}」，正在单独查询该角色，请稍候。')


def wait_export_public(*, style: str | None = None) -> str:
    if is_alice_style(style):
        return titled('练度导出', '遵命！爱丽丝正在帮兔子先生整理全部角色的完整练度信息，数据量比较大可能会慢一点，请耐心等我一下哦～')
    return titled('练度导出', '正在获取全部角色的完整练度信息，数据量较大，可能需要较长时间，请耐心等待。')


def wait_profile_refresh(*, style: str | None = None) -> str:
    if is_alice_style(style):
        return titled('刷新信息', '好，爱丽丝正在帮兔子先生快速刷新一下名片资料，很快就好哦～')
    return titled('刷新信息', '正在轻量刷新本人名片资料，不读取全部角色装备详情。')


def solo_wait_text(ahead: int = 0, *, style: str | None = None) -> str:
    if ahead > 0:
        if is_alice_style(style):
            return titled('个人突袭', f'兔子先生，现在还有 {ahead} 位小伙伴在前面排队测算呢，爱丽丝已经帮您占好位置啦，稍等一下就轮到您哦～')
        return titled('个人突袭', f'当前正在处理其他用户的单人突袭推荐，已为你排队，前方还有{ahead}个任务。')
    if is_alice_style(style):
        return titled('个人突袭', '遵命！爱丽丝正在帮兔子先生从 DILDORO 测算个人突袭推荐阵容，大概需要几十秒，稍微等我一下哦～')
    return titled('个人突袭', '正在从 https://dildoro.com/ 查询并生成个人突袭推荐，请稍候；更为详细的计算请直接访问该网站。')


def solo_privacy_text(label: str, *, style: str | None = None) -> str:
    if is_alice_style(style):
        return titled(
            '个人突袭',
            f'嗯……兔子先生的官网妮姬资料现在是「{label}」状态。为了完成这次推荐，'
            '爱丽丝会先临时帮您设为所有人可见，查询可能稍慢一点，完成后会恢复原状的（期间其他访问者也能看到资料哦）。',
        )
    return titled('个人突袭', f'你的官网妮姬资料当前为{label}。为本次推荐将临时设为所有人可见，查询可能较慢；期间其他访问者也可读取资料。')


# --- 5. 角色别名管理 (nikke_character.alias_commands) ---

def alias_owner_only_text(action: str = '维护角色别名', *, style: str | None = None) -> str:
    if is_alice_style(style):
        return titled('角色别名', f'唔……兔子先生，{action}这项工作只有 Bot 主才能操作哦。')
    return titled('角色别名', f'仅Bot主可{action}。')


def alias_add_text(role_name: str, alias: str, *, style: str | None = None) -> str:
    if is_alice_style(style):
        return titled('角色别名', f'嘿嘿，爱丽丝已经帮兔子先生记下新称呼啦：{role_name} → {alias}')
    return titled('角色别名', f'已添加：{role_name} → {alias}')


def alias_remove_text(role_name: str, alias: str, *, style: str | None = None) -> str:
    if is_alice_style(style):
        return titled('角色别名', f'好~，爱丽丝已经帮兔子先生把这个别名划掉啦～（已注销：{role_name} × {alias}）')
    return titled('角色别名', f'已注销：{role_name} × {alias}')


def alias_export_notice(kind: str, *, style: str | None = None) -> str:
    if is_alice_style(style):
        mapping = {
            'busy': '兔子先生，爱丽丝正在整理并发送别名表呢，稍微等我一下下哦～',
            'unconfirmed': '唔……别名表已经生成好啦，但没有收到接入端的发送确认，请检查文件上传支持哦。',
            'failed': '啊……别名表导出或发送失败了，请兔子先生检查本地别名文件与接入端权限。',
        }
        return titled('别名导出', mapping[kind])
    mapping = {
        'busy': '别名表正在导出或发送，请稍候。',
        'unconfirmed': '别名表已生成，但发送未确认，请检查接入端文件上传支持。',
        'failed': '别名表导出或文件发送失败，请检查本地别名文件与接入端权限。',
    }
    return titled('别名导出', mapping[kind])
