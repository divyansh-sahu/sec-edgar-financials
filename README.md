# EDGAR Financials API

A FastAPI service that pulls structured financial data (income statement, balance sheet, cash flow) from SEC EDGAR for any US public company — covering 10-K filings back to the early 1990s.

No API key required. All data sourced from SEC's public EDGAR API.

---

## Live API

Deployed on Render: `https://edgar-financials-api.onrender.com`

Interactive docs: `https://edgar-financials-api.onrender.com/docs`

---

## Endpoints

### Search

```
GET /search?name=Apple&limit=10
```

Find companies by name. Returns CIK numbers needed for all other endpoints.

---

### List Filings

```
GET /company/{cik}/filings
```

All 10-K annual filings for a company. Returns `accession_id` used in filing-specific endpoints.

---

### Financials for One Filing

```
GET /filing/{cik}/{accession_id}
```

Structured income statement, balance sheet, and cash flow for a single 10-K filing.

---

### All Filings with Financials

```
GET /company/{cik}/financials
```

All 10-K filings with full structured financials in one call. Uses 2 EDGAR API calls regardless of filing count. Returns newest → oldest.

---

### Download Filing Document

```
GET /filing/{cik}/{accession_id}/download?format=html
GET /filing/{cik}/{accession_id}/download?format=pdf
```

Download the official 10-K document as filed with the SEC.

- `html` (default) — inline XBRL HTML
- `pdf` — PDF if the company included one, falls back to HTML

---

### Filing Viewer URL

```
GET /filing/{cik}/{accession_id}/viewer
```

Returns the official SEC EDGAR filing index URL to open in a browser.

---

### List Filing Documents

```
GET /filing/{cik}/{accession_id}/documents
```

All files inside a filing — filename, type, description, size.

---

### Raw Submissions

```
GET /company/{cik}/submissions
```

Raw EDGAR submissions JSON — company metadata and full filing history.

---

## Example

```bash
# 1. Find Apple's CIK
curl "https://edgar-financials-api.onrender.com/search?name=Apple"
# → CIK: 0000320193

# 2. Get all filings
curl "https://edgar-financials-api.onrender.com/company/0000320193/filings"

# 3. Get financials for a specific year
curl "https://edgar-financials-api.onrender.com/filing/0000320193/0000320193-23-000106"

# 4. Download the 10-K as HTML
curl -O -J "https://edgar-financials-api.onrender.com/filing/0000320193/0000320193-23-000106/download"
```

---

## Running Locally

```bash
git clone https://github.com/divyansh-sahu/sec-edgar-financials.git
cd sec-edgar-financials
pip install -r requirements.txt
uvicorn api:app --reload
```

Open `http://localhost:8000/docs` for the interactive Swagger UI.

---

## Running with Docker

```bash
docker build -t edgar-financials .
docker run -p 8000:8000 edgar-financials
```

---

## Project Structure

```
.
├── api.py               # FastAPI endpoints
├── main.py              # CLI entry point
├── config.py            # Tag config for income/balance/cashflow metrics
├── sources/
│   └── edgar.py         # SEC EDGAR API client
├── models/
│   └── financials.py    # Pydantic models
├── taxonomy/
│   ├── manager.py       # Per-year FASB US-GAAP taxonomy lookup
│   ├── data.json        # Compiled taxonomy (2011–2024, 15MB)
│   └── build_data.py    # Regenerate data.json from Excel files
├── storage/
│   └── local.py         # Local file storage helpers
├── Dockerfile
└── render.yaml
```

---

## Taxonomy

Financial tag names in XBRL changed over the years — for example, Apple's revenue tag was `SalesRevenueNet` before 2018 and `RevenueFromContractWithCustomerExcludingAssessedTax` after. This project uses per-year FASB US-GAAP taxonomy files (2011–2024) to resolve the correct tags for each filing year, so old filings aren't blank.

Taxonomy data is pre-compiled into `taxonomy/data.json` (15MB). To regenerate it after downloading new taxonomy Excel files from [xbrl.us](https://xbrl.us/xbrl-taxonomy/):

```bash
python taxonomy/build_data.py
```

---

## Data Source

All data comes from [SEC EDGAR](https://www.sec.gov/cgi-bin/browse-edgar). This project is not affiliated with the SEC.
