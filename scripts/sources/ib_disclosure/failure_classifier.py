"""Classify an IB download failure from the evidence captured at fetch time.

Both download_client.py (which tags a DownloadResult the moment it happens)
and scripts/analyze_ib_download_failures.py (which re-derives/aggregates
from what was already stored in document_registry.metadata) import this, so
the two always agree on categories and a rule change here doesn't require
re-crawling -- the analyze script can re-classify stored evidence with the
current rules any time.

Categories (the "suggested_action" table from the task):
  - source_not_found     : document/page genuinely says the item doesn't
                           exist or was taken down -> SOURCE_BROKEN, don't
                           retry harder.
  - session_expired      : looks like the ASP.NET session/viewstate was
                           stale (a "系統逾時"/timeout/expired-session style
                           page) -> fixable in download_client.py's request
                           flow (fresh GET immediately before POST already
                           happens; if this fires anyway, investigate cookie
                           handling).
  - event_target_error   : detail page loaded fine but returned a generic
                           postback-rejected / no-such-control error ->
                           likely the wrong __EVENTTARGET was parsed out of
                           the urn:ib-linkbutton placeholder.
  - server_error         : ASP.NET unhandled exception / 5xx-shaped page ->
                           probably transient, worth a retry with backoff.
  - waf_blocked          : IB's edge/WAF rejected the request outright (not
                           an application-level response at all) -> back off
                           and slow down, not a parser or source problem.
  - inline_text_available : the postback produced no download link and the
                           response doesn't look like an error either --
                           this LinkButton was likely never a real file
                           download. NOTE: this is a fallback GUESS from a
                           failed download attempt's evidence; the reliable,
                           first-class path for inline text is
                           resolve_ib_product_details.py's _inline_text_entry,
                           which reads it straight off the detail page (no
                           failed postback needed at all) and marks the row
                           INLINE_TEXT_AVAILABLE, never BROKEN_LINK/NOT_LISTED,
                           so it never reaches this classifier in the first
                           place. This category exists for a document that
                           *did* look like a real LinkButton but turned out
                           to have nothing behind it.
  - html_error_unknown   : html_error but none of the above patterns
                           matched -- needs a human look before adding a new
                           category.

This module never makes network calls and never mutates the database; it's
pure pattern matching over already-captured text.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from source_response_classifier import classify_source_response  # noqa: E402

# IB/ASP.NET-specific patterns that scripts/source_response_classifier.py's
# source-agnostic patterns don't (and shouldn't) know about -- these are
# checked before delegating to the shared classifier below. Everything that
# WAS a generic "page says the thing is broken" pattern (not_found,
# server_error, waf_blocked) has moved to source_response_classifier.py so
# there's one place, not two independently-drifting copies -- see this
# module's own docstring.
_WAF_TRIGGER_SUBSTRINGS = ("drop",)  # keep in sync with download_client.WAF_TRIGGER_SUBSTRINGS
_SESSION_PATTERNS = (
    "逾時", "Session", "session state", "過期", "已逾期", "請重新登入", "驗證失敗",
    "Server was unable to process request", "State Server", "viewstate is invalid",
    "無法載入檢視狀態",
)
_EVENT_TARGET_PATTERNS = (
    "Invalid postback or callback argument", "找不到控制項", "無法找到具有識別項",
    "Cannot find control", "__EVENTTARGET",
)

# Maps scripts/source_response_classifier.py's source-agnostic categories to
# this module's richer IB-specific vocabulary. captcha_required/
# browser_required have no IB equivalent (IB has no CAPTCHA and every page
# is plain server-rendered HTML -- see query_client.py's module docstring)
# so a hit there is surfaced as html_error_unknown for a human to look at,
# rather than silently invented an IB-specific meaning for something that's
# never actually been seen on this source.
_SHARED_CATEGORY_TO_IB_CATEGORY = {
    "waf_blocked": "waf_blocked",
    "not_found": "source_not_found",
    "server_error": "server_error",
    "rate_limited": "waf_blocked",
    "login_required": "session_expired",
    "captcha_required": "html_error_unknown",
    "browser_required": "html_error_unknown",
    "html_error": "html_error_unknown",
}


@dataclass
class FailureEvidence:
    status_code: int = 0
    content_type: str = ""
    content_length: int = 0
    final_url: str = ""
    title: str = ""
    text_sample: str = ""  # first ~500 chars of plain text
    stage: str = ""  # "resolve" (postback never returned a download link) | "fetch" (DownLoad.aspx returned HTML)
    snapshot_path: str = ""
    extra: dict = field(default_factory=dict)


def _matches_any(haystack: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        if pattern.lower() in haystack.lower():
            return pattern
    return None


def classify(evidence: dict) -> dict:
    """`evidence` is a plain dict shaped like FailureEvidence (as stored in
    document_registry.metadata["download_error"]). Returns
    {"category": ..., "matched_pattern": ..., "reasoning": ...}.
    """
    title = str(evidence.get("title") or "")
    text_sample = str(evidence.get("text_sample") or "")
    haystack = f"{title}\n{text_sample}"

    # waf_false_positive: the request was (or would have been) rejected by
    # the WAF because the download token itself contains a substring proven
    # to trip its signature -- see download_client.WAF_TRIGGER_SUBSTRINGS.
    # Covers both a preflight skip (never sent) and older rows recorded as
    # plain waf_blocked whose stored final_url carries such a token.
    token = str(evidence.get("final_url") or "").split("file=", 1)[-1].lower()
    if evidence.get("preflight_match") or (
        "file=" in str(evidence.get("final_url") or "")
        and any(sub in token for sub in _WAF_TRIGGER_SUBSTRINGS)
        and classify_source_response(
            status_code=int(evidence.get("status_code") or 0), content_type="text/html", text_preview=haystack
        ).category == "waf_blocked"
    ):
        return {
            "category": "waf_false_positive",
            "matched_pattern": evidence.get("preflight_match") or "token-signature",
            "reasoning": "下載 token 含 WAF 會誤判的字串，重試必定被擋；不繞過，需從其他來源取得",
        }

    # IB/ASP.NET-specific checks first -- see _EVENT_TARGET_PATTERNS'
    # comment above for why these can't live in the source-agnostic
    # classifier. event_target_error before session_expired: a postback
    # rejection page can incidentally also mention "session" in its
    # boilerplate, and the more actionable diagnosis (wrong event target)
    # should win.
    match = _matches_any(haystack, _EVENT_TARGET_PATTERNS)
    if match:
        return {
            "category": "event_target_error",
            "matched_pattern": match,
            "reasoning": "ASP.NET 拒絕此 postback，可能是 event target 解析錯誤",
        }

    match = _matches_any(haystack, _SESSION_PATTERNS)
    if match:
        return {"category": "session_expired", "matched_pattern": match, "reasoning": "頁面文字指出 session/viewstate 已逾期或失效"}

    # Delegate the source-agnostic signals (waf/not_found/server_error/...)
    # to scripts/source_response_classifier.py -- see module docstring.
    # expected_binary=True: every evidence dict reaching this function came
    # from an attempt that expected a downloadable file (see
    # download_client.py's html_error/no_download_link paths), so an
    # otherwise-unclassified HTML response is itself already suspicious.
    shared = classify_source_response(
        status_code=int(evidence.get("status_code") or 0),
        content_type=str(evidence.get("content_type") or ""),
        text_preview=haystack,
        final_url=str(evidence.get("final_url") or ""),
        expected_binary=True,
    )
    mapped_category = _SHARED_CATEGORY_TO_IB_CATEGORY.get(shared.category)
    if mapped_category:
        matched_pattern = shared.matched_signals[0] if shared.matched_signals else None
        return {"category": mapped_category, "matched_pattern": matched_pattern, "reasoning": shared.reasoning}

    # shared.category is "ok" or "unknown" here -- this function is only
    # ever called on evidence FROM a failed download attempt, so neither of
    # those is a real answer; fall through to the IB-specific
    # inline_text_available heuristic, then the final catch-all.
    content_type = str(evidence.get("content_type") or "")
    if "html" in content_type.lower() and evidence.get("stage") == "resolve" and not evidence.get("content_length"):
        return {
            "category": "inline_text_available",
            "matched_pattern": None,
            "reasoning": "postback 未回傳任何 window.open 下載連結，可能該按鈕本來就不是檔案下載",
        }

    return {"category": "html_error_unknown", "matched_pattern": None, "reasoning": "html_error 但不符合任何已知樣式，需要人工檢視"}


_SUGGESTED_ACTION = {
    "source_not_found": "標記 SOURCE_BROKEN，不需要硬救",
    "session_expired": "檢查 download client 的 session/cookie 流程",
    "event_target_error": "修 parser 解析出的 event target / postback payload",
    "server_error": "加 retry/backoff，可能是暫時性錯誤",
    "waf_false_positive": "WAF 誤判（token 含觸發字串）：不重試、不繞過；改從公司官網/其他來源取得，或向 IB 反映",
    "waf_blocked": "調高 --delay-seconds、降低重測頻率後再重試，不要調查 parser",
    "inline_text_available": "不列入下載候選，改存 inline text（理想上應在 resolve 階段就被 _inline_text_entry 撿到，不該走到這裡）",
    "html_error_unknown": "需要人工檢視樣本後才能分類",
    "unclassified_legacy": "低速重測（--retest）以補齊 evidence，不要整批重跑",
}


def suggested_action(category: str) -> str:
    return _SUGGESTED_ACTION.get(category, _SUGGESTED_ACTION["html_error_unknown"])


_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def extract_title_and_text(html: str, max_chars: int = 500) -> tuple[str, str]:
    """Best-effort plain-text extraction without pulling in a full HTML
    parser dependency here -- download_client.py already has BeautifulSoup
    available via query_client.py's extract_hidden_fields, but this module
    is meant to stay dependency-free so scripts/analyze_ib_download_failures.py
    can re-run classification over stored evidence without a live parse.
    """
    title_match = _TITLE_RE.search(html)
    title = title_match.group(1).strip() if title_match else ""
    text_only = _TAG_RE.sub(" ", html)
    text_only = re.sub(r"\s+", " ", text_only).strip()
    return title, text_only[:max_chars]
