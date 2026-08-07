/* ───────────────────────────────────────────────────────────────
   03-questionnaire — frontend types
   Sliced verbatim from the live app's shared/types.ts.
   NOTE: QuestionnaireForm.tsx also references the `Client` interface —
   pull it from 01-client-data/frontend/types.ts (or your own Client type).
   ─────────────────────────────────────────────────────────────── */

export interface Questionnaire {
  id?: number;
  client_id?: number;
  preferred_channels: string[];
  retire_income_sources: string[];
  retire_dreams: string[];
  retire_target_amount: number;
  retire_monthly_living: number;
  interested_topics: string[];
  monthly_investable_budget: number;
  risk_factors: string[];
  consent_advisory: boolean;
  has_existing_insurance: boolean;
  existing_policies_notes: string;
  health_status: string;
  has_family_disease: boolean;
  existing_medical_coverage: string;
  existing_ltc_coverage: string;
  has_existing_life_insurance?: boolean;
  has_existing_medical_insurance?: boolean;
  has_existing_accident_insurance?: boolean;
  has_existing_annuity?: boolean;
  has_existing_savings_insurance?: boolean;
  created_at?: string;
  updated_at?: string;
}
