from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import pdfplumber

CLAIM_UPLOAD_DIR = Path(__file__).resolve().parents[1] / "data" / "claim_documents"

DOCUMENT_LABELS = {
    "diagnosis": "診斷證明",
    "receipt": "醫療收據",
    "detail": "醫療費用明細",
}


def save_claim_document(key: str, file) -> dict:
    CLAIM_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    original_filename = Path(file.filename or f"{key}.pdf").name
    suffix = Path(original_filename).suffix.lower() or ".pdf"
    local_path = CLAIM_UPLOAD_DIR / f"{uuid4().hex}_{key}{suffix}"

    with local_path.open("wb") as output:
        shutil.copyfileobj(file.file, output)

    content_type = getattr(file, "content_type", "") or ""
    result = {
        "key": key,
        "title": DOCUMENT_LABELS.get(key, key),
        "filename": original_filename,
        "local_path": str(local_path),
        "content_type": content_type,
        "file_size": local_path.stat().st_size,
        "status": "stored",
        "chars": 0,
        "preview": "",
        "message": "文件已儲存。",
    }

    if content_type == "application/pdf" or suffix == ".pdf":
        text = extract_pdf_text(local_path)
        result["chars"] = len(text)
        result["preview"] = text[:800]
        if text.strip():
            result["status"] = "parsed"
            result["message"] = "PDF 已抽取文字。"
        else:
            result["status"] = "needs_ocr"
            result["message"] = "PDF 可能是掃描檔，需要 OCR。"
        return result

    if content_type.startswith("image/") or suffix in {".jpg", ".jpeg", ".png"}:
        result["status"] = "needs_ocr"
        result["message"] = "圖片已儲存，等待 OCR 引擎辨識。"
        return result

    result["status"] = "unsupported"
    result["message"] = "目前僅支援 PDF 或圖片。"
    return result


def extract_pdf_text(path: Path, max_pages: int = 5) -> str:
    pages: list[str] = []
    try:
        with pdfplumber.open(path) as pdf:
            for index, page in enumerate(pdf.pages[:max_pages], 1):
                text = (page.extract_text(x_tolerance=1, y_tolerance=3) or "").strip()
                if text:
                    pages.append(f"[第 {index} 頁]\n{text}")
    except Exception:
        return ""
    return "\n\n".join(pages).strip()
