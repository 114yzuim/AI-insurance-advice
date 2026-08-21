# Company-Specific Product Repair Adapters

Generic crawling is not reliable enough for insurance company sites. Use one adapter per company when audit results show blocked APIs, redirected product pages, or repeated guide PDFs.

Priority adapters:

1. `taiwan_life_adapter.py`
   - Current issue: all 183 existing Taiwan Life products are `blocked`.
   - Existing URLs use `https://www.taiwanlife.com/portal-api/...`.
   - Goal: find the required headers/session flow or product page source for stable PDF access.

2. `kgi_life_adapter.py`
   - Current issue: many products are mapped to a repeated `reading-friendly-user-guide__v7.pdf`.
   - Goal: parse product pages and replace guide URLs with actual terms PDFs.

Adapters should not directly overwrite products on first run. They should write a proposed patch JSON report first:

```json
{
  "company": "凱基人壽",
  "items": [
    {
      "product_id": "...",
      "old_pdf_url": "...",
      "proposed_pdf_url": "...",
      "confidence": "high",
      "reason": "Matched product page terms download link"
    }
  ]
}
```

Apply patches only after reviewing the report.
