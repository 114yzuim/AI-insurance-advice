from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path
from uuid import uuid4

import pdfplumber
from PIL import Image

CLAIM_UPLOAD_DIR = Path(__file__).resolve().parents[1] / "data" / "claim_documents"

DOCUMENT_LABELS = {
    "diagnosis": "診斷證明",
    "receipt": "醫療收據",
    "detail": "醫療費用明細",
}


def empty_claim_fields() -> dict:
    return {
        "diagnoses": [],
        "surgeries": [],
        "hospital_stay": {"start_date": "", "end_date": "", "days": None},
        "medical_expense_total": None,
        "self_pay_total": None,
        "self_pay_items": [],
        "matched_signals": [],
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
        "ocr_engine": "",
        "extracted": empty_claim_fields(),
    }

    if content_type == "application/pdf" or suffix == ".pdf":
        text = extract_pdf_text(local_path)
        ocr_text = ""
        if not text.strip():
            ocr_text, ocr_message = extract_pdf_ocr_text(local_path)
            result["ocr_engine"] = "tesseract"
            if ocr_text.strip():
                text = ocr_text
                result["status"] = "ocr_parsed"
                result["message"] = "掃描 PDF 已透過 OCR 辨識文字。"
            else:
                result["status"] = "needs_ocr"
                result["message"] = ocr_message
        else:
            result["status"] = "parsed"
            result["message"] = "PDF 已抽取文字。"

        result["chars"] = len(text)
        result["preview"] = text[:800]
        result["extracted"] = extract_claim_fields(text, key)
        return result

    if content_type.startswith("image/") or suffix in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}:
        text, ocr_message = extract_image_ocr_text(local_path)
        result["ocr_engine"] = "tesseract"
        result["chars"] = len(text)
        result["preview"] = text[:800]
        result["extracted"] = extract_claim_fields(text, key)
        if text.strip():
            result["status"] = "ocr_parsed"
            result["message"] = "圖片已透過 OCR 辨識文字。"
        else:
            result["status"] = "needs_ocr"
            result["message"] = ocr_message
        return result

    result["status"] = "unsupported"
    result["message"] = "目前僅支援 PDF 或圖片。"
    return result


def extract_claim_fields(text: str, key: str = "") -> dict:
    fields = empty_claim_fields()
    if not text.strip():
        return fields

    normalized = normalize_text(text)
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]

    fields["diagnoses"] = extract_diagnoses(lines)
    fields["surgeries"] = extract_surgeries(lines)
    fields["hospital_stay"] = extract_hospital_stay(normalized)

    if key in {"receipt", "detail"}:
        fields["medical_expense_total"] = extract_total_amount(lines)
        fields["self_pay_total"] = extract_self_pay_amount(lines)
        fields["self_pay_items"] = extract_self_pay_items(lines)

    if fields["diagnoses"]:
        fields["matched_signals"].append("已辨識診斷資訊")
    if fields["surgeries"]:
        fields["matched_signals"].append("已辨識手術資訊")
    if fields["hospital_stay"].get("days") or fields["hospital_stay"].get("start_date"):
        fields["matched_signals"].append("已辨識住院期間")
    if fields["medical_expense_total"]:
        fields["matched_signals"].append("已辨識醫療費用")
    if fields["self_pay_items"] or fields["self_pay_total"]:
        fields["matched_signals"].append("已辨識自費項目")

    return fields


def summarize_claim_documents(documents: list[dict]) -> dict:
    summary = empty_claim_fields()
    totals: list[int] = []
    self_pay_totals: list[int] = []

    for doc in documents:
        extracted = doc.get("extracted") or {}
        summary["diagnoses"] = merge_unique(summary["diagnoses"], extracted.get("diagnoses") or [])
        summary["surgeries"] = merge_unique(summary["surgeries"], extracted.get("surgeries") or [])
        summary["self_pay_items"] = merge_unique(summary["self_pay_items"], extracted.get("self_pay_items") or [])
        summary["matched_signals"] = merge_unique(summary["matched_signals"], extracted.get("matched_signals") or [])

        stay = extracted.get("hospital_stay") or {}
        if not summary["hospital_stay"].get("days") and stay.get("days"):
            summary["hospital_stay"]["days"] = stay["days"]
        if not summary["hospital_stay"].get("start_date") and stay.get("start_date"):
            summary["hospital_stay"]["start_date"] = stay["start_date"]
        if not summary["hospital_stay"].get("end_date") and stay.get("end_date"):
            summary["hospital_stay"]["end_date"] = stay["end_date"]

        if extracted.get("medical_expense_total"):
            totals.append(int(extracted["medical_expense_total"]))
        if extracted.get("self_pay_total"):
            self_pay_totals.append(int(extracted["self_pay_total"]))

    summary["medical_expense_total"] = max(totals) if totals else None
    summary["self_pay_total"] = max(self_pay_totals) if self_pay_totals else None
    return summary


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


def extract_pdf_ocr_text(path: Path, max_pages: int = 3) -> tuple[str, str]:
    try:
        import fitz
    except Exception:
        return "", "PDF 是掃描檔，但目前缺少 PyMuPDF，無法轉圖 OCR。"

    try:
        import pytesseract
    except Exception:
        return "", "PDF 是掃描檔，但目前缺少 pytesseract 套件。"

    pages: list[str] = []
    try:
        document = fitz.open(path)
        for page_index in range(min(max_pages, document.page_count)):
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
            text = pytesseract.image_to_string(image, lang=get_ocr_languages())
            if text.strip():
                pages.append(f"[第 {page_index + 1} 頁 OCR]\n{text.strip()}")
    except pytesseract.TesseractNotFoundError:
        return "", "PDF 是掃描檔，但伺服器尚未安裝 Tesseract OCR 引擎。"
    except Exception as exc:
        return "", f"OCR 解析失敗：{exc}"
    finally:
        try:
            document.close()
        except Exception:
            pass

    if not pages:
        return "", "OCR 未辨識到文字，請確認檔案清晰度或改上傳可複製文字的 PDF。"
    return "\n\n".join(pages), "OCR 已完成。"


def extract_image_ocr_text(path: Path) -> tuple[str, str]:
    try:
        import pytesseract
    except Exception:
        return "", "圖片已儲存，但目前缺少 pytesseract 套件。"

    try:
        image = Image.open(path)
        text = pytesseract.image_to_string(image, lang=get_ocr_languages())
    except pytesseract.TesseractNotFoundError:
        return "", "圖片已儲存，但伺服器尚未安裝 Tesseract OCR 引擎。"
    except Exception as exc:
        return "", f"OCR 解析失敗：{exc}"

    if not text.strip():
        return "", "OCR 未辨識到文字，請確認圖片清晰度。"
    return text.strip(), "OCR 已完成。"


def get_ocr_languages() -> str:
    return "chi_tra+eng"


def normalize_text(text: str) -> str:
    return (
        text.replace("\u3000", " ")
        .replace("：", ":")
        .replace("，", ",")
        .replace("－", "-")
        .replace("～", "~")
    )


def merge_unique(existing: list[str], incoming: list[str], limit: int = 8) -> list[str]:
    values = list(existing)
    seen = {value for value in values}
    for raw in incoming:
        value = cleanup_value(raw)
        if value and value not in seen:
            values.append(value)
            seen.add(value)
        if len(values) >= limit:
            break
    return values


def cleanup_value(value: str) -> str:
    value = re.sub(r"\s+", " ", str(value)).strip(" :;,.，。；、")
    return value[:80]


def extract_diagnoses(lines: list[str]) -> list[str]:
    candidates: list[str] = []
    patterns = [
        r"(?:診斷病名|診斷名稱|疾病名稱|診斷|病名)\s*[:：]\s*(.+)",
        r"(?:Diagnosis|Dx)\s*[:：]\s*(.+)",
    ]
    for line in lines:
        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                value = cleanup_value(match.group(1))
                if is_meaningful_medical_text(value):
                    candidates.append(value)
    return merge_unique([], candidates, limit=5)


def extract_surgeries(lines: list[str]) -> list[str]:
    candidates: list[str] = []
    for line in lines:
        if "手術" not in line and "術式" not in line:
            continue
        if re.search(r"無\s*手術|未\s*手術|未施行", line):
            continue
        match = re.search(r"(?:手術名稱|手術項目|手術|術式)\s*[:：]?\s*(.+)", line)
        value = cleanup_value(match.group(1) if match else line)
        if is_meaningful_medical_text(value):
            candidates.append(value)
    return merge_unique([], candidates, limit=5)


def extract_hospital_stay(text: str) -> dict:
    stay = {"start_date": "", "end_date": "", "days": None}
    date_pattern = r"(\d{2,4}[./年-]\d{1,2}[./月-]\d{1,2}日?)"
    range_match = re.search(
        rf"(?:住院期間|住院日期|入院日期|入院).*?{date_pattern}\s*(?:至|到|~|-)\s*{date_pattern}",
        text,
        re.S,
    )
    if range_match:
        stay["start_date"] = cleanup_value(range_match.group(1))
        stay["end_date"] = cleanup_value(range_match.group(2))

    days_patterns = [
        r"住院(?:日數|天數)?\s*[:：]?\s*(\d{1,3})\s*(?:日|天)",
        r"(?:共計|合計)\s*(\d{1,3})\s*(?:日|天)",
        r"住院.*?(\d{1,3})\s*(?:日|天)",
    ]
    for pattern in days_patterns:
        match = re.search(pattern, text)
        if match:
            days = int(match.group(1))
            if 0 < days < 366:
                stay["days"] = days
                break
    if not stay["days"] and stay["start_date"] and stay["end_date"]:
        stay["days"] = calculate_inclusive_days(stay["start_date"], stay["end_date"])
    return stay


def calculate_inclusive_days(start_value: str, end_value: str) -> int | None:
    start_date = parse_tw_date(start_value)
    end_date = parse_tw_date(end_value)
    if not start_date or not end_date or end_date < start_date:
        return None
    days = (end_date - start_date).days + 1
    return days if 0 < days < 366 else None


def parse_tw_date(value: str) -> date | None:
    match = re.search(r"(\d{2,4})[./年-](\d{1,2})[./月-](\d{1,2})", value)
    if not match:
        return None
    year = int(match.group(1))
    if year < 1911:
        year += 1911
    try:
        return date(year, int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def extract_total_amount(lines: list[str]) -> int | None:
    amount_lines = [
        line
        for line in lines
        if re.search(r"合計|總計|總額|醫療費用|本次費用|應收|實收|收據金額", line)
    ]
    return largest_amount(amount_lines or lines)


def extract_self_pay_amount(lines: list[str]) -> int | None:
    amount_lines = [
        line
        for line in lines
        if re.search(r"自費|自付|部分負擔|差額|不給付|特材", line)
    ]
    return largest_amount(amount_lines)


def extract_self_pay_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        if not re.search(r"自費|自付|部分負擔|差額|特材|材料|病房費|藥品", line):
            continue
        amount = largest_amount([line])
        label = cleanup_value(line)
        if amount:
            label = f"{label} ({amount:,} 元)"
        items = merge_unique(items, [label], limit=8)
    return items


def largest_amount(lines: list[str]) -> int | None:
    amounts: list[int] = []
    for line in lines:
        for raw in re.findall(r"(?:NT\$|新臺幣|新台幣|\$)?\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,9})\s*(?:元)?", line):
            amount = int(raw.replace(",", ""))
            if 100 <= amount <= 10_000_000:
                amounts.append(amount)
    return max(amounts) if amounts else None


def is_meaningful_medical_text(value: str) -> bool:
    if not value or len(value) < 2:
        return False
    if re.fullmatch(r"[\d\s./年月日-]+", value):
        return False
    if any(label in value for label in ["醫師", "醫院", "地址", "電話", "身分證"]):
        return False
    return True
