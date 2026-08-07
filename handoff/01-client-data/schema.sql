-- =============================================
-- 01-client-data — schema
-- Tables: users, clients, client_financials
-- Sliced from db/01_schema.sql + the is_demo column from db/03_add_is_demo.sql.
-- =============================================

-- 1. Users (Brokers) — single hardcoded user in the source app (id = 1).
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Clients
CREATE TABLE clients (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    age INTEGER,
    gender VARCHAR(10),
    family_status VARCHAR(50),
    children_count INTEGER DEFAULT 0,
    children_ages JSONB,

    -- Joint Planning Details（配偶資訊）
    is_joint_plan BOOLEAN DEFAULT false,
    spouse_name VARCHAR(100),
    spouse_age INTEGER,
    spouse_gender VARCHAR(10),
    spouse_retire_age INTEGER,
    spouse_life_expectancy INTEGER DEFAULT 85,

    occupation VARCHAR(100),
    target_retire_age INTEGER,
    life_expectancy INTEGER DEFAULT 85,
    risk_tolerance VARCHAR(50),
    planning_goals JSONB,
    -- 客戶希望規劃哪些模組
    -- 'A' = 投資（ETF / 股債）, 'B' = 保險（年金 / 壽險）, 'C' = 失能長照
    selected_modules TEXT[] DEFAULT ARRAY['A'],
    -- is_demo: hides a reusable quick-calc client from lists (from db/03_add_is_demo.sql)
    is_demo BOOLEAN NOT NULL DEFAULT false,
    status VARCHAR(20) DEFAULT 'new',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Client Financials (rollup numbers; one row per client)
CREATE TABLE client_financials (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE UNIQUE,
    monthly_income NUMERIC(15, 2) DEFAULT 0,
    monthly_expense NUMERIC(15, 2) DEFAULT 0,
    current_assets NUMERIC(15, 2) DEFAULT 0,
    current_liabilities NUMERIC(15, 2) DEFAULT 0,
    monthly_investable NUMERIC(15, 2) DEFAULT 0,
    target_retire_monthly_expense NUMERIC(15, 2) DEFAULT 0,
    existing_insurance_annual NUMERIC(15, 2) DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_clients_user_id ON clients(user_id);
CREATE INDEX idx_clients_status ON clients(status);
CREATE INDEX idx_clients_is_demo ON clients(is_demo);
CREATE INDEX idx_client_financials_client_id ON client_financials(client_id);
