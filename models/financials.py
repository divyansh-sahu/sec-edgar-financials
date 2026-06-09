from pydantic import BaseModel
from typing import Optional


class IncomeStatement(BaseModel):
    fiscal_year: int
    period_end: str
    form: str

    # Revenue
    revenue: Optional[float] = None
    cost_of_revenue: Optional[float] = None
    gross_profit: Optional[float] = None

    # Operating expenses
    research_and_development: Optional[float] = None
    selling_general_administrative: Optional[float] = None
    selling_and_marketing: Optional[float] = None
    general_and_administrative: Optional[float] = None
    advertising_expense: Optional[float] = None
    operating_expenses: Optional[float] = None

    # Operating & below
    operating_income: Optional[float] = None
    nonoperating_income: Optional[float] = None
    interest_expense: Optional[float] = None
    interest_income: Optional[float] = None
    income_before_tax: Optional[float] = None
    income_tax: Optional[float] = None
    net_income: Optional[float] = None

    # Per share
    eps_basic: Optional[float] = None
    eps_diluted: Optional[float] = None
    dividends_per_share: Optional[float] = None
    shares_outstanding: Optional[float] = None
    shares_diluted: Optional[float] = None

    # Non-cash / supplemental
    depreciation_amortization: Optional[float] = None
    amortization_of_intangibles: Optional[float] = None
    stock_based_compensation: Optional[float] = None

    # Derived
    ebitda: Optional[float] = None
    gross_margin: Optional[float] = None       # gross_profit / revenue
    operating_margin: Optional[float] = None   # operating_income / revenue
    net_margin: Optional[float] = None         # net_income / revenue


class BalanceSheet(BaseModel):
    fiscal_year: int
    period_end: str
    form: str

    # Current assets
    cash_and_equivalents: Optional[float] = None
    short_term_investments: Optional[float] = None
    accounts_receivable: Optional[float] = None
    inventory: Optional[float] = None
    other_current_assets: Optional[float] = None
    current_assets: Optional[float] = None

    # Non-current assets
    property_plant_equipment_net: Optional[float] = None
    operating_lease_rou_asset: Optional[float] = None
    goodwill: Optional[float] = None
    intangible_assets: Optional[float] = None
    marketable_securities_noncurrent: Optional[float] = None
    deferred_tax_assets: Optional[float] = None
    other_noncurrent_assets: Optional[float] = None
    noncurrent_assets: Optional[float] = None

    # Total assets
    total_assets: Optional[float] = None

    # Current liabilities
    accounts_payable: Optional[float] = None
    accrued_liabilities: Optional[float] = None
    accrued_income_taxes: Optional[float] = None
    deferred_revenue_current: Optional[float] = None
    commercial_paper: Optional[float] = None
    long_term_debt_current: Optional[float] = None
    operating_lease_liability_current: Optional[float] = None
    other_current_liabilities: Optional[float] = None
    current_liabilities: Optional[float] = None

    # Non-current liabilities
    long_term_debt: Optional[float] = None
    operating_lease_liability_noncurrent: Optional[float] = None
    finance_lease_liability: Optional[float] = None
    deferred_tax_liabilities: Optional[float] = None
    other_noncurrent_liabilities: Optional[float] = None
    noncurrent_liabilities: Optional[float] = None

    # Totals
    total_liabilities: Optional[float] = None
    total_debt: Optional[float] = None

    # Equity
    retained_earnings: Optional[float] = None
    total_equity: Optional[float] = None
    total_liabilities_and_equity: Optional[float] = None


class CashFlow(BaseModel):
    fiscal_year: int
    period_end: str
    form: str

    # Operating
    operating_cash_flow: Optional[float] = None
    net_income_cf: Optional[float] = None           # net income as reported in CF
    depreciation_amortization_cf: Optional[float] = None
    stock_based_comp_cf: Optional[float] = None
    deferred_income_tax_cf: Optional[float] = None
    changes_in_working_capital: Optional[float] = None

    # Investing
    investing_cash_flow: Optional[float] = None
    capex: Optional[float] = None
    acquisitions: Optional[float] = None
    purchases_of_investments: Optional[float] = None
    proceeds_from_investments: Optional[float] = None

    # Financing
    financing_cash_flow: Optional[float] = None
    stock_repurchases: Optional[float] = None
    dividends_paid: Optional[float] = None
    debt_proceeds: Optional[float] = None
    debt_repayments: Optional[float] = None
    stock_issuance_proceeds: Optional[float] = None
    tax_withholding_on_equity_awards: Optional[float] = None

    # Derived
    free_cash_flow: Optional[float] = None          # operating_cf + capex
    net_change_in_cash: Optional[float] = None


class CompanyFinancials(BaseModel):
    cik: str
    ticker: str
    name: str
    sic: Optional[str] = None
    sic_description: Optional[str] = None
    income_statements: list[IncomeStatement] = []
    balance_sheets: list[BalanceSheet] = []
    cash_flows: list[CashFlow] = []


class FilingInfo(BaseModel):
    """One entry in a company's filing history."""
    accession_id: str              # e.g. 0000320193-25-000079
    form: str                      # 10-K, 10-K/A
    fiscal_year: Optional[int] = None
    period_end: str                # reporting period end date
    filed_date: str                # date filed with SEC
    primary_document: Optional[str] = None   # e.g. aapl-20250927.htm
    has_xbrl: bool = False         # whether structured financial data is available


class FilingFinancials(BaseModel):
    """Structured financials for one specific filing (one accession ID)."""
    cik: str
    name: str
    accession_id: str
    fiscal_year: Optional[int]
    period_end: str
    filed_date: str
    form: str
    income_statement: Optional[IncomeStatement] = None
    balance_sheet: Optional[BalanceSheet] = None
    cash_flow: Optional[CashFlow] = None
