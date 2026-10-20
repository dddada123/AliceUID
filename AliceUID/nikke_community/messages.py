"""Compact receipts based only on confirmed responses from this run."""


def result_message(result):
    kind = result['result']
    counts = result.get('counts', {})
    signed = result.get('signin_confirmed', False)
    parts = ['已完成本轮签到✅' if signed else '签到尚未确认⚠️']
    for action, label in (('like', '点赞'), ('browse', '浏览')):
        count = counts.get(action, 0)
        if count:
            parts.append(f'{label}{count}帖✅')
    points = result.get('points')
    if type(points) is int and points >= 0:
        parts.append(f'当前金币🪙：{points}')
    elif kind == 'completed':
        parts.append('金币余额暂不可用')
    message = ' '.join(parts)
    if kind == 'paused':
        return message + '\n后续任务已暂停⚠️ ' + result['reason'] + '；未自动重试。'
    if kind == 'cycle_changed':
        return message + '\n请求跨过北京时间08:00，本轮已停止并保留去重保护，请稍后核对状态。'
    if kind == 'unconfirmed' or (kind == 'completed' and not signed):
        message += '\n请到社区核对签到；结果不确定的提交不会重复发送。'
    if result.get('unknown_tasks'):
        message += '\n另有活动任务请到社区查看。'
    return message
