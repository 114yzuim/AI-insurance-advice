-- =============================================
-- 03-questionnaire — schema
-- Table: client_questionnaires (one row per client)
-- Sliced from db/01_schema.sql.
-- Depends on 01-client-data (FK client_id → clients.id).
-- =============================================

CREATE TABLE client_questionnaires (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE UNIQUE,
    preferred_channels JSONB,
    retire_income_sources JSONB,
    retire_dreams JSONB,
    retire_target_amount NUMERIC(15, 2),
    retire_monthly_living NUMERIC(15, 2),
    interested_topics JSONB,
    monthly_investable_budget NUMERIC(15, 2),
    risk_factors JSONB,
    consent_advisory BOOLEAN DEFAULT true,
    has_existing_insurance BOOLEAN DEFAULT false,
    existing_policies_notes TEXT,
    health_status TEXT,
    has_family_disease BOOLEAN,
    existing_medical_coverage TEXT,
    existing_ltc_coverage TEXT,
    -- Q11 結構化既有保單快簽
    has_existing_life_insurance BOOLEAN DEFAULT false,
    has_existing_medical_insurance BOOLEAN DEFAULT false,
    has_existing_accident_insurance BOOLEAN DEFAULT false,
    has_existing_annuity BOOLEAN DEFAULT false,
    has_existing_savings_insurance BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_questionnaires_client_id ON client_questionnaires(client_id);
