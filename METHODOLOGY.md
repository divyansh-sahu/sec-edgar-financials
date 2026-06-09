# EDGAR Financials — Data Methodology

## Flow

### Step 1 — Search
```
GET /files/company_tickers.json
→ match company name
→ return CIK
```

### Step 2 — List Annual Filings
```
GET /submissions/CIK{cik}.json
→ parallel arrays: accessionNumber, form, reportDate, filingDate, isXBRL
→ filter: form == "10-K" or "10-K/A" only
→ return per filing:
    accession_id  — unique filing ID
    period_end    — what date this filing covers (reportDate)
    filed_date    — when submitted to SEC
    has_xbrl      — whether machine-readable financial data exists (isXBRL flag)
```

Consumer sees `has_xbrl` upfront before requesting financials.

Note: if company has >1000 filings, older ones paginate into separate files
listed under `filings.files` — we fetch those too.

### Step 3 — Get Structured Financials
```
Input: cik, accession_id, period_end, has_xbrl (from Step 2)

0. If has_xbrl == False → return immediately, no data available

1. GET /api/xbrl/companyfacts/CIK{cik}.json
   → 3-4MB JSON with ALL financial data for ALL filings ever

2. PRE-FILTER — extract only this year's raw data
   For every tag in us-gaap:
     keep records where:
       accn == accession_id        (this specific filing)
       form == "10-K" or "10-K/A" (annual report only — defensive)
       end  == period_end          (exact year match)
   → result: { tag_name: value } flat dict for ONLY this year

   Why end == period_end:
   A 10-K includes 2-3 years of comparative data all under the same accn.
   All rows have fp="FY" and fy=filing_year — neither distinguishes the years.
   Only `end` (period end date) uniquely identifies which year's data it is.

   Why NOT use fy or fp:
   `fy` = the filing year, NOT the data year.
   e.g. FY2014 data filed in 2015 10-K has fy=2015. Misleading.
   `fp` = "FY" for all comparative rows in a 10-K. Not useful.

3. TAXONOMY MAPPING — map tag names → field names
   fiscal_year = period_end[:4]
   Load FASB US-GAAP taxonomy for that fiscal_year
   (tag names changed over years — e.g. SalesRevenueNet pre-2018
    vs RevenueFromContractWithCustomer post-2018)

   For each field (revenue, assets, net_income, ...):
     try tags in order from that year's taxonomy
     first tag that exists in pre-filtered dict wins
   → result: { field_name: value }

4. BUILD MODELS
   → IncomeStatement, BalanceSheet, CashFlow Pydantic models
   → Calculate derived fields:
       EBITDA         = operating_income + depreciation
       gross_margin   = gross_profit / revenue
       operating_margin = operating_income / revenue
       net_margin     = net_income / revenue
       FCF            = operating_cash_flow - abs(capex)

   Why abs(capex):
   XBRL `PaymentsToAcquirePropertyPlantAndEquipment` is supposed to be
   positive (absolute outflow) but some companies file it negative.
   abs() handles both conventions.
```

---

## Key Decisions

| Decision | Reason |
|---|---|
| `end == period_end` as primary filter | 10-K has 2-3 years of comparatives under same accn — exact date is only reliable discriminator |
| Pre-filter ALL tags first, then map | Separation of concerns — filtering and field mapping are independent operations |
| Per-year taxonomy | Tag names changed significantly across GAAP versions |
| `abs(capex)` then subtract for FCF | Some companies report outflow tags as negative despite XBRL convention |
| `form == "10-K"` filter | Defensive — accession already guarantees it but explicit is safer for monetary data |
| No `fy` filter | `fy` is the filing year, not the data year — unreliable |
| No `fp` filter | `fp="FY"` for all comparative rows in same 10-K — not useful |
| No fallback on missing data | Wrong number silently is worse than null for monetary data |
| `has_xbrl` check upfront | Avoids fetching 3-4MB company facts for filings with no structured data |

---

## Data Sources

| URL | Used for |
|---|---|
| `https://www.sec.gov/files/company_tickers.json` | Company name → CIK lookup |
| `https://data.sec.gov/submissions/CIK{cik}.json` | Filing history, metadata, has_xbrl flag |
| `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json` | All financial data (main source) |
| `https://www.sec.gov/Archives/edgar/data/{cik}/{accn}/{doc}` | Raw filing documents (HTML/PDF) |

Rate limit: 10 requests/second. User-Agent header required.

---

## Known Limitations

- Pre-XBRL filings (before 2009 for large filers) have no structured data → `has_xbrl: false`
- Companies with non-standard XBRL tags will have null fields — we only map tags in our config
- MLP / complex capital structures (e.g. MLP-to-C-corp conversions) may show EPS inconsistent
  with net income — this is inherent to their filing structure, not a data error
- Taxonomy year derived from `period_end[:4]` — for companies with fiscal year ending
  Jan/Feb, this may be off by one year (minor, tag changes are small year-to-year)
