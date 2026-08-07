import httpx
import pdfplumber
import tempfile
import os


async def extract_pdf_from_bytes(content: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        return _extract_text(tmp_path)
    finally:
        os.unlink(tmp_path)


async def fetch_pdf_text(url: str) -> str:
    # verify=False handles insurers with non-standard SSL certs (e.g. missing SKI)
    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if "html" in content_type.lower():
        raise ValueError(
            "此連結指向網頁而非 PDF 文件，無法自動解析。"
            "請至保險公司官網手動下載 PDF 保單後，使用「上傳 PDF」功能。"
        )

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(response.content)
        tmp_path = tmp.name

    try:
        text = _extract_text(tmp_path)
    finally:
        os.unlink(tmp_path)

    return text


def _extract_text(pdf_path: str) -> str:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                pages.append(page_text)
    return "\n".join(pages)
