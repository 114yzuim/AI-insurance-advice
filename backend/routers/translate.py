from fastapi import APIRouter, UploadFile, File, Form
from pydantic import BaseModel
from services.claude_service import translate_policy_text
from services.pdf_service import fetch_pdf_text, extract_pdf_from_bytes

router = APIRouter()

DISCLAIMER = "本服務提供資訊參考，非正式保險建議，請諮詢合格業務員。"


class TranslateByUrlRequest(BaseModel):
    pdf_url: str
    product_name: str = ""


class TranslateResponse(BaseModel):
    summary: str
    disclaimer: str


@router.post("/by-url", response_model=TranslateResponse)
async def translate_by_url(req: TranslateByUrlRequest):
    raw_text = await fetch_pdf_text(req.pdf_url)
    summary = await translate_policy_text(raw_text, req.product_name)
    return TranslateResponse(summary=summary, disclaimer=DISCLAIMER)


@router.post("/by-file", response_model=TranslateResponse)
async def translate_by_file(
    file: UploadFile = File(...),
    product_name: str = Form(""),
):
    content = await file.read()
    raw_text = await extract_pdf_from_bytes(content)
    summary = await translate_policy_text(raw_text, product_name)
    return TranslateResponse(summary=summary, disclaimer=DISCLAIMER)
