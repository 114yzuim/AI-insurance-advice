from fastapi import APIRouter, HTTPException, UploadFile, File, Form
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
    try:
        raw_text = await fetch_pdf_text(req.pdf_url)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"無法讀取保單文件，請確認連結是否有效：{e}")
    if not raw_text.strip():
        raise HTTPException(status_code=422, detail="保單文件內容為空，可能不是有效的 PDF。")
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
