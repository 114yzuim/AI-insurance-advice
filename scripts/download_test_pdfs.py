"""
下載並測試 12 筆選定保險商品的 PDF 條款可讀性。
執行方式：python scripts/download_test_pdfs.py
結果輸出至 backend/data/pdfs/  及  scripts/pdf_test_report.txt
"""

import os
import sys
import time
import requests
import pdfplumber
from pathlib import Path
from urllib.parse import urlparse

# ── 目錄設定 ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
PDF_DIR = ROOT / "backend" / "data" / "pdfs"
PDF_DIR.mkdir(parents=True, exist_ok=True)
REPORT_PATH = Path(__file__).parent / "pdf_test_report.txt"

# ── 12 筆選定商品 ─────────────────────────────────────────────────────────────
# 每筆只選「條款（CT）」或最新版 PDF，多份時優先選有 CT 字樣的
SELECTED_PRODUCTS = [
    {
        "id": "HM_001",
        "category": "健康醫療",
        "name": "鑫安實在住院醫療終身健康保險",
        "company": "富邦人壽",
        "pdf_url": "https://www.fubon.com/life/cms/23F3A42248C54558A7BC50EE9EA751A7/2025-12/202512291524475320726545.pdf",
    },
    {
        "id": "HM_002",
        "category": "健康醫療",
        "name": "台灣人壽真滿溢一年定期日額型住院手術健康保險附約",
        "company": "台灣人壽",
        "pdf_url": "https://www.taiwanlife.com/portal-api/File/23578",
    },
    {
        "id": "LI_001",
        "category": "壽險保障",
        "name": "新光人壽Go普惠new定期保險",
        "company": "新光人壽",
        # WFA_2_CT.pdf → CT = 條款
        "pdf_url": "https://www.skl.com.tw/sklife_resource/leap_do/ins_download_picture/1735304364095/WFA_2_CT.pdf",
    },
    {
        "id": "LI_002",
        "category": "壽險保障",
        "name": "遠雄人壽美滿美利讚美元利率變動型增額終身壽險",
        "company": "遠雄人壽",
        # HTML 跳轉頁，非直連 PDF，需人工確認
        "pdf_url": "https://www.fglife.com.tw/termsLink.html?UUID=BB1&termsKind=O",
    },
    {
        "id": "AN_001",
        "category": "年金保險",
        "name": "新豪開鑫利率變動型年金保險(甲型)",
        "company": "富邦人壽",
        "pdf_url": "https://www.fubon.com/life/cms/D3A6323B5A72447097CB91D8E0C50DDF/2025-12/202512311452286007397653.pdf",
    },
    {
        "id": "AN_002",
        "category": "年金保險",
        "name": "遠雄人壽金添得利利率變動型年金保險（甲型）",
        "company": "遠雄人壽",
        "pdf_url": "https://www.fglife.com.tw/termsLink.html?UUID=NJE&termsKind=O",
    },
    {
        "id": "AC_001",
        "category": "意外傷害",
        "name": "安康如意終身保險",
        "company": "富邦人壽",
        "pdf_url": "https://www.fubon.com/life/cms/CFF3BC0403144F5AA5B85D2E6D2B3B93/2025-12/202512291329360816263672.pdf",
    },
    {
        "id": "AC_002",
        "category": "意外傷害",
        "name": "台灣人壽意生平安一年定期傷害暨兒童傷害失能保險附約",
        "company": "台灣人壽",
        "pdf_url": "https://www.taiwanlife.com/portal-api/File/23766",
    },
    {
        "id": "IV_001",
        "category": "投資型保險",
        "name": "金富裕變額年金保險",
        "company": "富邦人壽",
        "pdf_url": "https://www.fubon.com/life/cms/910EA18FDC554C42B4B0E7E49DC9B75F/2025-06/202506261003555569171463.pdf",
    },
    {
        "id": "IV_002",
        "category": "投資型保險",
        "name": "新光人壽享加鑫變額年金保險",
        "company": "新光人壽",
        # V1 結尾通常是條款正本
        "pdf_url": "https://www.skl.com.tw/sklife_resource/leap_do/ins_download_picture/1767092635218/VA3003(%E6%96%B0%E5%85%89%E4%BA%BA%E5%A3%BD%E4%BA%AB%E5%8A%A0%E9%91%AB%E8%AE%8A%E9%A1%8D%E5%B9%B4%E9%87%91%E4%BF%9D%E9%9A%AA)-1150101-V1.pdf",
    },
    {
        "id": "EN_001",
        "category": "還本養老",
        "name": "享滿富分紅終身保險",
        "company": "富邦人壽",
        "pdf_url": "https://www.fubon.com/life/cms/C3991152DC664172A7B35C83CF66B70A/2025-12/202512291540094197770538.pdf",
    },
    {
        "id": "EN_002",
        "category": "還本養老",
        "name": "遠雄人壽富貴喜多利利率變動型終身還本保險",
        "company": "遠雄人壽",
        "pdf_url": "https://www.fglife.com.tw/termsLink.html?UUID=WM1&termsKind=O",
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "application/pdf,*/*",
}


def download_pdf(url: str, dest: Path) -> tuple[bool, str]:
    """下載 URL 至 dest，回傳 (success, message)。"""
    if dest.exists() and dest.stat().st_size > 10_000:
        return True, f"已存在（{dest.stat().st_size // 1024} KB）"
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        r = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True, verify=False)
        content_type = r.headers.get("content-type", "")
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        if "html" in content_type and b"%PDF" not in r.content[:1024]:
            return False, f"回應是 HTML 非 PDF（content-type: {content_type}）"
        dest.write_bytes(r.content)
        return True, f"下載成功（{len(r.content) // 1024} KB）"
    except Exception as e:
        return False, f"下載失敗：{e}"


def test_extract(pdf_path: Path) -> tuple[int, int, str]:
    """用 pdfplumber 解析，回傳 (頁數, 總字數, 前200字樣本)。"""
    try:
        pages_text = []
        with pdfplumber.open(pdf_path) as pdf:
            n_pages = len(pdf.pages)
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    pages_text.append(t)
        full_text = "\n".join(pages_text)
        sample = full_text[:200].replace("\n", " ")
        return n_pages, len(full_text), sample
    except Exception as e:
        return 0, 0, f"解析失敗：{e}"


def main():
    lines = ["=" * 70, "PDF 下載 + 解析測試報告", "=" * 70, ""]
    ok_count = 0

    for p in SELECTED_PRODUCTS:
        pid = p["id"]
        name = p["name"]
        company = p["company"]
        category = p["category"]
        url = p["pdf_url"]

        dest = PDF_DIR / f"{pid}.pdf"
        print(f"\n[{pid}] {name[:20]}...")

        # 下載
        dl_ok, dl_msg = download_pdf(url, dest)
        print(f"  下載: {dl_msg}")

        if dl_ok:
            n_pages, n_chars, sample = test_extract(dest)
            status = "[OK]" if n_chars > 500 else "[WARN] 文字過少（可能是掃描版）"
            if n_chars > 500:
                ok_count += 1
            print(f"  解析: {n_pages} 頁，{n_chars} 字  {status}")
        else:
            n_pages, n_chars, sample = 0, 0, "（未下載）"
            status = "[FAIL] 下載失敗"

        lines += [
            f"[{pid}] [{category}] {name}",
            f"  公司    : {company}",
            f"  URL     : {url}",
            f"  下載    : {dl_msg}",
            f"  頁數/字數: {n_pages} 頁 / {n_chars} 字",
            f"  狀態    : {status}",
            f"  樣本    : {sample}",
            "",
        ]
        time.sleep(0.5)  # 避免對伺服器請求過快

    lines += ["=" * 70, f"總結：{ok_count} / {len(SELECTED_PRODUCTS)} 筆可解析", "=" * 70]

    report = "\n".join(lines)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"\n\n{'=' * 70}")
    print(f"總結：{ok_count} / {len(SELECTED_PRODUCTS)} 筆可解析")
    print(f"完整報告已存至：{REPORT_PATH}")


if __name__ == "__main__":
    main()
