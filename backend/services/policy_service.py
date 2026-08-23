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
    "ltc": {"label": "長照保障", "unit": "萬/月"},
}

LEGACY_DEMO_POLICY_NOS = {
    "CT-2020-0188",
    "CT-2020-HS2",
    "FB-2019-6621",
    "FB-2019-CA1",
    "GL-2021-3107",
    "SK-2018-7789",
    "TW-2022-0912",
    "KGI-2023-1120",
}


def ensure_default_profile() -> None:
    with get_inventory_connection() as conn:
        conn.execute(
            """
            INSERT INTO insurance_profiles (id, owner_name, relation, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO NOTHING
            """,
            (DEFAULT_PROFILE_ID, "預設客戶", "本人"),
        )
        conn.execute(
            """
            UPDATE insurance_profiles
            SET owner_name = ?, relation = ?, updated_at = datetime('now')
            WHERE id = ? AND owner_name = ?
            """,
            ("預設客戶", "本人", DEFAULT_PROFILE_ID, "吳芳圳"),
        )
        delete_legacy_demo_policies(conn)


def delete_legacy_demo_policies(conn) -> None:
    placeholders = ", ".join(["?"] * len(LEGACY_DEMO_POLICY_NOS))
    demo_rows = conn.execute(
        f"""
        SELECT id
        FROM customer_policies
        WHERE profile_id = ?
          AND policy_no IN ({placeholders})
        """,
        (DEFAULT_PROFILE_ID, *LEGACY_DEMO_POLICY_NOS),
    ).fetchall()

    if not demo_rows:
        return

    conn.executemany(
        "DELETE FROM customer_policies WHERE id = ?",
        [(row["id"],) for row in demo_rows],
    )


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
            payload.get("company_name", "").strip() or "未知保險公司",
            payload.get("policy_name", "").strip() or "未命名保單",
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
    ensure_default_profile()
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
    ensure_default_profile()
    with get_inventory_connection() as conn:
        profile_rows = conn.execute(
            """
            SELECT p.*
            FROM insurance_profiles p
            ORDER BY
                CASE WHEN p.id = ? THEN 0 ELSE 1 END,
                p.created_at
            """,
            (DEFAULT_PROFILE_ID,),
        ).fetchall()
        profiles: list[dict] = []
        for row in profile_rows:
            profile = dict(row)
            policy_rows = conn.execute(
                "SELECT * FROM customer_policies WHERE profile_id = ? ORDER BY company_name, id",
                (profile["id"],),
            ).fetchall()
            policies = [policy_to_dict(conn, policy_row) for policy_row in policy_rows]
            summary = summarize_policies(policies)
            profile["policy_count"] = summary["policyCount"]
            profile["incomplete_policy_count"] = summary["incomplete"]
            profile["average_completeness"] = summary["averageCompleteness"]
            profiles.append(profile)
        return profiles


def create_profile(payload: dict) -> dict:
    profile_id = payload.get("id") or f"profile-{uuid4().hex[:12]}"
    owner_name = payload.get("owner_name", "").strip() or "保單持有人"
    relation = payload.get("relation", "").strip() or "本人"
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
    policy["completeness"] = evaluate_policy_completeness(policy)
    return policy


def evaluate_policy_completeness(policy: dict) -> dict:
    checks = [
        {
            "key": "company_name",
            "label": "保險公司",
            "ok": has_meaningful_value(policy.get("company_name")) and policy.get("company_name") != "未知保險公司",
        },
        {
            "key": "policy_name",
            "label": "商品 / 保單名稱",
            "ok": has_meaningful_value(policy.get("policy_name")) and "待 OCR" not in str(policy.get("policy_name")),
        },
        {"key": "policy_no", "label": "保單號碼", "ok": has_meaningful_value(policy.get("policy_no"))},
        {"key": "role", "label": "主約 / 附約", "ok": has_meaningful_value(policy.get("role"))},
        {"key": "status", "label": "保單狀態", "ok": has_meaningful_value(policy.get("status")) and policy.get("status") != "待補資料"},
        {"key": "annual_premium", "label": "年繳保費", "ok": float(policy.get("annual_premium") or 0) > 0},
        {"key": "effective_date", "label": "生效日 / 保單期間", "ok": has_meaningful_value(policy.get("effective_date"))},
        {
            "key": "coverages",
            "label": "保障額度",
            "ok": any(float(amount or 0) > 0 for amount in (policy.get("coverages") or {}).values()),
        },
        {
            "key": "terms_source",
            "label": "條款 / 來源商品",
            "ok": has_meaningful_value(policy.get("product_id")) or bool(policy.get("source_document_id")),
        },
    ]
    missing = [{"key": item["key"], "label": item["label"]} for item in checks if not item["ok"]]
    score = round(((len(checks) - len(missing)) / len(checks)) * 100) if checks else 0
    if score >= 90:
        level = "complete"
        label = "可直接健診"
    elif score >= 65:
        level = "partial"
        label = "仍待補強"
    else:
        level = "insufficient"
        label = "資料不足"
    return {
        "score": score,
        "level": level,
        "label": label,
        "missing": missing,
        "missing_count": len(missing),
        "total_checks": len(checks),
    }


def has_meaningful_value(value) -> bool:
    return value is not None and str(value).strip() != ""


def summarize_policies(policies: list[dict]) -> dict:
    coverage = {key: 0.0 for key in COVERAGE_META}
    for policy in policies:
        for key, amount in policy.get("coverages", {}).items():
            if key in coverage:
                coverage[key] += float(amount or 0)
    incomplete = [
        policy
        for policy in policies
        if (policy.get("completeness") or {}).get("missing_count", 0) > 0
    ]
    average_completeness = (
        round(sum((policy.get("completeness") or {}).get("score", 0) for policy in policies) / len(policies))
        if policies
        else 0
    )
    return {
        "policyCount": len(policies),
        "companyCount": len({policy["company_name"] for policy in policies}),
        "premium": sum(float(policy.get("annual_premium") or 0) for policy in policies),
        "incomplete": len(incomplete),
        "averageCompleteness": average_completeness,
        "coverage": coverage,
    }


def get_policy(policy_id: int) -> dict | None:
    ensure_default_profile()
    with get_inventory_connection() as conn:
        row = conn.execute("SELECT * FROM customer_policies WHERE id = ?", (policy_id,)).fetchone()
        return policy_to_dict(conn, row) if row else None


def update_policy(policy_id: int, payload: dict) -> dict | None:
    ensure_default_profile()
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
                payload.get("company_name", "").strip() or "未知保險公司",
                payload.get("policy_name", "").strip() or "未命名保單",
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
    ensure_default_profile()
    with get_inventory_connection() as conn:
        cursor = conn.execute("DELETE FROM customer_policies WHERE id = ?", (policy_id,))
        return cursor.rowcount > 0


def create_policy_from_upload(file, profile_id: str = DEFAULT_PROFILE_ID) -> dict:
    ensure_default_profile()
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
        "company_name": "未知保險公司",
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
        "message": "已建立保單資料，後續可接 OCR 解析保單內容。",
    }
