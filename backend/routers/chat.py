import json
from typing import Optional
from fastapi import APIRouter, Form, File, UploadFile
from pydantic import BaseModel
from services.claude_service import get_advisory_response
from services.clause_service import format_clause_context, search_clauses
from services.rag_service import retrieve_relevant_products, format_context
from services.pdf_rag_service import retrieve_clause_chunks, format_clause_context
from services.pdf_service import extract_pdf_from_bytes
from services.profile_rag_service import extract_profile, retrieve_with_profile

router = APIRouter()

DISCLAIMER = "本服務提供資訊參考，非正式保險建議，請諮詢合格業務員。"

# RAG 模式：
#   "metadata_rag" — 預設，以商品名稱/公司/類別向量搜尋（原系統）
#   "pdf_rag"      — Full PDF RAG，以條款全文段落向量搜尋
#   "no_rag"       — 純 LLM，不注入任何商品資料（Non-RAG Baseline）
RAG_MODES = {"metadata_rag", "pdf_rag", "no_rag"}


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    product_context: str = ""
    mode: str = "metadata_rag"


class ChatResponse(BaseModel):
    reply: str
    disclaimer: str


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    mode = req.mode if req.mode in RAG_MODES else "metadata_rag"

    if mode == "no_rag":
        context = ""
    elif mode == "pdf_rag":
        chunks = retrieve_clause_chunks(req.message)
        context = format_clause_context(chunks)
    else:  # metadata_rag (default) — profile-augmented when profile is available
        profile = await extract_profile(req.history, req.message)
        if profile.get("age") or profile.get("budget_monthly"):
            context = retrieve_with_profile(req.message, profile)
        else:
            products = retrieve_relevant_products(req.message)
            context = format_context(products)

    if req.product_context:
        context = req.product_context + ("\n\n" if context else "") + context

    clause_items = search_clauses(req.message, limit=6)
    clause_context = format_clause_context(clause_items)
    if clause_context:
        context = context + ("\n\n" if context else "") + clause_context

    reply = await get_advisory_response(req.message, req.history, context)
    return ChatResponse(reply=reply, disclaimer=DISCLAIMER)


@router.post("/with-file", response_model=ChatResponse)
async def chat_with_file(
    message: str = Form(...),
    history: str = Form("[]"),
    product_context: str = Form(""),
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
    clause_context = format_clause_context(search_clauses(message, limit=6))
    context = product_context + ("\n\n" if product_context else "") + file_context + rag_context
    if clause_context:
        context += "\n\n" + clause_context

    reply = await get_advisory_response(message, history_parsed, context)
    return ChatResponse(reply=reply, disclaimer=DISCLAIMER)
