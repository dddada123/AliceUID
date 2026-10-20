"""Official email UI adapter; selectors inspected on 2026-10-17.

No direct authentication HTTP implementation: the official SDK owns requests.
"""
from __future__ import annotations

import hashlib
import re
import time
from urllib.parse import urlsplit

EMAIL_FORM = "#loginCodeForm"
EMAIL_ACCOUNT = "#loginCodeForm_account"
EMAIL_CODE = '#loginCodeForm input[placeholder="電郵驗證碼"]'


class EmailCooldown:
    """Process-local limiter; independent user and mailbox buckets survive mode changes."""

    def __init__(self, seconds=60):
        self.seconds = seconds
        self._until = {}

    @staticmethod
    def mailbox_key(email):
        return hashlib.sha256(email.strip().casefold().encode()).hexdigest()

    def confirm(self, user_id, bot_id, digest):
        until = time.time() + self.seconds
        for key in [('user', str(bot_id), str(user_id)), ('email', digest)]:
            self._until[key] = max(self._until.get(key, 0), until)
        return until

    def reserve(self, user_id, bot_id, email):
        now = time.time()
        self._until = {key: value for key, value in self._until.items() if value > now}
        digest = self.mailbox_key(email)
        keys = [('user', str(bot_id), str(user_id)), ('email', digest)]
        retry = max((self._until.get(key, 0) - now for key in keys), default=0)
        if retry > 0:
            return int(retry) + 1
        for key in keys:
            self._until[key] = now + self.seconds
        return 0


def valid_email(value):
    return len(value) <= 64 and bool(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value))


cooldown = EmailCooldown()


async def open_email_form(page, account):
    await page.get_by_text('電郵登入', exact=True).click()
    await page.wait_for_selector(EMAIL_ACCOUNT, timeout=15000)
    await page.fill(EMAIL_ACCOUNT, account)


class EmailResponses:
    """Keep only response status/ret, never account, code, token or raw body."""

    def __init__(self, page):
        self.page = page
        self.sent = False
        self.error = ""
        page.on('response', self.observe)

    async def observe(self, response):
        url = urlsplit(response.url)
        if url.scheme != 'https' or url.hostname != 'li-sg.intlgame.com' or url.path not in ('/account/sendcode', '/account/loginwithcode'):
            return
        try:
            data = await response.json()
            ret = data.get('ret')
            if type(ret) is not int or response.status != 200:
                self.error = "官方响应异常，结果未确认，请手动重试"
            elif url.path == '/account/sendcode':
                if ret == 0:
                    self.sent = True
                elif ret != 2170:  # Official SDK owns the same-action captcha continuation.
                    self.error = "邮件发送失败，请检查邮箱或稍后手动重试"
            elif ret != 0:
                self.error = "邮箱验证码无效或已过期，请手动重新发送" if ret in (2114, 2021, 2022) else "邮箱验证码登录失败，请检查输入后手动重试"
        except Exception:
            self.error = "官方响应异常，结果未确认，请手动重试"

    def check(self):
        if self.error:
            from .browser import LoginError
            raise LoginError(self.error)

    def close(self):
        self.page.remove_listener('response', self.observe)


async def send_email_code(page, ctx, account, deadline, on_captcha, wait_official):
    feedback = EmailResponses(page)
    try:
        await open_email_form(page, account)
        account = ''
        # One click per explicit user action; countdown is NOT evidence of success.
        await page.locator(EMAIL_FORM).get_by_role('button', name='獲取', exact=True).click()
        async def confirmed():
            feedback.check()
            return feedback.sent
        await wait_official(ctx, page, deadline, on_captcha, confirmed)
        return feedback
    except BaseException:
        feedback.close()
        raise


async def submit_email_code(page, code):
    try:
        await page.fill(EMAIL_CODE, code)
        async with page.expect_request(
            lambda request: request.url.split('?')[0] == 'https://li-sg.intlgame.com/account/loginwithcode',
            timeout=15000,
        ):
            await page.locator(EMAIL_FORM).locator('button[type="submit"]').click()
    finally:
        code = ''
        # Clear the official React input even on rejection. The SDK retains its
        # own request value only until that in-flight request completes.
        try:
            await page.fill(EMAIL_CODE, '')
        except Exception:
            pass
