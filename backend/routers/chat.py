import json
from typing import Optional
from fastapi import APIRouter, Form, File, UploadFile
from pydantic import BaseModel
from services.claude_service import get_advisory_response
from services.rag_service import retrieve_relevant_products, format_context
from services.pdf_service import extract_pdf_from_bytes

router = APIRouter()

DISCLAIMER = "本服務提供資訊參考，非正式保險建議，請諮詢合格業務員。"


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    product_context: str = ""


class ChatResponse(BaseModel):
    reply: str
    disclaimer: str


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    products = retrieve_relevant_products(req.message)
    rag_context = format_context(products)
    sep = "\n\n" if req.product_context and rag_context else ""
    context = req.product_context + sep + rag_context
    reply = await get_advisory_response(req.message, req.history, context)
    return ChatResponse(reply=reply, disclaimer=DISCLAIMER)


@router.post("/with-file", response_model=ChatResponse)
async def chat_with_file(
    message: str = Form(...),
    history: str = Form("[]"),
    file: Optional[UploadFile] = File(default=None),
):
    history_parsed = json.loads(history)

    file_context = ""
    if file:
        content = await file.read()
        raw_text = await extract_pdf_from_bytes(content)
        if raw_text.strip():
            file_context = f"【用戶上傳的保單文件】\n{raw_text[:6000]}\n\n"

    products = retrieve_relevant_products(message)
    rag_context = format_context(products)
    context = file_context + rag_context

    reply = await get_advisory_response(message, history_parsed, context)
    return ChatResponse(reply=reply, disclaimer=DISCLAIMER)
