EDGAR = {
    "user_agent": "Financial Research Tool contact@example.com",
    "rate_limit_per_second": 10,

    # ── Endpoints ──────────────────────────────────────────────────────────────
    # All URL templates. {cik} is always zero-padded to 10 digits.
    "endpoints": {
        # 1. Ticker → CIK mapping (full list of all public companies)
        "tickers":          "https://www.sec.gov/files/company_tickers.json",

        # 2. Company metadata + recent filing index
        "submissions":      "https://data.sec.gov/submissions/CIK{cik}.json",

        # 3. All XBRL-tagged financials for a company across every filing
        "company_facts":    "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",

        # 4. Single XBRL concept for a company (e.g. just Assets over time)
        "company_concept":  "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{tag}.json",

        # 5. One concept across ALL companies for a given period
        "frames":           "https://data.sec.gov/api/xbrl/frames/{taxonomy}/{tag}/{unit}/{period}.json",

        # 6. Full-text search across EDGAR filings
        "search":           "https://efts.sec.gov/LATEST/search-index",

        # 7. Raw filing document (HTML / inline XBRL)
        "filing_doc":       "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{doc}",

        # 8. Filing index page (lists all documents in one accession)
        "filing_index":     "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type={form}&dateb=&owner=include&count={count}&search_text=",
    },

    # ── XBRL field → fallback tag list ────────────────────────────────────────
    # Each field tries tags in order; first one with data wins.
    # Different companies (and GAAP eras) use different tag names for the same concept.
    "xbrl_map": {

        # ── Income Statement ──────────────────────────────────────────────────
        "revenue": [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
            "SalesRevenueGoodsNet",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            "NetRevenues",
        ],
        "cost_of_revenue": [
            "CostOfRevenue",
            "CostOfGoodsAndServicesSold",
            "CostOfGoodsSold",
            "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization",
        ],
        "gross_profit":                 ["GrossProfit"],
        "research_and_development":     ["ResearchAndDevelopmentExpense"],
        "selling_general_administrative": [
            "SellingGeneralAndAdministrativeExpense",
        ],
        "selling_and_marketing":        ["SellingAndMarketingExpense"],
        "general_and_administrative":   ["GeneralAndAdministrativeExpense"],
        "advertising_expense":          ["AdvertisingExpense", "MarketingExpense"],
        "operating_expenses":           ["OperatingExpenses"],
        "operating_income": [
            "OperatingIncomeLoss",
        ],
        "nonoperating_income":          ["NonoperatingIncomeExpense"],
        "interest_expense":             ["InterestExpense", "InterestAndDebtExpense", "InterestExpenseDebt"],
        "interest_income":              ["InterestIncomeOperating", "InvestmentIncomeInterest"],
        "income_before_tax": [
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        ],
        "income_tax":                   ["IncomeTaxExpenseBenefit"],
        "net_income": [
            "NetIncomeLoss",
            "NetIncomeLossAvailableToCommonStockholdersBasic",
            "ProfitLoss",
        ],
        "eps_basic":                    ["EarningsPerShareBasic"],
        "eps_diluted":                  ["EarningsPerShareDiluted"],
        "dividends_per_share":          ["CommonStockDividendsPerShareCashPaid", "CommonStockDividendsPerShareDeclared"],
        "shares_outstanding":           ["CommonStockSharesOutstanding", "WeightedAverageNumberOfSharesOutstandingBasic"],
        "shares_diluted":               ["WeightedAverageNumberOfDilutedSharesOutstanding"],
        "depreciation_amortization": [
            "DepreciationDepletionAndAmortization",
            "DepreciationAndAmortization",
            "Depreciation",
        ],
        "amortization_of_intangibles":  ["AmortizationOfIntangibleAssets"],
        "stock_based_compensation":     ["AllocatedShareBasedCompensationExpense", "ShareBasedCompensation"],

        # ── Balance Sheet — Current Assets ────────────────────────────────────
        "cash_and_equivalents": [
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
            "Cash",
        ],
        "short_term_investments":       ["ShortTermInvestments", "MarketableSecuritiesCurrent"],
        "accounts_receivable":          ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"],
        "inventory":                    ["InventoryNet", "Inventories"],
        "other_current_assets":         ["OtherAssetsCurrent"],
        "current_assets":               ["AssetsCurrent"],

        # ── Balance Sheet — Non-current Assets ────────────────────────────────
        "property_plant_equipment_net": [
            "PropertyPlantAndEquipmentNet",
            "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization",
        ],
        "operating_lease_rou_asset":    ["OperatingLeaseRightOfUseAsset"],
        "goodwill":                     ["Goodwill"],
        "intangible_assets":            ["IntangibleAssetsNetExcludingGoodwill", "FiniteLivedIntangibleAssetsNet"],
        "marketable_securities_noncurrent": ["MarketableSecuritiesNoncurrent"],
        "deferred_tax_assets":          ["DeferredIncomeTaxAssetsNet", "DeferredTaxAssetsNet"],
        "other_noncurrent_assets":      ["OtherAssetsNoncurrent"],
        "noncurrent_assets":            ["AssetsNoncurrent", "NoncurrentAssets"],
        "total_assets":                 ["Assets"],

        # ── Balance Sheet — Current Liabilities ───────────────────────────────
        "accounts_payable":             ["AccountsPayableCurrent", "AccountsPayable"],
        "accrued_liabilities":          ["EmployeeRelatedLiabilitiesCurrent", "AccruedLiabilitiesCurrent", "OtherAccruedLiabilitiesCurrent"],
        "accrued_income_taxes":         ["AccruedIncomeTaxesCurrent"],
        "deferred_revenue_current":     ["ContractWithCustomerLiabilityCurrent", "DeferredRevenueCurrent"],
        "commercial_paper":             ["CommercialPaper"],
        "long_term_debt_current":       ["LongTermDebtCurrent"],
        "operating_lease_liability_current": ["OperatingLeaseLiabilityCurrent"],
        "other_current_liabilities":    ["OtherLiabilitiesCurrent", "OtherAccruedLiabilitiesCurrent"],
        "current_liabilities":          ["LiabilitiesCurrent"],

        # ── Balance Sheet — Non-current Liabilities ───────────────────────────
        "long_term_debt": [
            "LongTermDebtNoncurrent",
            "LongTermDebt",
            "LongTermDebtAndCapitalLeaseObligations",
        ],
        "operating_lease_liability_noncurrent": ["OperatingLeaseLiabilityNoncurrent"],
        "finance_lease_liability":      ["FinanceLeaseLiabilityNoncurrent", "FinanceLeaseLiability"],
        "deferred_tax_liabilities":     ["DeferredIncomeTaxLiabilitiesNet", "DeferredTaxLiabilitiesNet", "DeferredIncomeTaxLiabilities"],
        "other_noncurrent_liabilities": ["OtherLiabilitiesNoncurrent", "OtherAccruedLiabilitiesNoncurrent"],
        "noncurrent_liabilities":       ["LiabilitiesNoncurrent"],
        "total_liabilities":            ["Liabilities"],
        "total_debt": [
            "DebtLongtermAndShorttermCombinedAmount",
            "LongTermDebtAndCapitalLeaseObligations",
        ],

        # ── Balance Sheet — Equity ────────────────────────────────────────────
        "retained_earnings":            ["RetainedEarningsAccumulatedDeficit"],
        "total_equity": [
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ],
        "total_liabilities_and_equity": ["LiabilitiesAndStockholdersEquity"],

        # ── Cash Flow — Operating ─────────────────────────────────────────────
        "operating_cash_flow":          ["NetCashProvidedByUsedInOperatingActivities"],
        "net_income_cf":                ["NetIncomeLoss", "ProfitLoss"],
        "depreciation_amortization_cf": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization"],
        "stock_based_comp_cf":          ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
        "deferred_income_tax_cf":       ["DeferredIncomeTaxExpenseBenefit"],

        # ── Cash Flow — Investing ─────────────────────────────────────────────
        "investing_cash_flow":          ["NetCashProvidedByUsedInInvestingActivities"],
        "capex": [
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsForCapitalImprovements",
        ],
        "acquisitions":                 ["PaymentsToAcquireBusinessesNetOfCashAcquired", "BusinessAcquisitionCostOfAcquiredEntityPurchasePrice"],
        "purchases_of_investments": [
            "PaymentsToAcquireAvailableForSaleSecurities",
            "PaymentsToAcquireInvestments",
            "PaymentsToAcquireMarketableSecurities",
        ],
        "proceeds_from_investments": [
            "ProceedsFromSaleAndMaturityOfAvailableForSaleSecurities",
            "ProceedsFromSaleAndMaturityOfMarketableSecurities",
            "ProceedsFromMaturitiesPrepaymentsAndCallsOfAvailableForSaleSecurities",
        ],

        # ── Cash Flow — Financing ─────────────────────────────────────────────
        "financing_cash_flow":          ["NetCashProvidedByUsedInFinancingActivities"],
        "stock_repurchases":            ["PaymentsForRepurchaseOfCommonStock"],
        "dividends_paid":               ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
        "debt_proceeds":                ["ProceedsFromIssuanceOfLongTermDebt", "ProceedsFromLongTermLinesOfCredit"],
        "debt_repayments":              ["RepaymentsOfLongTermDebt", "RepaymentsOfOtherLongTermDebt"],
        "stock_issuance_proceeds":      ["ProceedsFromIssuanceOfCommonStock"],
        "tax_withholding_on_equity_awards": ["PaymentsRelatedToTaxWithholdingForShareBasedCompensation"],
        "net_change_in_cash": [
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
            "CashAndCashEquivalentsPeriodIncreaseDecrease",
        ],
    },

    # Which fields belong to which statement
    "income_fields": {
        "revenue", "cost_of_revenue", "gross_profit",
        "research_and_development", "selling_general_administrative",
        "selling_and_marketing", "general_and_administrative",
        "advertising_expense", "operating_expenses",
        "operating_income", "nonoperating_income",
        "interest_expense", "interest_income",
        "income_before_tax", "income_tax", "net_income",
        "eps_basic", "eps_diluted", "dividends_per_share",
        "shares_outstanding", "shares_diluted",
        "depreciation_amortization", "amortization_of_intangibles",
        "stock_based_compensation",
    },
    "balance_fields": {
        "cash_and_equivalents", "short_term_investments", "accounts_receivable",
        "inventory", "other_current_assets", "current_assets",
        "property_plant_equipment_net", "operating_lease_rou_asset",
        "goodwill", "intangible_assets", "marketable_securities_noncurrent",
        "deferred_tax_assets", "other_noncurrent_assets", "noncurrent_assets",
        "total_assets",
        "accounts_payable", "accrued_liabilities", "accrued_income_taxes",
        "deferred_revenue_current", "commercial_paper", "long_term_debt_current",
        "operating_lease_liability_current", "other_current_liabilities", "current_liabilities",
        "long_term_debt", "operating_lease_liability_noncurrent", "finance_lease_liability",
        "deferred_tax_liabilities", "other_noncurrent_liabilities", "noncurrent_liabilities",
        "total_liabilities", "total_debt",
        "retained_earnings", "total_equity", "total_liabilities_and_equity",
    },
    "cashflow_fields": {
        "operating_cash_flow", "net_income_cf",
        "depreciation_amortization_cf", "stock_based_comp_cf", "deferred_income_tax_cf",
        "investing_cash_flow", "capex", "acquisitions",
        "purchases_of_investments", "proceeds_from_investments",
        "financing_cash_flow", "stock_repurchases", "dividends_paid",
        "debt_proceeds", "debt_repayments", "stock_issuance_proceeds",
        "tax_withholding_on_equity_awards", "net_change_in_cash",
    },
}
