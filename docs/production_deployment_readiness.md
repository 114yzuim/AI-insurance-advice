# Production Deployment Readiness

This document is Phase C's deliverable: what it takes to run this
project's insurance-crawler/parser pipeline on Railway staging, instead of
only on a Windows workstation. It assumes you've read the pipeline's own
module docstrings (`scripts/sources/ib_disclosure/*.py`,
`scripts/document_parser_service.py`, `scripts/legacy_office_parser.py`,
`scripts/object_storage.py`) -- this is the deployment-shaped summary, not
a restatement of how the crawler itself works.

## 1. Railway suggested architecture

```
┌─────────────────┐     ┌──────────────────────┐     ┌────────────────────┐
│   Web API        │     │  Crawler Worker       │     │  Parser Worker      │
│  (backend/, the   │     │  (Dockerfile.worker)  │     │  (Dockerfile.worker,│
│   existing         │     │  scripts/ingest_*.py  │     │   same image)       │
│   FastAPI app)     │     │  scripts/resolve_*.py │     │  scripts/parse_     │
│                     │     │  scripts/download_*.py│     │   document_         │
│  Always-on service  │     │  Triggered by         │     │   snapshots.py      │
│                     │     │  scheduler/manual run, │     │  scripts/legacy_    │
│                     │     │  NEVER on cold start   │     │   office_parser.py  │
│                     │     │  (see section 5)       │     │  Also scheduler-    │
│                     │     │                        │     │  triggered          │
└─────────┬──────────┘     └──────────┬─────────────┘     └──────────┬──────────┘
          │                            │                              │
          └────────────┬───────────────┴──────────────┬──────────────┘
                        │                                │
                ┌───────▼────────┐              ┌────────▼─────────┐
                │ Railway         │              │ Object Storage    │
                │ Postgres        │              │ (R2/S3-compatible,│
                │                 │              │  Railway Bucket)  │
                │ Structured data │              │ Raw files         │
                │ only -- see §2  │              │ -- see §3         │
                └─────────────────┘              └────────────────────┘
```

Three services sharing one image (`Dockerfile.worker`) and one Postgres:
- **Web API** -- the existing `backend/` FastAPI app, unchanged by this
  phase. Always-on.
- **Crawler Worker** -- runs `scripts/ingest_*.py` / `resolve_*.py` /
  `download_ib_documents.py` / `recover_ib_download_failures.py`.
  Invoked by a Railway scheduled job or a manual `railway run`, never
  auto-started.
- **Parser Worker** -- runs `scripts/parse_document_snapshots.py` /
  `scripts/backfill_document_snapshots_to_object_store.py`. Same image as
  the crawler worker (`Dockerfile.worker`), different command. Also
  scheduler/manual-triggered.

Splitting crawler and parser into two *logical* workers (not necessarily
two Railway services on day one -- one worker service invoked with
different commands is fine to start) matters because they have different
failure modes: a crawler run can hit IB's WAF and needs to back off (see
`scripts/sources/ib_disclosure/failure_classifier.py`); a parser run
spawning LibreOffice processes has a completely different resource/timeout
profile and shouldn't be blocked behind a crawler's rate-limit cooldown.

## 2. What goes in the database (Railway Postgres)

Structured, small, queryable data ONLY:

- Product/商品 structured fields: `insurance_products`,
  `source_product_records`, `product_families`, `product_versions`
- Document **metadata**: `document_registry`, `document_snapshots`
  (`local_path`, `object_store_uri`, `object_store_key`, `checksum`,
  `file_size`, `content_type`, timestamps -- see §4's schema audit)
- `policy_documents` (metadata + `text_status` + `parsed_text` -- see the
  size caveat in §4) and `policy_document_chunks` (chunk text + a future
  vector/embedding pointer, once embeddings are wired in)
- Reconciliation/classification bookkeeping: `reconciliation_findings`,
  `crawl_runs`, `schema_migrations`

## 3. What goes in object storage

Every actual file, ever:

- Downloaded PDF/DOC/XLS documents (`scripts/object_storage.py`'s
  `document_key()` layout: `sources/{source}/documents/{checksum[:2]}/
  {checksum}.{ext}`)
- HTML snapshots of crawled/queried pages (`ib_disclosure_snapshots/`,
  `ib_document_snapshots/` today -- local dev paths; same content-addressed
  convention applies once backfilled)
- Any future parse-artifact JSON too large for a DB row (docstring
  reserves `parse_artifacts/{source}/{document_id}/{parser_name}.json` for
  this, not used yet)

`OBJECT_STORE_BACKEND=file` (default, local dev / small staging) or
`OBJECT_STORE_BACKEND=s3` (R2/S3/Railway Bucket) -- see
`scripts/object_storage.py`'s `object_store_from_env()`. Switching is a
config change, not a code change; see §6's staging checklist for when to
actually do it.

## 4. Why not Windows COM in production

`scripts/legacy_office_parser.py`'s `.doc` COM path
(`_parse_doc_windows_com`) automates a real, locally-installed, licensed
copy of Microsoft Word via `pywin32`. On Railway (Linux containers):

- There is no Word to automate -- `pywin32`/`win32com` don't exist on
  Linux at all, and `backend/requirements.txt` never installs them.
- Even on Windows, COM automation of a desktop app inside a headless
  server process is fragile (crashes on malformed input can hang the
  `Word.Application` process; no sandboxing) -- acceptable for a
  supervised local test of 20 files, not for an unattended worker.
- Licensing: automating MS Word server-side at scale is outside normal
  desktop licensing terms.

`Dockerfile.worker` therefore installs **LibreOffice headless**
(`libreoffice-writer`, `libreoffice-calc`, `fonts-noto-cjk` for correct
Traditional Chinese text extraction) and never installs `pywin32`. In
`scripts/legacy_office_parser.py`'s `parse_doc()`, LibreOffice is tried
first always; `--enable-windows-com` is the explicit, never-default,
Windows-desktop-only fallback used during local development when
LibreOffice isn't installed on the dev machine. It is dead weight in the
production container (`enable_windows_com=True` there would just hit
`_windows_com_available() == False` and fall through to
`parser_unavailable`, since `pywin32` isn't installed).

## 5. Why not crawl 190k records on day one

IB alone lists roughly 190,000 product/document combinations across all
companies (see `scripts/ingest_ib_company_products.py`'s pagination). This
phase's own verified-live findings (see the two previous phases' reports)
already show real, structural failure modes at the ~200-product scale for
a single company:

- **WAF blocking** (`waf_blocked` category,
  `scripts/sources/ib_disclosure/failure_classifier.py`) -- verified live
  that even a conservative per-request delay didn't immediately clear a
  block once triggered. Scaling request volume 1000x before understanding
  IB's actual rate-limit/ban thresholds risks a durable IP-level block
  across the whole project, not just slower crawling.
- **Source data reality** (`source_not_found` -- 47/199 in the previous
  phase's real sample) -- a meaningful fraction of "failures" are IB's own
  missing files, not a crawler bug. At 190k scale, chasing that ratio blind
  means burning enormous request budget on files that were never going to
  exist.
- **Legacy Office backlog** -- `.doc`/`.xls` are ~40% of downloaded
  documents in the 臺灣產物 sample (`documents_downloaded_not_parsed`
  before this phase). Scaling ingestion before the parser side could even
  read these formats would have meant 190k-scale content sitting unusable
  regardless of download success.

The right order is: prove the pipeline (fetch → classify → store → parse →
report) is correct and safe at ~200-product scale (done, this phase and the
two before it), THEN scale crawl volume deliberately, watching WAF/rate-limit
signals the whole way -- not the other way around. `scripts/
recover_ib_download_failures.py`'s `--cooldown-on-waf` circuit breaker and
`--max-per-category` sampling already encode this "small, bounded, honest
about what's still unknown" discipline; scaling ingestion should follow the
same discipline, not abandon it.

## 6. Staging acceptance checklist (run before pointing staging at real
   traffic)

```bash
# 1. Dependencies, LibreOffice, object storage config, migrations, DB hygiene
python scripts/check_deployment_readiness.py

# 2. Bounded, read-only/dry-run pass over the current DB -- see its own
#    docstring for exactly which steps write vs. dry-run
python scripts/run_staging_smoke_test.py --limit 20

# 3. Full test suite
python -m unittest scripts.test_insurance_fetcher scripts.test_source_response_classifier \
    scripts.test_object_storage scripts.test_document_parser_service \
    scripts.test_policy_data_contract scripts.test_legacy_office_parser \
    scripts.test_parse_document_snapshots

# 4. Compile check on everything touched across all three phases
python -m py_compile backend/*.py scripts/*.py scripts/sources/tii/*.py scripts/sources/ib_disclosure/*.py
```

Both `check_deployment_readiness.py` and `run_staging_smoke_test.py` exit
non-zero on failure (blockers), so both are safe to wire into a CI/deploy
gate directly.

Read `check_deployment_readiness.py`'s `blockers` vs `warnings` split
carefully: a missing LibreOffice or a `.doc` backlog are **warnings**, not
blockers, because they're expected on a bare local dev machine and don't
mean the pipeline is broken -- the actual Railway worker image
(`Dockerfile.worker`) installs LibreOffice, so run the same checker *inside
that container* (not just locally) before trusting the "no blockers"
verdict for a real deploy.

## Scope note

Per this phase's own constraints: no CAPTCHA automation, no WAF bypass, no
`.doc`/`.xls`/PDF/HTML bytes stored in the database (verified live via
`check_deployment_readiness.py`'s `no_raw_blobs_in_db` check -- see its
output for what it actually found), no re-crawling IB to backfill object
storage (`scripts/backfill_document_snapshots_to_object_store.py` is
local-file-only), no `yzu_contracts` dependency, and no wholesale import of
any reference repository -- see the two previous phases' reports for the
concept-by-concept "what was borrowed, what wasn't, why" breakdown.
