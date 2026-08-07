-- =============================================
-- 02-balance-sheet — schema
-- Table: client_balance_sheet  (one row per client; detail held in JSONB)
-- Sliced from db/01_schema.sql.
-- Depends on 01-client-data (FK client_id → clients.id).
-- =============================================

CREATE TABLE client_balance_sheet (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE UNIQUE,
    assets JSONB DEFAULT '{}',
    liabilities JSONB DEFAULT '{}',
    total_assets NUMERIC(15, 2) DEFAULT 0,
    total_liabilities NUMERIC(15, 2) DEFAULT 0,
    net_worth NUMERIC(15, 2) DEFAULT 0,
    monthly_income NUMERIC(15, 2) DEFAULT 0,
    monthly_expense NUMERIC(15, 2) DEFAULT 0,
    monthly_balance NUMERIC(15, 2) DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_client_balance_sheet_client_id ON client_balance_sheet(client_id);
