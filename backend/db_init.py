import sqlite3
import pathlib

DB_PATH = pathlib.Path(__file__).parent / "advisor.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    age INTEGER NOT NULL DEFAULT 30,
    gender TEXT,
    family_status TEXT,
    children_count INTEGER DEFAULT 0,
    children_ages TEXT DEFAULT '[]',
    occupation TEXT,
    target_retire_age INTEGER DEFAULT 65,
    life_expectancy INTEGER DEFAULT 85,
    risk_tolerance TEXT,
    planning_goals TEXT DEFAULT '[]',
    selected_modules TEXT DEFAULT '["A","B","C"]',
    is_joint_plan INTEGER DEFAULT 0,
    spouse_name TEXT,
    spouse_age INTEGER,
    spouse_gender TEXT,
    spouse_retire_age INTEGER,
    spouse_life_expectancy INTEGER DEFAULT 85,
    status TEXT DEFAULT 'new',
    is_demo INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS client_financials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER UNIQUE NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    monthly_income REAL DEFAULT 0,
    monthly_expense REAL DEFAULT 0,
    current_assets REAL DEFAULT 0,
    current_liabilities REAL DEFAULT 0,
    monthly_investable REAL DEFAULT 0,
    target_retire_monthly_expense REAL DEFAULT 0,
    existing_insurance_annual REAL DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS client_balance_sheet (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER UNIQUE NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    assets TEXT DEFAULT '{}',
    liabilities TEXT DEFAULT '{}',
    total_assets REAL DEFAULT 0,
    total_liabilities REAL DEFAULT 0,
    net_worth REAL DEFAULT 0,
    monthly_income REAL DEFAULT 0,
    monthly_expense REAL DEFAULT 0,
    monthly_balance REAL DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS client_questionnaires (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER UNIQUE NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    preferred_channels TEXT DEFAULT '[]',
    retire_income_sources TEXT DEFAULT '[]',
    retire_dreams TEXT DEFAULT '[]',
    retire_target_amount REAL DEFAULT 0,
    retire_monthly_living REAL DEFAULT 0,
    interested_topics TEXT DEFAULT '[]',
    monthly_investable_budget REAL DEFAULT 0,
    risk_factors TEXT DEFAULT '[]',
    consent_advisory INTEGER DEFAULT 1,
    has_existing_insurance INTEGER DEFAULT 0,
    existing_policies_notes TEXT DEFAULT '',
    health_status TEXT DEFAULT '良好',
    has_family_disease INTEGER DEFAULT 0,
    existing_medical_coverage TEXT DEFAULT '不清楚',
    existing_ltc_coverage TEXT DEFAULT '不清楚',
    has_existing_life_insurance INTEGER DEFAULT 0,
    has_existing_medical_insurance INTEGER DEFAULT 0,
    has_existing_accident_insurance INTEGER DEFAULT 0,
    has_existing_annuity INTEGER DEFAULT 0,
    has_existing_savings_insurance INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now'))
);
"""


def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()
