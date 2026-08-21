import asyncio
from typing import List
from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel
from services.claims_service import analyze_claim
from services.claim_document_service import save_claim_document
from services.claim_rules_service import estimate_claim
from services.product_service import get_products
from services.pdf_service import fetch_pdf_text

router = APIRouter()

DISCLAIMER = "本服務提供資訊參考，非正式保險建議，請諮詢合格業務員或直接聯繫保險公司確認。"

# In-process PDF text cache (persists for lifetime of backend process)
_pdf_cache: dict[str, str] = {}

PDF_TEXT_LIMIT = 4000   # chars per product, ~first 2-3 pages
PDF_TIMEOUT    = 15     # seconds


class HoldingItem(BaseModel):
    product_id: str = ""
    product_name: str
    company: str = ""
    category: str = ""
    amount: str = ""


class ClaimsRequest(BaseModel):
    scenario: str
    holdings: List[HoldingItem] = []


class ClaimEstimateRequest(BaseModel):
    profile_id: str = "demo-user"
    scenario: str = ""


class CoverageResult(BaseModel):
    type: str
    likely: bool
    note: str


class ClaimsResponse(BaseModel):
    applicable_coverages: List[CoverageResult]
    exclusions_to_check: List[str]
    required_documents: List[str]
    claim_steps: List[str]
    important_notes: str
    disclaimer: str


async def _fetch_policy_text(product_id: str) -> str:
    """Return cached or freshly fetched policy PDF text for a product."""
    if product_id in _pdf_cache:
        return _pdf_cache[product_id]

    products = get_products()
    product = next((p for p in products if p["product_id"] == product_id), None)
    if not product:
        return ""

    urls: list = product.get("download_urls") or []
    if not urls:
        return ""

    try:
        import httpx
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        async with httpx.AsyncClient(timeout=PDF_TIMEOUT, follow_redirects=True, headers=headers) as client:
            response = await client.get(urls[0])
            response.raise_for_status()
            pdf_bytes = response.content

        # Validate it's actually a PDF (not an HTML error page)
        if not pdf_bytes.startswith(b"%PDF"):
            print(f"[claims] PDF fetch got non-PDF response for {product_id} (content starts with: {pdf_bytes[:20]})")
            return ""

        import pdfplumber, tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        try:
            pages = []
            with pdfplumber.open(tmp_path) as pdf:
                for page in pdf.pages[:10]:   # first 10 pages maximum
                    t = page.extract_text()
                    if t:
                        pages.append(t)
                    if sum(len(p) for p in pages) >= PDF_TEXT_LIMIT:
                        break
        finally:
            os.unlink(tmp_path)

        text = "\n".join(pages)[:PDF_TEXT_LIMIT]
        _pdf_cache[product_id] = text
        return text

    except Exception as e:
        print(f"[claims] PDF fetch failed for {product_id}: {e}")
        return ""


@router.post("", response_model=ClaimsResponse)
async def claims_simulate(req: ClaimsRequest):
    if not req.scenario.strip():
        return ClaimsResponse(
            applicable_coverages=[],
            exclusions_to_check=[],
            required_documents=[],
            claim_steps=[],
            important_notes="請描述你的事故或疾病情境。",
            disclaimer=DISCLAIMER,
        )

    # Fetch policy PDFs in parallel for all holdings that have a product_id
    policy_texts: dict[str, str] = {}
    holdings_with_id = [h for h in req.holdings if h.product_id]
    if holdings_with_id:
        texts = await asyncio.gather(
            *[_fetch_policy_text(h.product_id) for h in holdings_with_id],
            return_exceptions=True,
        )
        for h, text in zip(holdings_with_id, texts):
            if isinstance(text, str) and text:
                policy_texts[h.product_id] = text

    holdings_dicts = [h.model_dump() for h in req.holdings]
    result = await analyze_claim(req.scenario, holdings_dicts, policy_texts)

    return ClaimsResponse(
        applicable_coverages=[CoverageResult(**c) for c in result.get("applicable_coverages", [])],
        exclusions_to_check=result.get("exclusions_to_check", []),
        required_documents=result.get("required_documents", []),
        claim_steps=result.get("claim_steps", []),
        important_notes=result.get("important_notes", ""),
        disclaimer=DISCLAIMER,
    )


@router.post("/documents")
async def upload_claim_documents(
    diagnosis: UploadFile | None = File(default=None),
    receipt: UploadFile | None = File(default=None),
    detail: UploadFile | None = File(default=None),
):
    files = {
        "diagnosis": diagnosis,
        "receipt": receipt,
        "detail": detail,
    }
    documents = [
        save_claim_document(key, file)
        for key, file in files.items()
        if file is not None and file.filename
    ]
    return {
        "documents": documents,
        "parsed_count": len([doc for doc in documents if doc["status"] == "parsed"]),
        "needs_ocr_count": len([doc for doc in documents if doc["status"] == "needs_ocr"]),
    }


@router.post("/estimate")
async def estimate_claim_by_profile(req: ClaimEstimateRequest):
    return estimate_claim(profile_id=req.profile_id)
