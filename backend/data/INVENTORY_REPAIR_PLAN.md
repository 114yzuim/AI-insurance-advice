# Inventory Repair Plan

Generated after the first full audit of 780 existing products.

## Current Classification

Products by company:

- 新光人壽: 229 products, 225 `pdf_ok`, 1 `pdf_redirected`, 3 `non_pdf`
- 台灣人壽: 183 products, all currently `blocked`
- 富邦人壽: 162 products, 121 `pdf_ok`, 41 `pdf_redirected`
- 遠雄人壽: 118 products, 118 `pdf_ok`
- 凱基人壽: 88 products, 86 `pdf_ok`, 2 `pdf_redirected`

Overall PDF status:

- `ok`: 550
- `redirected`: 44
- `blocked`: 183
- `non_pdf`: 3

## Important Findings

1. 台灣人壽 is not missing. It is blocked by the current generic HTTP checker/downloader.
   Treat it as requiring a company-specific adapter.

2. 凱基人壽 has a major document mapping issue.
   A repeated URL containing `reading-friendly-user-guide__v7.pdf` appears across 88 products.
   This is likely a guide/reading-friendly document, not the actual policy terms for each product.
   Do not bulk-download these as final terms.

3. 新光人壽 has 3 `non_pdf` URLs:
   - EZ
   - LTC
   - UC
   These URLs likely miss file extensions or need a second-step redirect.

4. 富邦人壽 has many `pdf_redirected` documents.
   These should be checked before marking them historical or broken.

## Recommended Execution Order

1. Safe bulk snapshot:
   Download PDFs that are `pdf_ok` and not suspicious guide URLs.
   Exclude URLs containing `guide`, `reading-friendly`, or `導讀`.

2. Deduplicate:
   Use checksum grouping after download to find accidental repeated PDFs.
   A repeated checksum is not always wrong, but high repetition across unrelated products is suspicious.

3. KGI adapter:
   Re-crawl 凱基 product pages and extract actual terms PDFs.
   Avoid generic guide files.

4. Taiwan Life adapter:
   Inspect `portal-api` access requirements.
   Try browser-like headers, TLS behavior, and endpoint-specific parameters.
   If HTTP remains blocked, use Playwright/browser flow or an official product download page.

5. Redirect repair:
   For 富邦 and 凱基 redirected documents, save both original and final URL.
   If final URL is a PDF, mark usable; if final URL is homepage or generic page, mark `redirected_needs_repair`.

6. Non-PDF repair:
   For 新光 non-PDF URLs, inspect response and product page for the real PDF path.

## Current Repair Status

After document-level audit:

- 凱基人壽: all 88 products have at least one `ok` document, but guide-like documents are marked `needs_review`.
- 富邦人壽: 130 products have `ok` documents; 32 products remain `redirected` and are marked `needs_redirect_review`.
- 新光人壽: 226 products have `ok` documents; 3 `non_pdf` documents remain and are marked `needs_url_repair`.
- 台灣人壽: generic access reaches product pages, but many document URLs return WAF `Request Rejected` or activity HTML; these are marked `needs_company_adapter`.

Do not treat `needs_review`, `needs_redirect_review`, `needs_url_repair`, or `needs_company_adapter` as parsed policy terms.

## Safe Commands

Import inventory:

```bash
python scripts/import_inventory.py
```

Full audit:

```bash
python scripts/audit_product_links.py --limit 1000 --concurrency 8 --timeout 10
```

Quality report:

```bash
python scripts/report_inventory_quality.py --top 100
```

Safe PDF snapshot batch:

```bash
python scripts/download_pdf_snapshots.py --limit 100 --concurrency 4
```

Include suspicious guide-like URLs only when debugging:

```bash
python scripts/download_pdf_snapshots.py --limit 20 --include-suspicious
```
