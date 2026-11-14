"""Distinguish temporary website failures from account/configuration errors."""


class SoloUnavailable(Exception):
    pass


class SoloTransient(SoloUnavailable):
    def __init__(self, message, *, stage='', reason=''):
        super().__init__(message)
        self.stage = stage
        self.reason = reason


class RetryAborted(Exception):
    """The binding or permission changed while a request was running."""
