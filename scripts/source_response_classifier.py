"""Classify an HTTP response as ok / blocked / error / etc, source-agnostic.

Concept borrowed from two places (see each function's own docstring for
which signal came from where):
  - C:/Users/rabbi/OneDrive/桌面/crawler-v1/BLOCKED_RESTRICTED_DETECTION_SPEC.md
    (remote YZU1507A/universal-crawler) -- the family/signal/recommended-action
    shape of the classification result, and the general principle that a
    blocked/CAPTCHA/error page must never silently look like a success.
  - scripts/sources/ib_disclosure/failure_classifier.py (this project, from
    the previous phase) -- the concrete patterns already verified live
    against real IB/TII responses (waf_blocked's "Request Rejected... Your
    support ID is", source_not_found's "不存在", etc).

What's deliberately NOT carried over from crawler-v1: its `robots_disallowed`
family (this project's crawlers don't crawl broad sitemaps against a robots
policy -- IB/TII are specific, publicly-invited query forms, see
scripts/sources/ib_disclosure/README.md) and its `blocked_page` family
being Cloudflare/Incapsula-specific (kept as a generic `waf_blocked`
instead, since IB's own edge device isn't either of those two).

This module is the SINGLE source of pattern-matching truth for "what kind of
response is this" across every source in this project.
scripts/sources/ib_disclosure/failure_classifier.py now delegates its
pattern matching here (see its own docstring) instead of keeping a second,
independently-drifting copy of the same patterns.

Usage:
    result = classify_source_response(
        status_code=200,
        content_type="text/html",
        text_preview="Request Rejected ... Your support ID is: 123",
        final_url="https://ins-info.ib.gov.tw/FSC/DownLoad.aspx?file=...",
    )
    result.category  # "waf_blocked"
"""

from __future__ import annotations

from dataclasses import dataclass, field

CATEGORIES = (
    "ok",
    "not_found",
    "rate_limited",
    "server_error",
    "captcha_required",
    "waf_blocked",
    "login_required",
    "browser_required",
    "html_error",
    "unknown",
)

# Categories that must never be treated as content a RAG/chunking pipeline
# can index -- see BLOCKED_RESTRICTED_DETECTION_SPEC.md's "chatbot_indexable
# = false" requirement. "ok" is the only indexable outcome.
NON_INDEXABLE_CATEGORIES = frozenset(c for c in CATEGORIES if c != "ok")

_RECOMMENDED_ACTION = {
    "ok": "index",
    "not_found": "mark_source_broken",
    "rate_limited": "backoff_and_retry_later",
    "server_error": "retry_with_backoff",
    "captcha_required": "do_not_index_manual_review",
    "waf_blocked": "slow_down_and_retry_later",
    "login_required": "do_not_index_manual_review",
    "browser_required": "needs_browser_rendering",
    "html_error": "check_expected_content_type",
    "unknown": "manual_review",
}

# Verified live 2026-09-14 against real IB responses (see
# scripts/sources/ib_disclosure/failure_classifier.py's history) unless
# noted otherwise. Order within classify_source_response() matters -- most
# specific/unambiguous signals are checked first.
_CAPTCHA_PATTERNS = (
    "captcha", "驗證碼", "查詢識別碼", "請輸入圖形", "人機驗證", "i'm not a robot", "i am not a robot",
)
_WAF_PATTERNS = (
    "request rejected", "the requested url was rejected", "your support id is",
    "incapsula", "cloudflare ray id", "attention required", "bot detection",
    "unusual connection", "reference id",
)
_LOGIN_PATTERNS = (
    "請先登入", "請重新登入", "session 已逾期", "session has expired", "please log in", "please sign in",
    "驗證失敗",
)
_NOT_FOUND_PATTERNS = (
    "找不到您要瀏覽的網頁", "找不到檔案", "檔案不存在", "資料不存在", "查無資料", "查無此檔案",
    "已下架", "已移除", "the resource you are looking for", "file not found", "page not found",
    "not found", "不存在",
)
_SERVER_ERROR_PATTERNS = (
    "server error", "發生錯誤", "object reference", "unhandled exception", "runtime error", "應用程式錯誤",
)
_BROWSER_REQUIRED_PATTERNS = (
    "enable javascript", "請啟用 javascript", "javascript is required", "noscript",
)


@dataclass(frozen=True)
class SourceResponseClassification:
    category: str
    matched_signals: tuple[str, ...] = field(default_factory=tuple)
    reasoning: str = ""
    chatbot_indexable: bool = False
    recommended_action: str = "manual_review"


def _matches(haystack: str, patterns: tuple[str, ...]) -> str | None:
    lowered = haystack.lower()
    for pattern in patterns:
        if pattern.lower() in lowered:
            return pattern
    return None


def classify_source_response(
    *,
    status_code: int,
    content_type: str = "",
    text_preview: str = "",
    final_url: str = "",
    expected_binary: bool = False,
) -> SourceResponseClassification:
    """Classify one HTTP response. `expected_binary` -- the caller expected
    a file (PDF/DOC/XLS/...) but got something back with an HTML content
    type -- is what turns an otherwise-generic 200 into `html_error`
    (mirrors download_client.py's "DownLoad.aspx returned HTML instead of a
    file" check, generalized for any source).
    """
    content_type = (content_type or "").lower()
    haystack = text_preview or ""

    def _result(category: str, matched: str | None, reasoning: str) -> SourceResponseClassification:
        return SourceResponseClassification(
            category=category,
            matched_signals=(matched,) if matched else (),
            reasoning=reasoning,
            chatbot_indexable=(category == "ok"),
            recommended_action=_RECOMMENDED_ACTION[category],
        )

    # Text-based signals checked first regardless of status code -- IB/TII
    # both return these as ordinary HTTP 200 responses (see
    # failure_classifier.py's verified-live evidence), so gating on status
    # code alone would miss every one of them.
    match = _matches(haystack, _WAF_PATTERNS)
    if match:
        return _result("waf_blocked", match, "邊界設備/WAF 拒絕了這次請求，不是應用程式層級的錯誤")

    match = _matches(haystack, _CAPTCHA_PATTERNS)
    if match:
        return _result("captcha_required", match, "頁面要求圖形驗證碼或人機驗證")

    match = _matches(haystack, _LOGIN_PATTERNS)
    if match:
        return _result("login_required", match, "頁面要求登入或 session 已逾期")

    match = _matches(haystack, _NOT_FOUND_PATTERNS)
    if match:
        return _result("not_found", match, "頁面文字指出資源不存在或已下架")

    match = _matches(haystack, _SERVER_ERROR_PATTERNS)
    if match:
        return _result("server_error", match, "頁面呈現未處理例外或伺服器錯誤")

    match = _matches(haystack, _BROWSER_REQUIRED_PATTERNS)
    if match:
        return _result("browser_required", match, "頁面需要 JavaScript 渲染才有內容")

    # Status-code-based signals.
    if status_code == 429:
        return _result("rate_limited", "HTTP 429", "HTTP 429 Too Many Requests")
    if status_code == 404:
        return _result("not_found", "HTTP 404", "HTTP 404 Not Found")
    if status_code in (401, 403):
        # 401/403 without a clearer text signal above defaults to
        # login_required (a credential problem) rather than waf_blocked (an
        # infrastructure problem) -- see module docstring's table; callers
        # with a stronger prior can override by checking matched_signals.
        return _result("login_required", f"HTTP {status_code}", f"HTTP {status_code}，缺乏更明確文字線索，預設視為需要登入/授權")
    if 500 <= status_code < 600:
        return _result("server_error", f"HTTP {status_code}", f"HTTP {status_code} 伺服器錯誤")

    if expected_binary and "html" in content_type:
        return _result("html_error", None, "預期收到二進位檔案，實際收到 HTML")

    if 200 <= status_code < 300:
        return _result("ok", None, "")

    return _result("unknown", None, f"HTTP {status_code}，不符合任何已知樣式")
