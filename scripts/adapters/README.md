# Company-Specific Product Inventory Adapters

Generic crawling is not reliable enough for insurance company sites. Use one
adapter per company when official product pages expose different HTML, sitemap,
SPA, or PDF-link structures.

## Current Official Adapters

| Adapter | Company | Source shape |
| --- | --- | --- |
| `cathay_life_adapter.py` | 國泰人壽 | Official product pages |
| `nanshan_life_adapter.py` | 南山人壽 | Official product pages |
| `kgi_life_adapter.py` | 凱基人壽 | Official product pages and repaired PDF links |
| `taiwan_life_adapter.py` | 台灣人壽 | Existing official URLs; PDF download still browser-required |
| `transglobe_life_adapter.py` | 全球人壽 | Official product pages |
| `yuanta_life_adapter.py` | 元大人壽 | Existing official URLs; PDF download still browser-required |
| `first_life_adapter.py` | 第一金人壽 | Official product category pages |
| `hontai_life_adapter.py` | 宏泰人壽 | Official product tables |
| `mli_life_adapter.py` | 三商美邦人壽 | Official product cards |
| `tcb_life_adapter.py` | 合作金庫人壽 | Official sitemap and PDF assets |
| `aia_life_adapter.py` | 友邦人壽 | Official clauses table/download list |
| `chubb_life_adapter.py` | 安達人壽 | Official product prospectus page |
| `prudential_life_adapter.py` | 保誠人壽 | Official e-consultant product page |

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

Refresh coverage reports:

```powershell
python scripts\report_inventory_quality.py --output backend\data\inventory_quality_report.json
python scripts\report_requested_company_coverage.py --output backend\data\REQUESTED_COMPANY_COVERAGE.md
```

## Remaining Gaps

See `backend/data/INVENTORY_REMAINING_GAPS.md`.

The short version:

- 安聯人壽：official download zone/browser verification and SPA-only product shell.
- 法國巴黎人壽：Liferay page requires content/API parameters; current direct HTML shows template error.
- 臺銀人壽：official PDFs exist, but product-to-PDF mapping is not stable from ordinary HTTP crawl.
- 華南永昌人壽：requires business confirmation on company/source ownership before crawling.

Do not backfill these from random search-result PDFs unless the source and
product ownership can be verified.
