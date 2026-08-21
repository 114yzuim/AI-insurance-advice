import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from inventory_db import get_inventory_connection

REQUESTED_LIFE = [
    "國泰人壽",
    "富邦人壽",
    "南山人壽",
    "凱基人壽",
    "新光人壽",
    "台灣人壽",
    "全球人壽",
    "三商美邦人壽",
    "遠雄人壽",
    "元大人壽",
    "保誠人壽",
    "安達人壽",
    "安聯人壽",
    "友邦人壽",
    "宏泰人壽",
    "康健人壽",
    "臺銀人壽",
    "第一金人壽",
    "合作金庫人壽",
    "華南永昌人壽",
]

REQUESTED_PROPERTY = [
    "富邦產物",
    "國泰世紀產物",
    "明台產物",
    "泰安產物",
    "新安東京海上產物",
    "旺旺友聯產物",
    "華南產物",
    "第一產物",
    "臺灣產物",
    "南山產物",
    "兆豐產物",
    "友聯產物",
    "群益產物",
]


def fetch_company(conn, name: str) -> dict:
    row = conn.execute(
        """
        SELECT
            c.short_name,
            c.type,
            c.former_names,
            c.official_url,
            COUNT(DISTINCT p.id) AS products,
            COUNT(DISTINCT d.id) AS documents,
            COUNT(DISTINCT CASE WHEN d.local_path IS NOT NULL AND d.local_path != '' THEN d.id END) AS downloaded_documents,
            COUNT(DISTINCT CASE WHEN d.text_status = 'parsed' THEN d.id END) AS parsed_documents,
            COUNT(DISTINCT CASE WHEN d.text_status = 'needs_company_adapter' THEN d.id END) AS needs_company_adapter,
            COUNT(DISTINCT CASE WHEN d.text_status = 'needs_browser_download' THEN d.id END) AS needs_browser_download,
            COUNT(DISTINCT CASE WHEN d.text_status = 'needs_redirect_review' THEN d.id END) AS needs_redirect_review
        FROM insurance_companies c
        LEFT JOIN insurance_products p ON p.company_id = c.id OR p.company_name = c.short_name
        LEFT JOIN policy_documents d ON d.product_db_id = p.id
        WHERE c.short_name = ?
           OR c.name = ?
           OR EXISTS (
                SELECT 1 FROM json_each(c.former_names)
                WHERE json_each.value = ?
           )
        GROUP BY c.id
        """,
        (name, name, name),
    ).fetchone()
    if not row:
        return {
            "requested_name": name,
            "matched_name": "",
            "type": "",
            "master_data": False,
            "products": 0,
            "documents": 0,
            "downloaded_documents": 0,
            "parsed_documents": 0,
            "needs_company_adapter": 0,
            "needs_browser_download": 0,
            "needs_redirect_review": 0,
            "official_url": "",
        }
    result = dict(row)
    result["requested_name"] = name
    result["matched_name"] = result.pop("short_name")
    result["master_data"] = True
    return result


def status_for(item: dict) -> str:
    if not item["master_data"]:
        return "需確認公司 master data"
    if item["parsed_documents"] > 0:
        return "已有可用條款 chunks"
    if item["needs_browser_download"] > 0:
        return "已有舊商品/文件，待瀏覽器下載 PDF"
    if item["documents"] > 0:
        return "已有商品/文件，需修連結或 adapter"
    return "需新爬商品與條款"


def table(items: list[dict]) -> str:
    lines = [
        "| 要求公司 | 對應公司 | 商品 | 文件 | 已解析 | 狀態 |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for item in items:
        lines.append(
            f"| {item['requested_name']} | {item['matched_name'] or '-'} | "
            f"{item['products']} | {item['documents']} | {item['parsed_documents']} | {status_for(item)} |"
        )
    return "\n".join(lines)


def main() -> None:
    with get_inventory_connection() as conn:
        life = [fetch_company(conn, name) for name in REQUESTED_LIFE]
        prop = [fetch_company(conn, name) for name in REQUESTED_PROPERTY]

    out = BACKEND / "data" / "REQUESTED_COMPANY_COVERAGE.md"
    out.write_text(
        "\n".join(
            [
                "# 對方要求公司覆蓋率",
                "",
                "這份報表用來區分：公司 master data 是否已建、舊爬蟲資料是否已覆蓋、哪些公司需要新爬蟲。",
                "",
                "## 壽險",
                "",
                table(life),
                "",
                "## 產險",
                "",
                table(prop),
                "",
                "## 結論",
                "",
                "- 舊檔 `crawled_products_with_pdf_dm_links.json` 目前只含 5 家壽險：凱基、台灣、富邦、新光、遠雄。",
                "- 已有可用條款 chunks 的公司，優先可進 Demo RAG。",
                "- 有商品/文件但已解析為 0 的公司，通常需要 adapter 或連結修復。",
                "- 產品資料庫補齊的下一步，是針對尚無商品的壽險公司逐家新增爬蟲 adapter。",
                "- 產險公司目前先保留 master data，商品與條款建議放第二批。",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({"output": str(out), "life": len(life), "property": len(prop)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
