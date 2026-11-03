-- Synthetic competition-video data only. No real customer, insurer or contract.
-- Apply once through schema_migrations; preserve existing profiles and policies.
-- Leave product_id/source_document_id empty: no verified terms are attached.
INSERT INTO insurance_profiles (id, owner_name, relation)
VALUES ('cardif-xiao-an-demo', '小安（示範）', '本人')
ON CONFLICT (id) DO NOTHING;

INSERT INTO customer_policies (
    profile_id, product_id, company_name, policy_name, policy_no, role,
    status, annual_premium, effective_date, source_document_id
)
SELECT
    'cardif-xiao-an-demo', '', '安心示範保險（虛構）',
    '小安住院醫療保障（合成測試保單）', 'DEMO-XA-2026-001', '主約',
    '有效', 9600, '2025/01/01', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM customer_policies
    WHERE profile_id = 'cardif-xiao-an-demo' AND policy_no = 'DEMO-XA-2026-001'
);

-- Units match the UI: daily is in NTD; medical is in units of NTD 10,000.
INSERT INTO customer_policy_coverages (policy_id, coverage_key, amount, unit)
SELECT id, 'daily', 2000, '元' FROM customer_policies
WHERE profile_id = 'cardif-xiao-an-demo' AND policy_no = 'DEMO-XA-2026-001'
ON CONFLICT (policy_id, coverage_key) DO NOTHING;

INSERT INTO customer_policy_coverages (policy_id, coverage_key, amount, unit)
SELECT id, 'medical', 20, '萬' FROM customer_policies
WHERE profile_id = 'cardif-xiao-an-demo' AND policy_no = 'DEMO-XA-2026-001'
ON CONFLICT (policy_id, coverage_key) DO NOTHING;
