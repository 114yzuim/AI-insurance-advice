/* ───────────────────────────────────────────────────────────────
   02-balance-sheet — frontend types
   Sliced verbatim from the live app's shared/types.ts.
   NOTE: BalanceSheet.tsx + BalanceSheet.constants.ts both import these.
   The `Client` interface is also referenced by BalanceSheet.tsx — pull it
   from 01-client-data/frontend/types.ts (or your own Client type).
   ─────────────────────────────────────────────────────────────── */

export interface FixedDebtSlot {
  balance: number;
  monthly_payment: number;
  rate: number;
}

export interface BalanceSheetAssets {
  cash: {
    demand_deposit: number;
    reserve: number;
    time_deposit: number;
    foreign_currency: number;
  };
  investment: {
    stocks_funds: number;
    endowment_twd: number;
    endowment_aud_reduced: number;
    investment_linked_usd: number;
    other_investment: number;
    lent_to_others: number;
    endowment_usd: number;
  };
  movable: { vehicle: number };
  real_estate: { house: number; presale: number; land: number };
  revolving: { friends_revolving: number };
  income: { salary: number; side_income: number; other_income: number };
}

export interface BalanceSheetLiabilities {
  fixed: {
    mortgage: FixedDebtSlot;
    car_loan: FixedDebtSlot;
    startup_loan: FixedDebtSlot;
    business_loan: FixedDebtSlot;
    relief_loan: FixedDebtSlot;
    student_loan: FixedDebtSlot;
    policy_loan: FixedDebtSlot;
    investment_saving: FixedDebtSlot;
    credit_card_full: FixedDebtSlot;
    credit_card_installment: FixedDebtSlot;
    private_loan: FixedDebtSlot;
    private_finance: FixedDebtSlot;
    informal_loan: FixedDebtSlot;
  };
  general: {
    living: number;
    rent: number;
    medical_insurance: number;
    phone: number;
    presale_remaining: number;
    presale_renovation: number;
  };
}
