from __future__ import annotations

import re
import shutil
from pathlib import Path
from uuid import uuid4

from inventory_db import get_inventory_connection

DEFAULT_PROFILE_ID = "demo-user"
UPLOAD_DIR = Path(__file__).resolve().parents[1] / "data" / "customer_policy_uploads"

COVERAGE_META = {
    "life": {"label": "壽險保障", "unit": "萬"},
    "cancer": {"label": "癌症保障", "unit": "萬"},
    "critical": {"label": "重大傷病", "unit": "萬"},
    "accident": {"label": "意外保障", "unit": "萬"},
    "daily": {"label": "住院日額", "unit": "元"},
    "medical": {"label": "實支實付", "unit": "萬"},
    "ltc": {"label": "長照保障", "unit": "萬元/月"},
}

DEMO_POLICIES = [
    {
        "company_name": "國泰人壽",
        "policy_name": "新守護終身壽險",
        "policy_no": "CT-2020-0188",
        "role": "主約",
        "status": "有效",
        "annual_premium": 42000,
        "effective_date": "2020/08/15",
        "coverages": {"life": 500, "accident": 300},
        "riders": ["新真全意住院醫療", "好骨力傷害醫療"],
    },
    {
        "company_name": "國泰人壽",
        "policy_name": "新真全意住院醫療健康保險附約",
        "policy_no": "CT-2020-HS2",
        "role": "附約",
        "status": "有效",
        "annual_premium": 18500,
        "effective_date": "2020/08/15",
        "coverages": {"daily": 2000, "medical": 20},
        "riders": [],
    },
    {
        "company_name": "富邦人壽",
        "policy_name": "安心定期壽險",
        "policy_no": "FB-2019-6621",
        "role": "主約",
        "status": "有效",
        "annual_premium": 28000,
        "effective_date": "2019/11/02",
        "coverages": {"life": 700, "critical": 100},
        "riders": ["防癌一次給付健康保險附約"],
    },
    {
        "company_name": "富邦人壽",
        "policy_name": "防癌一次給付健康保險附約",
        "policy_no": "FB-2019-CA1",
        "role": "附約",
        "status": "有效",
        "annual_premium": 21500,
        "effective_date": "2019/11/02",
        "coverages": {"cancer": 200},
        "riders": [],
    },
    {
        "company_name": "全球人壽",
        "policy_name": "醫卡照重大傷病健康保險",
        "policy_no": "GL-2021-3107",
        "role": "主約",
        "status": "有效",
        "annual_premium": 23800,
        "effective_date": "2021/04/20",
        "coverages": {"critical": 100, "cancer": 100},
        "riders": [],
    },
    {
        "company_name": "新光人壽",
        "policy_name": "意外傷害保險附約",
        "policy_no": "SK-2018-7789",
        "role": "附約",
        "status": "待補資料",
        "annual_premium": 6200,
        "effective_date": "2018/06/01",
        "coverages": {"accident": 700},
        "riders": [],
    },
    {
        "company_name": "台灣人壽",
        "policy_name": "住院醫療健康保險附約",
        "policy_no": "TW-2022-0912",
        "role": "附約",
        "status": "有效",
        "annual_premium": 16800,
        "effective_date": "2022/09/12",
        "coverages": {"daily": 3000, "medical": 20},
        "riders": [],
    },
    {
        "company_name": "凱基人壽",
        "policy_name": "享安心長期照顧健康保險",
        "policy_no": "KGI-2023-1120",
        "role": "主約",
        "status": "有效",
        "annual_premium": 11200,
        "effective_date": "2023/01/05",
        "coverages": {"ltc": 5},
        "riders": [],
    },
]


def ensure_demo_profile() -> None:
    with get_inventory_connection() as conn:
        conn.execute(
            """
            INSERT INTO insurance_profiles (id, owner_name, relation, updated_at)
            VALUES (?, '吳芳圳', '本人', datetime('now'))
            ON CONFLICT(id) DO NOTHING
            """,
            (DEFAULT_PROFILE_ID,),
        )
        count = conn.execute(
            "SELECT COUNT(*) FROM customer_policies WHERE profile_id = ?",
            (DEFAULT_PROFILE_ID,),
        ).fetchone()[0]
        if count:
            return
        for policy in DEMO_POLICIES:
            create_policy({**policy, "profile_id": DEFAULT_PROFILE_ID}, conn=conn)


def create_policy(payload: dict, conn=None) -> int:
    if conn is not None:
        return _insert_policy(payload, conn)
    with get_inventory_connection() as own_conn:
        return _insert_policy(payload, own_conn)


def _insert_policy(payload: dict, conn) -> int:
    cursor = conn.execute(
        """
        INSERT INTO customer_policies (
            profile_id, product_id, company_name, policy_name, policy_no, role,
            status, annual_premium, effective_date, source_document_id, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            payload.get("profile_id", DEFAULT_PROFILE_ID),
            payload.get("product_id", ""),
            payload["company_name"],
            payload["policy_name"],
            payload.get("policy_no", ""),
            payload.get("role", "主約"),
            payload.get("status", "有效"),
            float(payload.get("annual_premium", 0) or 0),
            payload.get("effective_date", ""),
            payload.get("source_document_id"),
        ),
    )
    policy_id = int(cursor.lastrowid)
    replace_policy_coverages(policy_id, payload.get("coverages", {}), conn)
    replace_policy_riders(policy_id, payload.get("riders", []), conn)
    return policy_id


def replace_policy_coverages(policy_id: int, coverages: dict, conn) -> None:
    conn.execute("DELETE FROM customer_policy_coverages WHERE policy_id = ?", (policy_id,))
    for key, amount in coverages.items():
        meta = COVERAGE_META.get(key, {"unit": ""})
        conn.execute(
            """
            INSERT INTO customer_policy_coverages (policy_id, coverage_key, amount, unit)
            VALUES (?, ?, ?, ?)
            """,
            (policy_id, key, float(amount or 0), meta["unit"]),
        )


def replace_policy_riders(policy_id: int, riders: list[str], conn) -> None:
    conn.execute("DELETE FROM customer_policy_riders WHERE policy_id = ?", (policy_id,))
    for rider in riders:
        if rider.strip():
            conn.execute(
                "INSERT INTO customer_policy_riders (policy_id, rider_name) VALUES (?, ?)",
                (policy_id, rider.strip()),
            )


def list_policies(profile_id: str = DEFAULT_PROFILE_ID) -> dict:
    ensure_demo_profile()
    with get_inventory_connection() as conn:
        profile_row = conn.execute("SELECT * FROM insurance_profiles WHERE id = ?", (profile_id,)).fetchone()
        profile = dict(profile_row) if profile_row else None
        rows = conn.execute(
            "SELECT * FROM customer_policies WHERE profile_id = ? ORDER BY company_name, id",
            (profile_id,),
        ).fetchall()
        policies = [policy_to_dict(conn, row) for row in rows]
    return {"profile": profile, "policies": policies, "summary": summarize_policies(policies)}


def list_profiles() -> list[dict]:
    ensure_demo_profile()
    with get_inventory_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                p.*,
                COUNT(cp.id) AS policy_count
            FROM insurance_profiles p
            LEFT JOIN customer_policies cp ON cp.profile_id = p.id
            GROUP BY p.id
            ORDER BY
                CASE WHEN p.id = ? THEN 0 ELSE 1 END,
                p.created_at
            """,
            (DEFAULT_PROFILE_ID,),
        ).fetchall()
        return [dict(row) for row in rows]


def create_profile(payload: dict) -> dict:
    profile_id = payload.get("id") or f"profile-{uuid4().hex[:12]}"
    owner_name = payload.get("owner_name", "").strip() or "家庭成員"
    relation = payload.get("relation", "").strip() or "家人"
    with get_inventory_connection() as conn:
        conn.execute(
            """
            INSERT INTO insurance_profiles (id, owner_name, relation, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
                owner_name = excluded.owner_name,
                relation = excluded.relation,
                updated_at = datetime('now')
            """,
            (profile_id, owner_name, relation),
        )
        row = conn.execute("SELECT *, 0 AS policy_count FROM insurance_profiles WHERE id = ?", (profile_id,)).fetchone()
        return dict(row)


def policy_to_dict(conn, row) -> dict:
    policy = dict(row)
    policy["id"] = str(policy["id"])
    policy["coverages"] = {
        coverage["coverage_key"]: coverage["amount"]
        for coverage in conn.execute(
            "SELECT coverage_key, amount FROM customer_policy_coverages WHERE policy_id = ?",
            (policy["id"],),
        ).fetchall()
    }
    policy["riders"] = [
        rider["rider_name"]
        for rider in conn.execute(
            "SELECT rider_name FROM customer_policy_riders WHERE policy_id = ? ORDER BY id",
            (policy["id"],),
        ).fetchall()
    ]
    return policy


def summarize_policies(policies: list[dict]) -> dict:
    coverage = {key: 0.0 for key in COVERAGE_META}
    for policy in policies:
        for key, amount in policy.get("coverages", {}).items():
            if key in coverage:
                coverage[key] += float(amount or 0)
    return {
        "policyCount": len(policies),
        "companyCount": len({policy["company_name"] for policy in policies}),
        "premium": sum(float(policy.get("annual_premium") or 0) for policy in policies),
        "incomplete": len([policy for policy in policies if policy.get("status") == "待補資料"]),
        "coverage": coverage,
    }


def get_policy(policy_id: int) -> dict | None:
    ensure_demo_profile()
    with get_inventory_connection() as conn:
        row = conn.execute("SELECT * FROM customer_policies WHERE id = ?", (policy_id,)).fetchone()
        return policy_to_dict(conn, row) if row else None


def update_policy(policy_id: int, payload: dict) -> dict | None:
    ensure_demo_profile()
    with get_inventory_connection() as conn:
        exists = conn.execute("SELECT id FROM customer_policies WHERE id = ?", (policy_id,)).fetchone()
        if not exists:
            return None
        conn.execute(
            """
            UPDATE customer_policies
            SET product_id = ?, company_name = ?, policy_name = ?, policy_no = ?, role = ?,
                status = ?, annual_premium = ?, effective_date = ?, source_document_id = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                payload.get("product_id", ""),
                payload["company_name"],
                payload["policy_name"],
                payload.get("policy_no", ""),
                payload.get("role", "主約"),
                payload.get("status", "有效"),
                float(payload.get("annual_premium", 0) or 0),
                payload.get("effective_date", ""),
                payload.get("source_document_id"),
                policy_id,
            ),
        )
        replace_policy_coverages(policy_id, payload.get("coverages", {}), conn)
        replace_policy_riders(policy_id, payload.get("riders", []), conn)
        row = conn.execute("SELECT * FROM customer_policies WHERE id = ?", (policy_id,)).fetchone()
        return policy_to_dict(conn, row)


def delete_policy(policy_id: int) -> bool:
    ensure_demo_profile()
    with get_inventory_connection() as conn:
        cursor = conn.execute("DELETE FROM customer_policies WHERE id = ?", (policy_id,))
        return cursor.rowcount > 0


def create_policy_from_upload(file, profile_id: str = DEFAULT_PROFILE_ID) -> dict:
    ensure_demo_profile()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    original_filename = Path(file.filename or "policy.pdf").name
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(original_filename).stem).strip("._") or "policy"
    safe_suffix = Path(original_filename).suffix.lower() or ".pdf"
    local_path = UPLOAD_DIR / f"{uuid4().hex}_{safe_stem}{safe_suffix}"

    with local_path.open("wb") as output:
        shutil.copyfileobj(file.file, output)

    file_size = local_path.stat().st_size
    policy_name = f"{Path(original_filename).stem}（待 OCR）"
    payload = {
        "profile_id": profile_id,
        "company_name": "待辨識保險公司",
        "policy_name": policy_name,
        "policy_no": "",
        "role": "主約",
        "status": "待補資料",
        "annual_premium": 0,
        "effective_date": "",
        "coverages": {},
        "riders": [],
    }

    with get_inventory_connection() as conn:
        policy_id = create_policy(payload, conn=conn)
        cursor = conn.execute(
            """
            INSERT INTO customer_policy_uploads (
                profile_id, policy_id, original_filename, local_path,
                content_type, file_size, ocr_status, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'pending', datetime('now'))
            """,
            (
                profile_id,
                policy_id,
                original_filename,
                str(local_path),
                getattr(file, "content_type", "") or "",
                file_size,
            ),
        )
        upload = dict(
            conn.execute(
                "SELECT * FROM customer_policy_uploads WHERE id = ?",
                (int(cursor.lastrowid),),
            ).fetchone()
        )

    return {
        "policy": get_policy(policy_id),
        "upload": upload,
        "ocr_status": "pending",
        "message": "已建立待補資料保單，後續可接 OCR 回填保單欄位。",
    }
