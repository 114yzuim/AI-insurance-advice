# Insurance Inventory Data

This folder now contains two layers of product data:

- `crawled_products_with_pdf_dm_links.json`: original crawl payload kept as raw source input.
- `insurance_inventory.db`: generated SQLite inventory database, ignored by git and rebuilt by scripts.

Recommended workflow:

1. Seed companies and import existing products.
   ```bash
   python scripts/import_inventory.py
   ```
2. Audit product and PDF links.
   ```bash
   python scripts/audit_product_links.py --limit 1000 --concurrency 8 --timeout 10
   ```
3. Download local PDF snapshots for usable documents.
   ```bash
   python scripts/download_pdf_snapshots.py --limit 100 --concurrency 4
   ```
4. Parse downloaded PDF snapshots into text chunks.
   ```bash
   python scripts/parse_pdf_snapshots.py --limit 2000
   ```

Useful APIs after parsing:

- `GET /products/inventory-summary`
- `GET /companies`
- `GET /clauses/summary`
- `GET /clauses/search?q=住院&company=新光人壽`

Status meanings:

- `ok`: URL responded and matches expected content.
- `redirected`: URL is reachable but moved, often to a homepage or new canonical URL.
- `blocked`: likely requires a company-specific adapter, headers, TLS handling, or browser flow.
- `browser_required`: URL appears to be official, but the company site blocks plain HTTP clients and needs a browser/TLS-compatible downloader.
- `missing`: clear missing URL such as 404 or no URL.
- `non_pdf`: document URL responded but did not look like a PDF.
- `download_failed`: PDF audit looked usable, but snapshot download failed.
- `parsed`: PDF text was extracted and chunked.
- `needs_browser_download`: document text is waiting for a browser/TLS-compatible PDF download step.
- `scanned_pdf`: PDF opened but text extraction produced too little text.
- `parse_failed`: PDF parsing failed and should be retried or inspected.

Do not delete missing or redirected products automatically. Treat them as historical candidates until a replacement URL, uploaded policy, or company archive confirms their status.
