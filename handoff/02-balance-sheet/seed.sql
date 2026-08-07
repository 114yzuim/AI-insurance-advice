-- =============================================
-- 02-balance-sheet — seed (5 sample rows, clients 1-5)
-- Apply AFTER 01-client-data seed (needs clients 1-5 to exist).
-- Sliced verbatim from db/02_seed_clients.sql.
--
-- NOTE on JSONB shape: this seed uses the source DB's stored detail keys
-- (assets: cash/investment/property/other/income; liabilities: fixed_debts[]/general).
-- The frontend types.ts / BalanceSheet.constants.ts use a slightly evolved
-- key layout (real_estate/movable/revolving; liabilities.fixed{} keyed map).
-- compute_summary() in balance_sheet_utils.py tolerates both — it sums numeric
-- leaves and reads liabilities.fixed.* / .general.*. If you adopt the frontend
-- layout end-to-end, regenerate these rows via POST /{client_id}/balance-sheet.
-- =============================================

INSERT INTO client_balance_sheet (client_id, assets, liabilities, total_assets, total_liabilities, net_worth, monthly_income, monthly_expense, monthly_balance) VALUES
-- 1. 王小明 (42歲, 工程師, 已婚有子女)
(1,
 '{"cash":{"demand_deposit":350000,"time_deposit":1500000,"foreign_currency_deposit":200000,"cash_on_hand":600000},"investment":{"stocks":1500000,"funds":800000,"etf":500000,"bonds":0,"overseas_funds":300000,"endowment_twd":800000,"endowment_usd":300000,"endowment_aud_reduced":0,"investment_linked":500000,"other_investment":0},"property":{"real_estate":0,"vehicle":450000,"other_movable":0,"presale_remaining":0,"presale_main":0,"presale_renovation":0},"other":{"lent_to_others":0,"receivables":0,"friends_revolving":0,"other_assets":0},"income":{"salary":120000,"side_income":0,"rental_income":0,"gov_subsidy":0,"other_income":0}}',
 '{"fixed_debts":[{"id":"d1-1","name":"房貸","balance":3500000,"periods":240,"interest_rate":2.1,"monthly_payment":35000},{"id":"d1-2","name":"車貸","balance":200000,"periods":24,"interest_rate":3.5,"monthly_payment":8000}],"general":{"living":30000,"education":0,"insurance_premium":0,"rent":0,"medical":5000,"transportation":0,"entertainment":0,"other_expense":2000}}',
 7500000, 80000, 4000000, 120000, 80000, 40000),

-- 2. 李小華 (38歲, 醫師, 已婚)
(2,
 '{"cash":{"demand_deposit":800000,"time_deposit":3000000,"foreign_currency_deposit":500000,"cash_on_hand":1200000},"investment":{"stocks":2500000,"funds":1500000,"etf":1000000,"bonds":0,"overseas_funds":600000,"endowment_twd":1500000,"endowment_usd":800000,"endowment_aud_reduced":0,"investment_linked":1200000,"other_investment":0},"property":{"real_estate":0,"vehicle":600000,"other_movable":0,"presale_remaining":0,"presale_main":0,"presale_renovation":0},"other":{"lent_to_others":0,"receivables":0,"friends_revolving":0,"other_assets":0},"income":{"salary":180000,"side_income":0,"rental_income":0,"gov_subsidy":0,"other_income":0}}',
 '{"fixed_debts":[{"id":"d2-1","name":"房貸","balance":5000000,"periods":300,"interest_rate":2.0,"monthly_payment":50000},{"id":"d2-2","name":"學貸","balance":300000,"periods":60,"interest_rate":1.5,"monthly_payment":15000}],"general":{"living":45000,"education":0,"insurance_premium":0,"rent":0,"medical":8000,"transportation":0,"entertainment":0,"other_expense":2000}}',
 14600000, 120000, 12600000, 180000, 120000, 60000),

-- 3. 陳小傑 (35歲, 軟體工程師, 單身)
(3,
 '{"cash":{"demand_deposit":200000,"time_deposit":800000,"foreign_currency_deposit":100000,"cash_on_hand":400000},"investment":{"stocks":1500000,"funds":600000,"etf":400000,"bonds":0,"overseas_funds":400000,"endowment_twd":0,"endowment_usd":0,"endowment_aud_reduced":0,"investment_linked":800000,"other_investment":0},"property":{"real_estate":0,"vehicle":300000,"other_movable":0,"presale_remaining":0,"presale_main":0,"presale_renovation":0},"other":{"lent_to_others":0,"receivables":0,"friends_revolving":0,"other_assets":0},"income":{"salary":95000,"side_income":0,"rental_income":0,"gov_subsidy":0,"other_income":0}}',
 '{"fixed_debts":[{"id":"d3-1","name":"車貸","balance":250000,"periods":24,"interest_rate":3.0,"monthly_payment":10000}],"general":{"living":35000,"education":0,"insurance_premium":0,"rent":15000,"medical":3000,"transportation":0,"entertainment":0,"other_expense":2000}}',
 5100000, 65000, 4100000, 95000, 65000, 30000),

-- 4. 林小蕎 (29歲, 教師, 已婚有子女)
(4,
 '{"cash":{"demand_deposit":150000,"time_deposit":500000,"foreign_currency_deposit":50000,"cash_on_hand":300000},"investment":{"stocks":400000,"funds":200000,"etf":200000,"bonds":0,"overseas_funds":50000,"endowment_twd":500000,"endowment_usd":0,"endowment_aud_reduced":0,"investment_linked":200000,"other_investment":0},"property":{"real_estate":0,"vehicle":200000,"other_movable":0,"presale_remaining":0,"presale_main":0,"presale_renovation":0},"other":{"lent_to_others":0,"receivables":0,"friends_revolving":0,"other_assets":0},"income":{"salary":65000,"side_income":0,"rental_income":0,"gov_subsidy":0,"other_income":0}}',
 '{"fixed_debts":[{"id":"d4-1","name":"房貸","balance":2000000,"periods":240,"interest_rate":2.1,"monthly_payment":20000},{"id":"d4-2","name":"信貸","balance":150000,"periods":36,"interest_rate":5.0,"monthly_payment":5000},{"id":"d4-3","name":"學貸","balance":100000,"periods":60,"interest_rate":1.5,"monthly_payment":3000}],"general":{"living":18000,"education":0,"insurance_premium":0,"rent":0,"medical":3000,"transportation":0,"entertainment":0,"other_expense":1500}}',
 2700000, 50500, 900000, 65000, 50500, 14500),

-- 5. 黃小成 (52歲, 企業主, 已婚有子女)
(5,
 '{"cash":{"demand_deposit":2000000,"time_deposit":5000000,"foreign_currency_deposit":2000000,"cash_on_hand":3000000},"investment":{"stocks":6000000,"funds":3000000,"etf":3000000,"bonds":0,"overseas_funds":1500000,"endowment_twd":3000000,"endowment_usd":2000000,"endowment_aud_reduced":0,"investment_linked":5000000,"other_investment":0},"property":{"real_estate":5000000,"vehicle":1500000,"other_movable":0,"presale_remaining":0,"presale_main":0,"presale_renovation":0},"other":{"lent_to_others":0,"receivables":0,"friends_revolving":1000000,"other_assets":0},"income":{"salary":320000,"side_income":0,"rental_income":0,"gov_subsidy":0,"other_income":0}}',
 '{"fixed_debts":[{"id":"d5-1","name":"房貸","balance":6000000,"periods":180,"interest_rate":2.0,"monthly_payment":80000},{"id":"d5-2","name":"車貸","balance":500000,"periods":36,"interest_rate":3.0,"monthly_payment":15000},{"id":"d5-3","name":"保單借款","balance":400000,"periods":0,"interest_rate":4.0,"monthly_payment":20000}],"general":{"living":80000,"education":0,"insurance_premium":0,"rent":0,"medical":15000,"transportation":0,"entertainment":0,"other_expense":3000}}',
 41500000, 213000, 33500000, 320000, 213000, 107000);
