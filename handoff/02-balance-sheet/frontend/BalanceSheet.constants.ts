import type { BalanceSheetAssets, BalanceSheetLiabilities, FixedDebtSlot } from '../../shared/types';

export const ES: FixedDebtSlot = { balance: 0, monthly_payment: 0, rate: 0 };

export const emptyAssets: BalanceSheetAssets = {
  cash: { demand_deposit: 0, reserve: 0, time_deposit: 0, foreign_currency: 0 },
  investment: {
    stocks_funds: 0,
    endowment_twd: 0,
    endowment_aud_reduced: 0,
    investment_linked_usd: 0,
    other_investment: 0,
    lent_to_others: 0,
    endowment_usd: 0,
  },
  movable: { vehicle: 0 },
  real_estate: { house: 0, presale: 0, land: 0 },
  revolving: { friends_revolving: 0 },
  income: { salary: 0, side_income: 0, other_income: 0 },
};

export const emptyLiabilities: BalanceSheetLiabilities = {
  fixed: {
    mortgage: { ...ES },
    car_loan: { ...ES },
    startup_loan: { ...ES },
    business_loan: { ...ES },
    relief_loan: { ...ES },
    student_loan: { ...ES },
    policy_loan: { ...ES },
    investment_saving: { ...ES },
    credit_card_full: { ...ES },
    credit_card_installment: { ...ES },
    private_loan: { ...ES },
    private_finance: { ...ES },
    informal_loan: { ...ES },
  },
  general: {
    living: 0,
    rent: 0,
    medical_insurance: 0,
    phone: 0,
    presale_remaining: 0,
    presale_renovation: 0,
  },
};

export const ASSET_SECTIONS: { key: string; title: string; fields: [string, string][] }[] = [
  { key: 'cash', title: '現金與存款', fields: [['demand_deposit', '現金/活存'], ['reserve', '預備金'], ['time_deposit', '定存'], ['foreign_currency', '外幣']] },
  {
    key: 'investment',
    title: '儲蓄與投資',
    fields: [
      ['stocks_funds', '股票/基金'],
      ['endowment_twd', '台幣儲蓄險'],
      ['endowment_aud_reduced', '澳幣儲蓄險(減額)'],
      ['investment_linked_usd', '投資型美元保單'],
      ['other_investment', '其他投資'],
      ['lent_to_others', '借他人錢'],
      ['endowment_usd', '美元保單'],
    ],
  },
  { key: 'movable', title: '動產（殘值）', fields: [['vehicle', '汽車']] },
  { key: 'real_estate', title: '不動產（市值）', fields: [['house', '成屋'], ['presale', '預售屋'], ['land', '土地']] },
  { key: 'revolving', title: '週轉金（信任）', fields: [['friends_revolving', '親友可週轉']] },
  {
    key: 'income',
    title: '收入現況（月）',
    fields: [['salary', '實領薪轉收入(月)'], ['side_income', '現金收入/兼職(月)'], ['other_income', '其他現金收入(月)']],
  },
];

export const DEBT_KEYS: [string, string][] = [
  ['mortgage', '房貸'],
  ['car_loan', '車貸'],
  ['startup_loan', '創業貸款'],
  ['business_loan', '企業貸款'],
  ['relief_loan', '紓困貸款'],
  ['student_loan', '學貸'],
  ['policy_loan', '保單借款'],
  ['investment_saving', '儲蓄、投資'],
  ['credit_card_full', '信用卡債—一次付清'],
  ['credit_card_installment', '信用卡債—分期付款'],
  ['private_loan', '私人借貸'],
  ['private_finance', '私人融資'],
  ['informal_loan', '民間融資借款'],
];

export const GENERAL_FIELDS: [string, string][] = [
  ['living', '生活費'],
  ['rent', '房租'],
  ['medical_insurance', '醫療、意外險等'],
  ['phone', '手機費用'],
  ['presale_remaining', '預售屋剩餘費用'],
  ['presale_renovation', '預售屋裝潢款'],
];
