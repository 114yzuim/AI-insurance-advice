-- =============================================
-- 03-questionnaire — seed (2 sample rows, clients 1-2)
-- Apply AFTER 01-client-data seed (needs clients 1-2 to exist).
--
-- NOTE: in the source db/02_seed_clients.sql, questionnaires are seeded for
-- clients 21-50 (the 30 clients whose status = questionnaire_done). The
-- 01-client-data bundle here only seeds clients 1-8, so these two rows are
-- ILLUSTRATIVE MOCKS adapted from the source data shape and re-keyed to
-- clients 1-2, keeping every column the PUT /{client_id} endpoint reads.
-- =============================================

INSERT INTO client_questionnaires (
  client_id, preferred_channels, retire_income_sources, retire_dreams,
  retire_target_amount, retire_monthly_living, interested_topics,
  monthly_investable_budget, risk_factors, consent_advisory,
  has_existing_insurance, existing_policies_notes,
  health_status, has_family_disease, existing_medical_coverage, existing_ltc_coverage,
  has_existing_life_insurance, has_existing_medical_insurance,
  has_existing_accident_insurance, has_existing_annuity, has_existing_savings_insurance
) VALUES
(1,
 '["銀行存款","股票","基金"]', '["政府老人年金","自己規劃","勞工退休金"]', '["環遊世界","含飴弄孫","園藝種花"]',
 45000000, 85000, '["個人儲蓄投資理財","退休理財規劃","遺產規劃"]',
 30000, '["壽命延長","通貨膨脹","投資風險"]', true,
 true, '國泰終身壽險 100萬、南山醫療險',
 '良好', false, '南山實支實付醫療險', NULL,
 true, true, false, false, false),
(2,
 '["銀行存款","股票","基金","外幣存款"]', '["政府老人年金","自己規劃"]', '["環遊世界","學習新知","含飴弄孫"]',
 52000000, 95000, '["個人儲蓄投資理財","退休理財規劃","子女教育基金"]',
 45000, '["壽命延長","生活費用高","通貨膨脹"]', true,
 true, '富邦儲蓄險 年繳12萬、新光實支實付',
 '良好', false, '新光實支實付', NULL,
 false, true, false, false, true);
