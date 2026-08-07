-- =============================================
-- 01-client-data — seed
-- Apply AFTER schema.sql.
-- 1 broker (user id=1) + 8 sample clients + their client_financials.
-- Sliced from db/01_schema.sql (broker) and db/02_seed_clients.sql (clients 1-8,
-- financials 1-8). The live app seeds 50 clients; this is a representative subset.
-- Clients 1-5 also have balance sheets in 02-balance-sheet/seed.sql.
-- =============================================

INSERT INTO users (name, email) VALUES ('Demo Broker', 'demo@advisor.tw');

INSERT INTO clients (user_id, name, phone, age, gender, family_status, children_count, children_ages, occupation, target_retire_age, life_expectancy, risk_tolerance, status) VALUES
(1, '王小明', '0912-001-001', 42, '男', '已婚有子女', 2, '[10, 8]', '工程師', 60, 85, 'moderate', 'new'),
(1, '李小華', '0912-001-002', 38, '女', '已婚', 0, '[]', '醫師', 58, 85, 'conservative', 'new'),
(1, '陳小傑', '0912-001-003', 35, '男', '單身', 0, '[]', '軟體工程師', 60, 85, 'aggressive', 'new'),
(1, '林小蕎', '0912-001-004', 29, '女', '已婚有子女', 1, '[5]', '教師', 62, 85, 'moderate', 'new'),
(1, '黃小成', '0912-001-005', 52, '男', '已婚有子女', 2, '[22, 20]', '企業主', 55, 85, 'moderate', 'new'),
(1, '吳小芸', '0912-001-006', 33, '女', '已婚', 0, '[]', '會計師', 61, 85, 'conservative', 'new'),
(1, '劉小隆', '0912-001-007', 45, '男', '已婚有子女', 2, '[16, 14]', '律師', 59, 85, 'moderate', 'new'),
(1, '張小妤', '0912-001-008', 31, '女', '單身', 0, '[]', '行銷主管', 64, 85, 'aggressive', 'new');

INSERT INTO client_financials (client_id, monthly_income, monthly_expense, current_assets, current_liabilities, monthly_investable, target_retire_monthly_expense, existing_insurance_annual) VALUES
(1, 120000, 90000, 8500000, 3500000, 30000, 80000, 85000),
(2, 180000, 135000, 15200000, 2000000, 45000, 95000, 120000),
(3, 95000, 65000, 5800000, 1000000, 30000, 60000, 45000),
(4, 65000, 52000, 3200000, 1800000, 13000, 45000, 35000),
(5, 320000, 240000, 42000000, 8000000, 80000, 150000, 285000),
(6, 110000, 77000, 9200000, 1200000, 33000, 70000, 55000),
(7, 180000, 126000, 18500000, 5500000, 54000, 100000, 95000),
(8, 95000, 66500, 6800000, 500000, 28500, 55000, 50000);
