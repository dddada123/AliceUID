"""Full owned-roster share cards; integration remains lazy for offline tests."""

def setup(policy=None, scheduler=None):
    from .commands import setup as register
    return register(policy=policy, scheduler=scheduler)


def invalidate_binding(bind):
    from .service import invalidate_binding as invalidate
    return invalidate(bind)


def invalidate_actor(actor, bot):
    from .service import invalidate_actor as invalidate
    return invalidate(actor, bot)


def mark_sent(prepared):
    from .service import mark_sent as mark
    return mark(prepared)
