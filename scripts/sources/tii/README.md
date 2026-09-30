# scripts/sources/tii

Everything that turns TII (保發中心 / insprod.tii.org.tw) pages into
`SourceProductRecord`s. Three different pages on this site behave three
different ways -- read this before touching any of them.

| Page | Access | Handled by |
|---|---|---|
| `Query.aspx` (search form, incl. keyword-only/no-filter) | CAPTCHA-gated on every request | **never touched -- off-limits** |
| `ResultQueryAll.aspx?page=N` | Public, plain GET, no CAPTCHA (confirmed live) | `list_parser.py` |
| `DetailList.aspx?productId=...` | **Redirects to Query.aspx on direct access** (confirmed live, see below) | `detail_parser.py` -- but see the caveat |

## `Query.aspx`: never touched

Every query form on insprod.tii.org.tw -- including a bare company/type
filter with no keyword -- is gated by an image CAPTCHA ("查詢識別碼"). This
project does not automate solving CAPTCHAs and never submits this form.

## `ResultQueryAll.aspx?page=N`: the public full index

Confirmed live (2026-09-13): fetching `ResultQueryAll.aspx?page=1` with a
plain GET, no cookies, no referer tricks, returns "總共找到 195255 筆" and a
real 10-row product table with `DetailList.aspx?productId=...` links --
no CAPTCHA, no redirect. `list_parser.py` parses this page; the CLI is
`scripts/ingest_tii_result_pages.py`. See that script's module docstring for
the full scope (rate limiting, resume, the 403/429 stop rule).

This page only exposes three columns -- product name (as the detail link),
sale start date, sale end date -- so every record it produces has an empty
`company_name` (and no `documents`). See `list_parser.py`'s module docstring
for why that's left blank rather than guessed at, and note that
`reconcile_source_records.py` will skip these records until `company_name`
is filled in some other way.

## `DetailList.aspx?productId=...`: blocked, even for a plain GET

This is the important one. The original plan assumed a `productId` obtained
from a real search result (human-solved CAPTCHA, or read off
`ResultQueryAll.aspx`) could be fetched directly, the same way its
`Open2.ashx?id=<uuid>` attachment links can. **Verified live and it does
not work**, and the mechanism is easy to get wrong, so it's worth spelling
out precisely:

- It is *not* a server-side HTTP redirect. TII returns a normal 200 for
  `DetailList.aspx?productId=<any real id>`, whose body is a small
  `<script>` block: `alert("識別碼錯誤！"); location.href = "Query.aspx";`.
  A real browser executes that and lands on `Query.aspx` (confirmed via
  `window.location.href` after navigating there directly, cold session, no
  prior navigation, tried against two different real product ids from a
  live `ResultQueryAll.aspx` page) -- but a plain GET (what `TiiClient` and
  every script here does; no JS execution) never runs that script, so
  `response.url` never changes. The *only* reliable way to detect this from
  a plain fetch is the exact script text in the response body --
  `resolve_tii_details.py` checks for it explicitly, first, before anything
  else, with a same-URL / Query.aspx-form-text check kept only as a
  defensive fallback.
- Separately, and confirmed independently: once a browser session *does*
  follow that script to `Query.aspx`, `ResultQueryAll.aspx?page=1` --
  previously working fine in the same browser tab -- *also* started
  redirecting to `Query.aspx` on the next visit. That part does look like a
  session-level flag, applied browser-side by the executed script/session
  state, not something a script-only fetch (which never runs the redirect
  script to begin with) would trigger on its own.

We do not attempt to reverse-engineer whatever referer/session sequence
would satisfy that check -- that would be probing for a bypass to an access
control the site clearly intends, which is exactly the kind of thing this
project avoids doing to the CAPTCHA. `scripts/resolve_tii_details.py`
therefore makes one honest, plain GET per URL (via `TiiClient`, same as
everything else here), detects the `Query.aspx` redirect by its final URL
(and, defensively, by page content), and marks the record
`detail_status: "blocked_query_redirect"` rather than either crashing or --
much worse -- running `detail_parser.py`'s label:value scraper against the
*search form's* HTML, which contains rows like "銷售日區間：" and "保險類別："
that would otherwise silently masquerade as real product data. If you find
a way to legitimately reach a `DetailList.aspx` page (e.g. clicking through
a solved-CAPTCHA search result in your own browser, the way
`ingest_tii_product.py --html-file` was originally designed for), that path
still works and is unaffected by any of this.

```
client.py           fetch a given TII URL, rate-limited, snapshot-to-disk
list_parser.py       ResultQueryAll.aspx page -> {total_records, records: [...]}
detail_parser.py     DetailList.aspx HTML -> SourceProductRecord (metadata)
document_parser.py   DetailList.aspx HTML -> list of TiiDocumentLink (attachments)
source.py            the SourceProductRecord / TiiDocumentLink / DocumentType shapes
```

CLIs (one directory up): `ingest_tii_result_pages.py` (the list index),
`ingest_tii_product.py` (one human-obtained detail page),
`resolve_tii_details.py` (best-effort detail backfill for
`source_product_records` rows that came from the list index and have no
`company_name` yet). All three write to different JSONL/DB locations --
see each script's module docstring.

## Status: `detail_parser.py`'s field map is still unverified against a live page

`detail_parser.py`'s field-label keyword map (公司名稱/商品名稱/保險類別/銷售
日/停售日/核准日期/核准文號/送審方式 -> field name) was written from the
labels visible on TII's own query form, not from a captured detail page --
and per the section above, we now have direct evidence that plain
automated access to a detail page doesn't work at all, so this remains
unverified for the foreseeable future unless reached via
`ingest_tii_product.py --html-file` with a manually-saved page.
`raw_fields` on every record preserves every label:value pair found, mapped
or not, specifically so nothing is lost while this is still unverified.

Fixtures: `fixtures/real_result_page_1.html` is a real, live-captured
`ResultQueryAll.aspx?page=1` snapshot (2026-09-13) -- trust it for
`list_parser.py`'s markup assumptions. `fixtures/synthetic_detail_page.html`
is hand-written, not real -- see `detail_parser.py`'s own docstring caveat
before trusting it for anything beyond exercising the code path.
