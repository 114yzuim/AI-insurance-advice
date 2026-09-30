# scripts/sources/ib_disclosure

IB (保險業公開資訊觀測站, ins-info.ib.gov.tw) is a central, regulator-run
public-disclosure source -- not a company's own site, and not TII's product
registry. This package covers the two pages it takes to go from "one
company" to "that company's products' full detail":

```
company seed (backend/data/ib_companies_seed.json)
        v
query_client.py            GET + one search-form POST, plain ASP.NET, no CAPTCHA
        v
property_parser.py         company product list -> SourceProductRecords (1 per product)
        v
scripts/import_source_records.py       -> source_product_records + document_registry
        v
scripts/resolve_ib_product_details.py  fetches the 5 property5-1-N.aspx pages per product
        v
detail_parser.py / document_parser.py  -> fills in insurance_type/approval fields,
                                           writes document_registry rows
        v
scripts/reconcile_source_records.py    -> product_families / product_versions
```

## Scope and what's verified live (2026-09-13)

- **Company product list** (`Property_Layout.aspx?UID=<uid>`): a completely
  ordinary ASP.NET WebForms page -- GET it, read off
  `__VIEWSTATE`/`__VIEWSTATEGENERATOR`/`__VIEWSTATEENCRYPTED`/
  `__EVENTVALIDATION`, POST them back with a blank product code and keyword
  (the same "list everything" submission a human clicking "查詢" with
  nothing typed would make), get a real product list back. **No CAPTCHA.**
  This is not the same category of thing as TII's `Query.aspx` (CAPTCHA-gated)
  -- submitting a blank search on a page whose own UI invites exactly that is
  not a bypass of anything.
- **Pagination** is a plain GET, `Property_Layout.aspx?Page=N&UID=...` --
  *not* a `__doPostBack`, confirmed simpler than first assumed. Confirmed to
  work when the same client session had already POSTed the search once;
  `query_client.py` always does that first.
- **Detail pages** (`property5-1-{1..5}.aspx?UID=...&proc=<product_code>`)
  are plain GETs, no CAPTCHA, no session dependency observed. Function
  numbers 1-5 map to 基本資訊/條款內容/短期費率表/費用率與退費係數表/理賠申請文件及程序
  -- see `property_parser.py`'s `FUNCTION_OPTIONS` and
  `detail_parser.py`'s module docstring.
- **Every real file download is an ASP.NET LinkButton**
  (`javascript:__doPostBack('ctl00$MainContent$LinkButtonN','')`), never a
  plain `<a href="....pdf">`. There is no static URL to read off the HTML.
  Per this project's "don't fabricate a URL" rule, these are recorded with
  their visible filename and postback target, `url=""` -- see
  `document_parser.py`'s module docstring, and
  `scripts/resolve_ib_product_details.py`'s for how a document_registry row
  still gets written (a synthesized, unambiguous `urn:ib-linkbutton:...` key,
  not a real download link) so the reference isn't lost even though nothing
  here can actually fetch the file.
- **Not every function has data for every product.** Two different "nothing
  here" outcomes were observed on the same function (3, 短期費率表) across
  different products: an explicit "本商品不適用短期費率" table row (ordinary
  data, no special handling needed), and a bounce back to the company's own
  search page (detected via that page's own `txtProductCode` input field,
  reported as `status="redirected_to_search"` rather than parsed as if it
  were real content).

## What this phase does NOT do

- Never touches TII's `Query.aspx` or attempts to solve its CAPTCHA.
- Never drives a browser (no Selenium/Playwright) -- every request here is a
  plain `httpx` GET/POST.
- Never resolves what an IB LinkButton's postback actually returns (a
  redirect to a real file? streamed bytes with no separate URL?) --
  untested, deliberately out of scope; see `document_parser.py`.
- Never clicks through IB's UI beyond the one query-form POST described
  above -- no tab-switching, no other postbacks.

## Licensing / usage note

IB's own footer states (as of 2026-09-13): "歡迎連結使用金融監督管理委員會網站資料。
引用時，請註明資料來源，請確保資料之完整性，不得任意增刪，亦不得作為商業使用。" --
roughly, attribute the source, keep data intact, and don't use it
commercially. Everything in this package is for research / internal
verification use. **Before any production or commercial use, confirm the
actual data-licensing terms with IB / 金融監督管理委員會保險局 directly** --
this note is not a substitute for that.

## Files

```
source.py            SourceProductRecord / IbDocumentLink / DocumentType shapes
query_client.py       GET+POST session against a company's product-list page
property_parser.py    product-list page -> SourceProductRecord per product (+ pagination)
detail_parser.py      property5-1-N.aspx page -> parsed fields/documents for that function
document_parser.py    shared link/LinkButton extraction helpers used by both parsers above
```

CLIs (one directory up): `ingest_ib_property_page.py` (single given URL,
Phase 2.7, no search submitted), `ingest_ib_company_products.py` (Phase 2.8,
full company product list via the search POST + pagination),
`resolve_ib_product_details.py` (Phase 2.9, backfills each product's 5
detail pages into its `source_product_records` row and `document_registry`).

## Fixtures

`fixtures/real_property_layout_03557115.html` -- bare company page, no
search submitted (empty results). `fixtures/
real_property_layout_03557115_query_results.html` -- the same page after the
blank-query POST (real product rows). `fixtures/real_property5_1_1_basic_info.html`,
`real_property5_1_4_fees_and_rebate.html`, `real_property5_1_5_claim_info.html`
-- real detail pages for functions 1/4/5. All are real, live-captured
snapshots (2026-09-13), not hand-written.
