/* ───────────────────────────────────────────────────────────────
   01-client-data — frontend types
   Sliced verbatim from the live app's shared/types.ts.
   These mirror the FastAPI / PostgreSQL shapes for clients + client_financials.
   ─────────────────────────────────────────────────────────────── */

/** A = 投資 / B = 保險 / C = 失能長照 (internal module codes) */
export type ModuleCode = "A" | "B" | "C";

export interface Client {
  id?: number;
  user_id?: number;
  name: string;
  email?: string | null;
  phone?: string | null;
  age: number;
  gender?: string | null;
  family_status?: string | null;
  children_count?: number;
  children_ages?: number[];
  occupation?: string | null;
  target_retire_age?: number;
  life_expectancy?: number;
  risk_tolerance?: string | null;
  planning_goals?: string[];
  /** Modules this client is interested in. A=投資 / B=保險 / C=長照 */
  selected_modules?: ModuleCode[];
  is_joint_plan?: boolean;
  is_demo?: boolean;
  spouse_name?: string | null;
  spouse_age?: number | null;
  spouse_gender?: string | null;
  spouse_retire_age?: number | null;
  spouse_life_expectancy?: number | null;
  status?: string;
  created_at?: string;
  updated_at?: string;
  // From client_financials join (LEFT JOIN in the list/get endpoints)
  monthly_income?: number;
  monthly_expense?: number;
  current_assets?: number;
  current_liabilities?: number;
  monthly_investable?: number;
  target_retire_monthly_expense?: number;
  existing_insurance_annual?: number;
}
