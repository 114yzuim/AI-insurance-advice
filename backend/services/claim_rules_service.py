from __future__ import annotations

from services.policy_service import DEFAULT_PROFILE_ID, list_policies

CLAIM_RULES = {
    "daily": {"label": "住院日額", "factor": 6, "confidence": "高度符合"},
    "medical": {"label": "實支實付", "factor": 5000, "confidence": "高度符合"},
    "accident": {"label": "意外保障", "factor": 120, "confidence": "高度符合"},
    "critical": {"label": "重大傷病", "factor": 500, "confidence": "需保險公司確認"},
    "cancer": {"label": "癌症保障", "factor": 350, "confidence": "需保險公司確認"},
}


def estimate_claim(profile_id: str = DEFAULT_PROFILE_ID) -> dict:
    portfolio = list_policies(profile_id)
    groups: dict[str, dict] = {}

    for policy in portfolio["policies"]:
        company = policy["company_name"]
        group = groups.setdefault(company, {"company": company, "total": 0, "items": []})
        for coverage_key, amount in policy.get("coverages", {}).items():
            rule = CLAIM_RULES.get(coverage_key)
            if not rule or not amount:
                continue
            item_amount = round(float(amount) * rule["factor"])
            group["items"].append(
                {
                    "name": rule["label"],
                    "amount": item_amount,
                    "confidence": rule["confidence"],
                    "source_policy": policy["policy_name"],
                }
            )
            group["total"] += item_amount

    companies = [group for group in groups.values() if group["total"] > 0]
    estimated_total = sum(company["total"] for company in companies)
    high_confidence_total = sum(
        item["amount"]
        for company in companies
        for item in company["items"]
        if item["confidence"] == "高度符合"
    )

    return {
        "companies": companies,
        "estimated_total": estimated_total,
        "high_confidence_total": high_confidence_total,
        "review_total": estimated_total - high_confidence_total,
        "possible_denied_total": 0,
        "profile_id": profile_id,
        "policy_count": portfolio["summary"]["policyCount"],
    }
