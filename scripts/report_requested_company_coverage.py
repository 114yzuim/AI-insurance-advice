import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from inventory_db import get_inventory_connection

OFFICIAL_LIFE_20 = [
    "臺銀人壽",
    "台灣人壽",
    "保誠人壽",
    "國泰人壽",
    "凱基人壽",
    "南山人壽",
    "新光人壽",
    "富邦人壽",
    "三商美邦人壽",
    "遠雄人壽",
    "宏泰人壽",
    "安聯人壽",
    "中華郵政",
    "全球人壽",
    "元大人壽",
    "第一金人壽",
    "合作金庫人壽",
    "安達國際人壽",
    "友邦人壽",
    "法國巴黎人壽",
]

EXTRA_REQUESTED_LIFE = [
    "康健人壽",
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
            COUNT(DISTINCT CASE WHEN d.text_status = 'needs_redirect_review' THEN d.id END) AS needs_redirect_review,
            COUNT(DISTINCT ch.id) AS chunks
        FROM insurance_companies c
        LEFT JOIN insurance_products p ON p.company_id = c.id OR p.company_name = c.short_name OR p.company_name = c.name
        LEFT JOIN policy_documents d ON d.product_db_id = p.id
        LEFT JOIN policy_document_chunks ch ON ch.document_id = d.id
        WHERE c.short_name = ?
           OR c.name = ?
           OR c.name LIKE ?
           OR EXISTS (
                SELECT 1 FROM json_each(c.former_names)
                WHERE json_each.value = ?
           )
        GROUP BY c.id
        """,
        (name, name, f"%{name}%", name),
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
            "chunks": 0,
            "official_url": "",
        }
    result = dict(row)
    result["requested_name"] = name
    result["matched_name"] = result.pop("short_name")
    result["master_data"] = True
    return result


def status_for(item: dict) -> str:
    if not item["master_data"]:
        return "缺 master data"
    if item["parsed_documents"] > 0:
        return "已有可用文字 chunks"
    if item["needs_browser_download"] > 0:
        return "已有商品清單，待瀏覽器下載 PDF"
    if item["documents"] > 0:
        return "已有文件，待下載/解析"
    if item["products"] > 0:
        return "已有商品，待補條款文件"
    return "待補官方來源"


def table(items: list[dict]) -> str:
    lines = [
        "| 要求公司 | 對應公司 | 商品 | 文件 | 已下載 | 已解析 | chunks | 狀態 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in items:
        lines.append(
            f"| {item['requested_name']} | {item['matched_name'] or '-'} | "
            f"{item['products']} | {item['documents']} | {item['downloaded_documents']} | "
            f"{item['parsed_documents']} | {item['chunks']} | {status_for(item)} |"
        )
    return "\n".join(lines)


def main() -> None:
    with get_inventory_connection() as conn:
        life = [fetch_company(conn, name) for name in OFFICIAL_LIFE_20]
        extra_life = [fetch_company(conn, name) for name in EXTRA_REQUESTED_LIFE]
        prop = [fetch_company(conn, name) for name in REQUESTED_PROPERTY]

    out = BACKEND / "data" / "REQUESTED_COMPANY_COVERAGE.md"
    covered_life = sum(1 for item in life if item["products"] > 0)
    parsed_life = sum(1 for item in life if item["parsed_documents"] > 0)
    out.write_text(
        "\n".join(
            [
                "# 要求保險公司覆蓋報告",
                "",
                f"壽險公會現行 20 家：{covered_life}/20 家已有商品，{parsed_life}/20 家已有可用文字 chunks。",
                "",
                "## 壽險公司",
                "",
                table(life),
                "",
                "## 業務方額外提過但非現行 20 家口徑",
                "",
                table(extra_life),
                "",
                "## 產險公司",
                "",
                table(prop),
                "",
                "## 備註",
                "",
                "- 壽險主清單依壽險公會會員公司名錄：20 家，其中 18 家本國公司、2 家外商在台分公司。",
                "- 已解析文件代表可進入商品搜尋、條款 RAG、保單健診/理賠比對的底層資料。",
                "- 台灣人壽、元大人壽目前有商品與 PDF URL，但官方檔案下載需要瀏覽器流程或特殊 API。",
                "- 安聯人壽、臺銀人壽仍需獨立 browser/API adapter 或官方匯出資料。",
                "- 產險公司先保留 master data，待壽險補齊後再逐步新增 adapter。",
            ]
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(out),
                "official_life": len(life),
                "life_with_products": covered_life,
                "life_with_parsed_documents": parsed_life,
                "property": len(prop),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
