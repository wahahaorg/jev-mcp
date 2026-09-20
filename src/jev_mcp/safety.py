"""Small, explicit guardrails for a browsing-only browser agent."""

from __future__ import annotations

import re
from collections.abc import Mapping


class SensitiveActionBlocked(RuntimeError):
    """Raised before an action that exceeds the browsing-only scope is executed."""


# These are intentionally conservative. The agent may browse commerce sites, but it must not transact,
# disclose credentials, or supply personal data without a separately designed approval flow.
GOAL_BLOCKLIST = re.compile(
    r"\b(?:buy now|checkout|place (?:an )?order|submit (?:an )?order|pay(?:ment)?|"
    r"transfer money|upload (?:a )?(?:file|document)|log ?in|sign ?in|password)\b|"
    r"(?:立即购买|购买|下单|提交订单|付款|支付|结算|转账|上传(?:文件|证件)?|登录|登入|密码)",
    re.IGNORECASE,
)
ACTION_BLOCKLIST = re.compile(
    r"\b(?:buy(?: now)?|purchase|add to (?:cart|bag)|checkout|place order|submit order|"
    r"pay(?:ment)?|confirm (?:and )?pay|complete purchase|upload|password|cvv|card number|"
    r"verification code)\b|(?:立即购买|购买|加入购物车|购物车|下单|提交订单|付款|支付|结算|"
    r"确认支付|上传|密码|验证码|银行卡)",
    re.IGNORECASE,
)
SENSITIVE_FIELD_BLOCKLIST = re.compile(
    r"\b(?:password|passcode|cvv|card number|security code|verification code|"
    r"home address|phone number)\b|(?:密码|验证码|银行卡|卡号|安全码|家庭住址|手机号)",
    re.IGNORECASE,
)


def ensure_safe_goal(goal: str) -> None:
    """Reject a goal that requests an operation outside read-only product browsing."""
    if GOAL_BLOCKLIST.search(goal):
        raise SensitiveActionBlocked(
            "This server is browsing-only. It will not log in, upload files, disclose credentials, "
            "place orders, or make payments. Rephrase the goal as search, filter, view, or extract."
        )


def ensure_safe_action(action: Mapping[str, object]) -> None:
    """Reject an observed control if executing it could make a purchase or reveal sensitive data."""
    label = str(action.get("label", ""))
    kind = str(action.get("kind", ""))
    if ACTION_BLOCKLIST.search(label):
        raise SensitiveActionBlocked(f"Blocked sensitive browser control: {label!r}.")
    if kind == "fill" and SENSITIVE_FIELD_BLOCKLIST.search(label):
        raise SensitiveActionBlocked(f"Blocked sensitive form field: {label!r}.")
