# Company-Specific Product Inventory Adapters

Generic crawling is not reliable enough for insurance company sites. Use one
adapter per company when official product pages expose different HTML, sitemap,
SPA, or PDF-link structures.

## Current Official Adapters

| Adapter | Company | Source shape |
| --- | --- | --- |
| `cathay_life_adapter.py` | 國泰人壽 | Official product pages |
| `nanshan_life_adapter.py` | 南山人壽 | Official product pages |
| `kgi_life_adapter.py` | 凱基人壽 | Suspicious/repaired PDF mapping report |
| `taiwan_life_adapter.py` | 台灣人壽 | Existing official URLs; PDF download still browser-required |
| `transglobe_life_adapter.py` | 全球人壽 | Official product pages |
| `yuanta_life_adapter.py` | 元大人壽 | Official Nuxt API; PDF download still browser-required |
| `first_life_adapter.py` | 第一金人壽 | Official product category pages |
| `hontai_life_adapter.py` | 宏泰人壽 | Official product tables |
| `mli_life_adapter.py` | 三商美邦人壽 | Official product cards |
| `tcb_life_adapter.py` | 合作金庫人壽 | Official sitemap and PDF assets |
| `aia_life_adapter.py` | 友邦人壽 | Official clauses table/download list |
| `chubb_life_adapter.py` | 安達人壽 | Official product prospectus page |
| `prudential_life_adapter.py` | 保誠人壽 | Official e-consultant product page |
| `post_life_adapter.py` | 中華郵政 | Official active products and discontinued terms table |
| `cardif_life_adapter.py` | 法國巴黎人壽 | Official contract terms page |

## Typical Flow

Run a small probe first:

```powershell
python scripts\adapters\aia_life_adapter.py --limit 5 --output backend\data\aia_life_adapter_probe.json
```

Apply the adapter after reviewing the probe:

```powershell
python scripts\adapters\aia_life_adapter.py --apply --output backend\data\aia_life_adapter_report.json
```

Download and parse official PDFs:

```powershell
python scripts\download_pdf_snapshots.py --company "友邦人壽" --limit 120 --concurrency 5 --timeout 45 --report backend\data\aia_pdf_downloads.json
python scripts\parse_pdf_snapshots.py --company "友邦人壽" --limit 120 --max-pages 30 --engine pypdf --report backend\data\aia_pdf_parse.json
```

Refresh coverage reports and deployable seed:

```powershell
python scripts\report_inventory_quality.py --output backend\data\inventory_quality_report.json
python scripts\report_requested_company_coverage.py
python scripts\export_inventory_seed.py
```

## Remaining Gaps

The current official 20-life-insurer coverage report is generated at
`backend/data/REQUESTED_COMPANY_COVERAGE.md`.

The short version:

- 安聯人壽: official product/download pages require browser or security verification.
- 臺銀人壽: official pages currently return a shell/empty content to ordinary HTTP clients.
- 台灣人壽: product inventory exists, but official PDF downloads need a browser-compatible flow.
- 元大人壽: product inventory exists via official API, but PDF downloads need a dedicated downloader.

Do not backfill these from random search-result PDFs unless the source and
product ownership can be verified.
