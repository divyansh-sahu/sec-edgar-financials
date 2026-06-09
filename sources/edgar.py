import time
import requests
from typing import Optional
from config import EDGAR
from models.financials import (
    CompanyFinancials, IncomeStatement, BalanceSheet, CashFlow,
    FilingInfo, FilingFinancials,
)
from sources.base import BaseSource
from taxonomy.manager import TaxonomyManager, taxonomy_for_year


def _score(name: str, query: str) -> int:
    n, q = name.lower(), query.lower()
    if n == q:                          return 100
    if n.startswith(q):                 return 80
    if all(w in n for w in q.split()): return 60
    if q in n:                          return 40
    return 0


class EdgarAPI(BaseSource):
    """
    SEC EDGAR scraper.

    Method layers
    ─────────────
    _get()                    internal HTTP with rate-limit + auth header
    fetch_*()                 one method per EDGAR endpoint, returns raw JSON/text
    lookup() / search()       resolve identifiers (satisfy BaseSource)
    get_financials()          full pipeline: lookup → fetch → parse → model
    _extract / _pick / _build  private parsing helpers
    """

    def __init__(self):
        self._cfg = EDGAR
        self._endpoints = EDGAR["endpoints"]
        self._xbrl_map = EDGAR["xbrl_map"]
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": EDGAR["user_agent"],
            "Accept-Encoding": "gzip, deflate",
        })
        self._min_interval = 1.0 / EDGAR["rate_limit_per_second"]
        self._last_call = 0.0
        self._tickers_cache: dict | None = None
        self._submissions_cache: dict[str, dict] = {}     # cik → submissions JSON
        self._taxonomy_cache: dict[int, dict[str, list[str]]] = {}  # year → resolved tags

    def _tags_for_year(self, fiscal_year: int) -> dict[str, list[str]]:
        """Return resolved tag lists for the best-matching taxonomy year (cached)."""
        taxonomy = taxonomy_for_year(fiscal_year)
        if taxonomy.year not in self._taxonomy_cache:
            self._taxonomy_cache[taxonomy.year] = {
                field: taxonomy.get_tags(candidates)
                for field, candidates in self._xbrl_map.items()
            }
        return self._taxonomy_cache[taxonomy.year]

    # ──────────────────────────────────────────────────────────────────────────
    # Internal HTTP
    # ──────────────────────────────────────────────────────────────────────────

    def _get(self, url: str, params: dict | None = None) -> dict | str | bytes:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        resp = self._session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        self._last_call = time.monotonic()
        ct = resp.headers.get("Content-Type", "")
        if "json" in ct:
            return resp.json()
        if "pdf" in ct or "octet-stream" in ct:
            return resp.content  # bytes
        return resp.text

    # ──────────────────────────────────────────────────────────────────────────
    # Raw API endpoints  (endpoint 1-7 from config)
    # ──────────────────────────────────────────────────────────────────────────

    def fetch_tickers(self) -> dict:
        """Endpoint 1 — full ticker → CIK mapping for all US public companies."""
        if self._tickers_cache is None:
            self._tickers_cache = self._get(self._endpoints["tickers"])
        return self._tickers_cache

    def fetch_submissions(self, cik: str) -> dict:
        """Endpoint 2 — company metadata + filing history index (cached per CIK)."""
        if cik not in self._submissions_cache:
            url = self._endpoints["submissions"].format(cik=cik)
            self._submissions_cache[cik] = self._get(url)
        return self._submissions_cache[cik]

    def fetch_company_facts(self, cik: str) -> dict:
        """Endpoint 3 — all XBRL-tagged financials across every filing (main data source)."""
        url = self._endpoints["company_facts"].format(cik=cik)
        return self._get(url)

    def fetch_company_concept(self, cik: str, taxonomy: str, tag: str) -> dict:
        """Endpoint 4 — single XBRL concept for one company over time.
           e.g. taxonomy='us-gaap', tag='Assets'
        """
        url = self._endpoints["company_concept"].format(
            cik=cik, taxonomy=taxonomy, tag=tag
        )
        return self._get(url)

    def fetch_frames(self, taxonomy: str, tag: str, unit: str, period: str) -> dict:
        """Endpoint 5 — one concept across ALL companies for a period.
           e.g. taxonomy='us-gaap', tag='Assets', unit='USD', period='CY2023'
        """
        url = self._endpoints["frames"].format(
            taxonomy=taxonomy, tag=tag, unit=unit, period=period
        )
        return self._get(url)

    def fetch_search(
        self,
        query: str,
        form: str = "10-K",
        start: int = 0,
        count: int = 10,
        **kwargs,
    ) -> dict:
        """Endpoint 6 — full-text search across EDGAR filings."""
        params = {"q": f'"{query}"', "forms": form, "from": start, "size": count}
        params.update(kwargs)
        return self._get(self._endpoints["search"], params=params)

    def fetch_filing_document(self, cik: str, accession: str, doc: str) -> str:
        """Endpoint 7 — raw HTML/XBRL of one document inside a filing.
           accession: '0000320193-23-000106' (with or without dashes)
           doc:       '0000320193-23-000106-index.htm' or specific file name
        """
        accession_clean = accession.replace("-", "")
        url = self._endpoints["filing_doc"].format(
            cik=cik.lstrip("0"), accession=accession_clean, doc=doc
        )
        return self._get(url)

    def fetch_filing_index(self, cik: str, accession_id: str) -> dict:
        """
        Parse the EDGAR filing index page for one accession.
        Returns dict with 'primary_doc', 'viewer_url', and 'documents' list.
        Each document entry: sequence, description, document (filename), type, size.
        """
        import re as _re
        accn_dashed  = self._normalise_accn(accession_id)
        accn_clean   = accn_dashed.replace("-", "")  # always 18 chars after normalise
        cik_stripped = cik.lstrip("0")
        url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{cik_stripped}/{accn_clean}/{accn_dashed}-index.htm"
        )
        html = self._get(url)

        # Extract document rows from the filing index HTML table
        base = f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{accn_clean}/"
        documents = []
        for row in _re.finditer(
            r"<tr[^>]*>.*?</tr>", html, _re.DOTALL | _re.IGNORECASE
        ):
            cells = _re.findall(
                r"<td[^>]*>(.*?)</td>", row.group(), _re.DOTALL | _re.IGNORECASE
            )
            if len(cells) < 3:
                continue
            def _strip(s):
                return _re.sub(r"<[^>]+>", "", s).strip()
            seq   = _strip(cells[0])
            desc  = _strip(cells[1]) if len(cells) > 1 else ""
            doc_cell = cells[2] if len(cells) > 2 else ""
            href  = (_re.search(r'href="([^"]+)"', doc_cell, _re.IGNORECASE) or [None, None])[1]
            fname = href.split("/")[-1] if href else _strip(doc_cell)
            dtype = _strip(cells[3]) if len(cells) > 3 else ""
            size  = _strip(cells[4]) if len(cells) > 4 else ""
            if not fname or not seq.isdigit():
                continue
            documents.append({
                "sequence":    seq,
                "description": desc,
                "document":    fname,
                "url":         base + fname,
                "type":        dtype,
                "size":        size,
            })

        # Primary doc: first 10-K type, else first document
        primary_doc = None
        for d in documents:
            if d["type"] in ("10-K", "10-K/A"):
                primary_doc = d["document"]
                break
        if not primary_doc and documents:
            primary_doc = documents[0]["document"]

        return {
            "accession_id": accn_dashed,
            "viewer_url":   url,
            "primary_doc":  primary_doc,
            "documents":    documents,
        }

    def _primary_doc_from_submissions(self, cik: str, accession_id: str) -> str | None:
        """Look up primaryDocument for an accession directly from submissions JSON (fast, no extra call if cached)."""
        accn_dashed = self._normalise_accn(accession_id)
        sub = self.fetch_submissions(cik)
        filing_data = sub.get("filings", {})
        blocks = [filing_data.get("recent", {})]
        for page in filing_data.get("files", []):
            blocks.append(self._get(f"https://data.sec.gov/submissions/{page['name']}"))
        for block in blocks:
            accns = block.get("accessionNumber", [])
            pdocs = block.get("primaryDocument", [])
            for accn, pdoc in zip(accns, pdocs):
                if accn == accn_dashed:
                    return pdoc or None
        return None

    def download_primary_document(self, cik: str, accession_id: str) -> tuple[str | bytes, str]:
        """
        Fetch the primary filing document.
        Uses the primaryDocument field from submissions (fast).
        Returns (content, filename).
        """
        primary_doc = self._primary_doc_from_submissions(cik, accession_id)
        if not primary_doc:
            raise ValueError(f"No primary document found for accession {accession_id}")
        content = self.fetch_filing_document(cik, accession_id, primary_doc)
        return content, primary_doc

    def download_document_by_format(
        self, cik: str, accession_id: str, fmt: str
    ) -> tuple[str | bytes, str, str]:
        """
        Download a filing document in the requested format.
        fmt: 'pdf' | 'html' | 'htm'
        Returns (content, filename, media_type).
        For PDF: scans the filing index for a .pdf file; falls back to HTML.
        For HTML: uses primaryDocument from submissions directly.
        """
        want_pdf = fmt.lower() == "pdf"
        target = None

        if want_pdf:
            # Need the full document list to find a PDF
            index = self.fetch_filing_index(cik, accession_id)
            for d in index.get("documents", []):
                name  = (d.get("document") or "").lower()
                dtype = (d.get("type") or "").lower()
                if name.endswith(".pdf") or "pdf" in dtype:
                    target = d["document"]
                    break
            # No PDF found — fall back to primary HTML
            if not target:
                target = index.get("primary_doc")
        else:
            target = self._primary_doc_from_submissions(cik, accession_id)

        if not target:
            raise ValueError(f"No document found for accession {accession_id}")

        content = self.fetch_filing_document(cik, accession_id, target)
        if target.lower().endswith(".pdf") or isinstance(content, bytes):
            media_type = "application/pdf"
        else:
            media_type = "text/html"
        return content, target, media_type

    def get_viewer_url(self, cik: str, accession_id: str) -> str:
        """Official SEC EDGAR filing index page — lists all documents for this accession."""
        accn_dashed  = self._normalise_accn(accession_id)
        accn_clean   = accn_dashed.replace("-", "")
        cik_stripped = cik.lstrip("0")
        return (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{cik_stripped}/{accn_clean}/{accn_dashed}-index.htm"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Identifier resolution  (satisfies BaseSource)
    # ──────────────────────────────────────────────────────────────────────────

    def lookup(self, ticker: str) -> str:
        """Ticker → zero-padded 10-digit CIK string. Raises ValueError if not found."""
        tickers = self.fetch_tickers()
        ticker_upper = ticker.upper()
        for entry in tickers.values():
            if entry["ticker"].upper() == ticker_upper:
                return str(entry["cik_str"]).zfill(10)
        raise ValueError(f"Ticker '{ticker}' not found in EDGAR.")

    def search(self, name: str, limit: int = 10) -> list[dict]:
        """
        Company name → ranked list of matching companies with basic info.

        Scores matches from the full ticker list (exact > starts-with > contains),
        then fetches submissions for each to pull rich metadata.

        Returns list of dicts ready for JSON serialisation.
        """
        tickers = self.fetch_tickers()

        # Score every company name against the query
        scored = []
        for entry in tickers.values():
            s = _score(entry["title"], name)
            if s > 0:
                scored.append((s, entry))

        if not scored:
            return []

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:limit]

        results = []
        for _, entry in top:
            cik = str(entry["cik_str"]).zfill(10)
            try:
                sub = self.fetch_submissions(cik)
            except Exception:
                sub = {}

            # Latest 10-K date from recent filings
            recent = sub.get("filings", {}).get("recent", {})
            forms  = recent.get("form", [])
            dates  = recent.get("filingDate", [])
            latest_10k = next(
                (d for f, d in zip(forms, dates) if f == "10-K"), None
            )

            raw_category = sub.get("category") or ""
            category = ", ".join(
                p.strip() for p in raw_category.replace("<br>", "\n").splitlines() if p.strip()
            ) or None

            results.append({
                "cik":                    cik,
                "name":                   sub.get("name", entry["title"]),
                "tickers":                sub.get("tickers", [entry["ticker"]]),
                "exchanges":              sub.get("exchanges", []),
                "sic_code":               sub.get("sic"),
                "sic_description":        sub.get("sicDescription"),
                "state_of_incorporation": sub.get("stateOfIncorporationDescription"),
                "fiscal_year_end":        sub.get("fiscalYearEnd"),
                "filer_category":         category,
                "latest_10k":             latest_10k,
                "total_filings":          len(forms),
            })

        return results

    # ──────────────────────────────────────────────────────────────────────────
    # Full pipeline
    # ──────────────────────────────────────────────────────────────────────────

    def get_financials(self, ticker: str) -> CompanyFinancials:
        """Ticker → structured CompanyFinancials (income, balance, cashflow)."""
        cik = self.lookup(ticker)
        raw = self.fetch_company_facts(cik)
        return self._build_financials(cik, ticker, raw)

    def get_filings(self, cik: str) -> list[FilingInfo]:
        """
        CIK → list of annual (10-K) filings, newest first.
        Fetches all pagination pages so the full history is returned.
        Each item has an accession_id you can pass to get_filing_financials().
        """
        sub = self.fetch_submissions(cik)
        filing_data = sub.get("filings", {})

        # Collect all filing blocks — recent + any extra pages
        blocks = [filing_data.get("recent", {})]
        for page in filing_data.get("files", []):
            url = f"https://data.sec.gov/submissions/{page['name']}"
            blocks.append(self._get(url))

        filings = []
        for block in blocks:
            accessions  = block.get("accessionNumber", [])
            forms       = block.get("form", [])
            filed_dates = block.get("filingDate", [])
            periods     = block.get("reportDate", [])

            primary_docs = block.get("primaryDocument", [])
            xbrl_flags   = block.get("isXBRL", [])
            for accn, form, filed, period, pdoc, is_xbrl in zip(
                accessions, forms, filed_dates, periods,
                primary_docs if primary_docs else [""] * len(accessions),
                xbrl_flags   if xbrl_flags   else [0]  * len(accessions),
            ):
                if form not in ("10-K", "10-K/A"):
                    continue
                fy = int(period[:4]) if period else None
                filings.append(FilingInfo(
                    accession_id=accn,
                    form=form,
                    fiscal_year=fy,
                    period_end=period or "",
                    filed_date=filed or "",
                    primary_document=pdoc or None,
                    has_xbrl=bool(is_xbrl),
                ))

        # Sort newest first
        filings.sort(key=lambda f: f.filed_date, reverse=True)
        return filings

    def get_filing_financials(self, cik: str, accession_id: str) -> FilingFinancials:
        """CIK + accession_id → structured financials for that exact filing."""
        accn  = self._normalise_accn(accession_id)
        sub   = self.fetch_submissions(cik)
        raw   = self.fetch_company_facts(cik)
        meta  = self._filing_meta(sub, accn)
        return self._build_filing_financials(cik, accn, meta, raw.get("facts", {}), raw.get("entityName", ""))

    def get_all_financials(self, cik: str) -> list[FilingFinancials]:
        """
        CIK → structured financials for ALL 10-K filings, newest first.
        2 EDGAR API calls total (submissions + company facts).
        """
        raw   = self.fetch_company_facts(cik)
        facts = raw.get("facts", {})
        name  = raw.get("entityName", "")
        # get_filings uses fetch_submissions which is now cached — no extra HTTP call
        filings = self.get_filings(cik)
        results = []
        for filing in filings:
            accn = self._normalise_accn(filing.accession_id)
            meta = {
                "period":  filing.period_end,
                "filed":   filing.filed_date,
                "form":    filing.form,
            }
            results.append(
                self._build_filing_financials(cik, accn, meta, facts, name)
            )
        return results

    # ──────────────────────────────────────────────────────────────────────────
    # Private: parsing helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _normalise_accn(self, accession_id: str) -> str:
        """Ensure accession is in EDGAR dash format: XXXXXXXXXX-YY-ZZZZZZ.
        EDGAR accessions are always 18 digits (10-digit CIK + 2-digit year + 6-digit seq).
        Raises ValueError with a clear message if the input is malformed.
        """
        a = accession_id.replace("-", "")
        if len(a) != 18:
            raise ValueError(
                f"Invalid accession_id '{accession_id}': expected 18 digits "
                f"(format XXXXXXXXXX-YY-ZZZZZZ), got {len(a)}. "
                f"Use the accession_id returned by /company/{{cik}}/filings."
            )
        return f"{a[:10]}-{a[10:12]}-{a[12:]}"

    def _filing_meta(self, sub: dict, accn: str) -> dict:
        """
        Extract period_end, filed_date, form for one accession
        by scanning all submission pages.
        """
        filing_data = sub.get("filings", {})
        blocks = [filing_data.get("recent", {})]
        for page in filing_data.get("files", []):
            url = f"https://data.sec.gov/submissions/{page['name']}"
            blocks.append(self._get(url))

        for block in blocks:
            accns   = block.get("accessionNumber", [])
            periods = block.get("reportDate", [])
            filed   = block.get("filingDate", [])
            forms   = block.get("form", [])
            for i, a in enumerate(accns):
                if a == accn:
                    return {
                        "period": periods[i],
                        "filed":  filed[i],
                        "form":   forms[i],
                    }
        return {}

    def _build_filing_financials(
        self, cik: str, accn: str, meta: dict, facts: dict, name: str
    ) -> FilingFinancials:
        period_end  = meta.get("period", "")
        filed_date  = meta.get("filed", "")
        form        = meta.get("form", "10-K")
        fiscal_year = int(period_end[:4]) if period_end else None

        d = self._extract_values_for_accession(facts, accn, fiscal_year or 2024, period_end)
        return FilingFinancials(
            cik=cik,
            name=name,
            accession_id=accn,
            fiscal_year=fiscal_year,
            period_end=period_end,
            filed_date=filed_date,
            form=form,
            income_statement=self._build_income(fiscal_year, period_end, form, d),
            balance_sheet=self._build_balance(fiscal_year, period_end, form, d),
            cash_flow=self._build_cashflow(fiscal_year, period_end, form, d),
        )

    def _extract_values_for_accession(
        self, facts: dict, accession: str, fiscal_year: int, period_end: str = ""
    ) -> dict:
        """
        Two-step extraction:
        1. PRE-FILTER: scan all us-gaap tags, keep only records matching
           this exact accession + form + period_end → { tag: value }
        2. TAXONOMY MAP: for each field, pick the first matching tag
           from the year-appropriate taxonomy ordering.
        """
        # ── Step 1: pre-filter all tags for this exact year ──────────────────
        # Primary: match by accession + form + period_end
        # Fallback: if accession not yet in company facts (XBRL processing lag),
        #           use any 10-K accession with the same period_end
        year_snapshot: dict[str, float] = {}
        for tag, entry in facts.get("us-gaap", {}).items():
            for unit, recs in entry.get("units", {}).items():
                if unit not in ("USD", "shares", "USD/shares"):
                    continue
                for r in recs:
                    if (
                        r.get("accn") == accession
                        and r.get("form") in ("10-K", "10-K/A")
                        and r.get("end") == period_end
                    ):
                        year_snapshot[tag] = r["val"]
                        break

        if not year_snapshot and period_end:
            # Accession not yet indexed in company facts — try any 10-K for same period_end
            for tag, entry in facts.get("us-gaap", {}).items():
                for unit, recs in entry.get("units", {}).items():
                    if unit not in ("USD", "shares", "USD/shares"):
                        continue
                    for r in recs:
                        if (
                            r.get("form") in ("10-K", "10-K/A")
                            and r.get("end") == period_end
                        ):
                            year_snapshot[tag] = r["val"]
                            break

        # ── Step 2: map tag names → field names via taxonomy ─────────────────
        resolved = self._tags_for_year(fiscal_year)
        d = {}
        all_fields = (
            self._cfg["income_fields"]
            | self._cfg["balance_fields"]
            | self._cfg["cashflow_fields"]
        )
        for field in all_fields:
            for tag in resolved.get(field, []):
                if tag in year_snapshot:
                    d[field] = year_snapshot[tag]
                    break
        return d

    def _build_income(
        self, fy: Optional[int], end: str, form: str, d: dict
    ) -> Optional[IncomeStatement]:
        income_f = self._cfg["income_fields"]
        if not any(f in d for f in income_f):
            return None
        ebit   = d.get("operating_income")
        da     = d.get("depreciation_amortization")
        rev    = d.get("revenue")
        gp     = d.get("gross_profit")
        ni     = d.get("net_income")
        return IncomeStatement(
            fiscal_year=fy or 0, period_end=end, form=form,
            revenue=rev,
            cost_of_revenue=d.get("cost_of_revenue"),
            gross_profit=gp,
            research_and_development=d.get("research_and_development"),
            selling_general_administrative=d.get("selling_general_administrative"),
            selling_and_marketing=d.get("selling_and_marketing"),
            general_and_administrative=d.get("general_and_administrative"),
            advertising_expense=d.get("advertising_expense"),
            operating_expenses=d.get("operating_expenses"),
            operating_income=ebit,
            nonoperating_income=d.get("nonoperating_income"),
            interest_expense=d.get("interest_expense"),
            interest_income=d.get("interest_income"),
            income_before_tax=d.get("income_before_tax"),
            income_tax=d.get("income_tax"),
            net_income=ni,
            eps_basic=d.get("eps_basic"),
            eps_diluted=d.get("eps_diluted"),
            dividends_per_share=d.get("dividends_per_share"),
            shares_outstanding=d.get("shares_outstanding"),
            shares_diluted=d.get("shares_diluted"),
            depreciation_amortization=da,
            amortization_of_intangibles=d.get("amortization_of_intangibles"),
            stock_based_compensation=d.get("stock_based_compensation"),
            ebitda=(ebit + da) if ebit is not None and da is not None else None,
            gross_margin=(gp / rev) if gp and rev else None,
            operating_margin=(ebit / rev) if ebit is not None and rev else None,
            net_margin=(ni / rev) if ni is not None and rev else None,
        )

    def _build_balance(
        self, fy: Optional[int], end: str, form: str, d: dict
    ) -> Optional[BalanceSheet]:
        if not any(f in d for f in self._cfg["balance_fields"]):
            return None
        return BalanceSheet(
            fiscal_year=fy or 0, period_end=end, form=form,
            cash_and_equivalents=d.get("cash_and_equivalents"),
            short_term_investments=d.get("short_term_investments"),
            accounts_receivable=d.get("accounts_receivable"),
            inventory=d.get("inventory"),
            other_current_assets=d.get("other_current_assets"),
            current_assets=d.get("current_assets"),
            property_plant_equipment_net=d.get("property_plant_equipment_net"),
            operating_lease_rou_asset=d.get("operating_lease_rou_asset"),
            goodwill=d.get("goodwill"),
            intangible_assets=d.get("intangible_assets"),
            marketable_securities_noncurrent=d.get("marketable_securities_noncurrent"),
            deferred_tax_assets=d.get("deferred_tax_assets"),
            other_noncurrent_assets=d.get("other_noncurrent_assets"),
            noncurrent_assets=d.get("noncurrent_assets"),
            total_assets=d.get("total_assets"),
            accounts_payable=d.get("accounts_payable"),
            accrued_liabilities=d.get("accrued_liabilities"),
            accrued_income_taxes=d.get("accrued_income_taxes"),
            deferred_revenue_current=d.get("deferred_revenue_current"),
            commercial_paper=d.get("commercial_paper"),
            long_term_debt_current=d.get("long_term_debt_current"),
            operating_lease_liability_current=d.get("operating_lease_liability_current"),
            other_current_liabilities=d.get("other_current_liabilities"),
            current_liabilities=d.get("current_liabilities"),
            long_term_debt=d.get("long_term_debt"),
            operating_lease_liability_noncurrent=d.get("operating_lease_liability_noncurrent"),
            finance_lease_liability=d.get("finance_lease_liability"),
            deferred_tax_liabilities=d.get("deferred_tax_liabilities"),
            other_noncurrent_liabilities=d.get("other_noncurrent_liabilities"),
            noncurrent_liabilities=d.get("noncurrent_liabilities"),
            total_liabilities=d.get("total_liabilities"),
            total_debt=d.get("total_debt"),
            retained_earnings=d.get("retained_earnings"),
            total_equity=d.get("total_equity"),
            total_liabilities_and_equity=d.get("total_liabilities_and_equity"),
        )

    def _build_cashflow(
        self, fy: Optional[int], end: str, form: str, d: dict
    ) -> Optional[CashFlow]:
        if not any(f in d for f in self._cfg["cashflow_fields"]):
            return None
        ocf   = d.get("operating_cash_flow")
        capex = abs(d["capex"]) if d.get("capex") is not None else None
        return CashFlow(
            fiscal_year=fy or 0, period_end=end, form=form,
            operating_cash_flow=ocf,
            net_income_cf=d.get("net_income_cf"),
            depreciation_amortization_cf=d.get("depreciation_amortization_cf"),
            stock_based_comp_cf=d.get("stock_based_comp_cf"),
            deferred_income_tax_cf=d.get("deferred_income_tax_cf"),
            investing_cash_flow=d.get("investing_cash_flow"),
            capex=capex,
            acquisitions=d.get("acquisitions"),
            purchases_of_investments=d.get("purchases_of_investments"),
            proceeds_from_investments=d.get("proceeds_from_investments"),
            financing_cash_flow=d.get("financing_cash_flow"),
            stock_repurchases=d.get("stock_repurchases"),
            dividends_paid=d.get("dividends_paid"),
            debt_proceeds=d.get("debt_proceeds"),
            debt_repayments=d.get("debt_repayments"),
            stock_issuance_proceeds=d.get("stock_issuance_proceeds"),
            tax_withholding_on_equity_awards=d.get("tax_withholding_on_equity_awards"),
            free_cash_flow=(ocf - capex) if ocf is not None and capex is not None else None,
            net_change_in_cash=d.get("net_change_in_cash"),
        )

    def _extract_annual_values(self, units: list[dict]) -> dict[str, dict]:
        """
        From a list of XBRL unit records keep only annual (10-K) entries.
        For each period-end, keep the most recently filed record.
        Returns {period_end: {val, fy, form, filed}}
        """
        annual: dict[str, dict] = {}
        for rec in units:
            if rec.get("form") not in ("10-K", "10-K/A"):
                continue
            end = rec.get("end", "")
            if not end:
                continue
            if end not in annual or rec.get("filed", "") > annual[end]["filed"]:
                annual[end] = {
                    "val":   rec["val"],
                    "fy":    rec.get("fy"),
                    "form":  rec.get("form"),
                    "filed": rec.get("filed", ""),
                }
        return annual

    def _pick_value(self, facts: dict, field: str, fiscal_year: Optional[int] = None) -> dict[str, dict]:
        """
        Try each tag for `field` in filer-count order.
        When fiscal_year is given, uses the matching taxonomy to sort tags.
        When omitted (multi-year path), falls back to the raw config candidate list
        so no tags are dropped for older filings.
        Returns the first tag that has data as {period_end: {val, fy, form}}.
        """
        if fiscal_year is not None:
            tags = self._tags_for_year(fiscal_year).get(field, [])
        else:
            tags = self._xbrl_map.get(field, [])
        for tag in tags:
            entry = facts.get("us-gaap", {}).get(tag)
            if not entry:
                continue
            units = entry.get("units", {})
            raw_list = units.get("USD") or units.get("shares") or units.get("USD/shares")
            if raw_list:
                return self._extract_annual_values(raw_list)
        return {}

    def _build_financials(
        self, cik: str, ticker: str, raw: dict
    ) -> CompanyFinancials:
        """
        Combine all picked values by period_end and build the three statement models.
        """
        facts = raw.get("facts", {})
        income_f  = self._cfg["income_fields"]
        balance_f = self._cfg["balance_fields"]
        cashflow_f = self._cfg["cashflow_fields"]

        # Collect all values keyed by period_end
        period_data: dict[str, dict] = {}
        for field in income_f | balance_f | cashflow_f:
            for end, rec in self._pick_value(facts, field).items():
                if end not in period_data:
                    period_data[end] = {"fy": rec.get("fy"), "form": rec.get("form", "10-K")}
                period_data[end][field] = rec["val"]

        income_statements, balance_sheets, cash_flows = [], [], []

        for end, d in sorted(period_data.items()):
            fy   = d.get("fy") or int(end[:4])
            form = d.get("form", "10-K")

            # Derived metrics
            ocf    = d.get("operating_cash_flow")
            capex  = abs(d["capex"]) if d.get("capex") is not None else None
            fcf    = (ocf - capex) if ocf is not None and capex is not None else None
            ebit   = d.get("operating_income")
            da     = d.get("depreciation_amortization")
            ebitda = (ebit + da) if ebit is not None and da is not None else None
            rev    = d.get("revenue")
            gp     = d.get("gross_profit")
            ni     = d.get("net_income")
            gross_margin   = (gp / rev)   if gp  is not None and rev else None
            op_margin      = (ebit / rev) if ebit is not None and rev else None
            net_margin     = (ni / rev)   if ni   is not None and rev else None

            if any(f in d for f in income_f):
                income_statements.append(IncomeStatement(
                    fiscal_year=fy, period_end=end, form=form,
                    revenue=rev,
                    cost_of_revenue=d.get("cost_of_revenue"),
                    gross_profit=gp,
                    research_and_development=d.get("research_and_development"),
                    selling_general_administrative=d.get("selling_general_administrative"),
                    selling_and_marketing=d.get("selling_and_marketing"),
                    general_and_administrative=d.get("general_and_administrative"),
                    advertising_expense=d.get("advertising_expense"),
                    operating_expenses=d.get("operating_expenses"),
                    operating_income=ebit,
                    nonoperating_income=d.get("nonoperating_income"),
                    interest_expense=d.get("interest_expense"),
                    interest_income=d.get("interest_income"),
                    income_before_tax=d.get("income_before_tax"),
                    income_tax=d.get("income_tax"),
                    net_income=ni,
                    eps_basic=d.get("eps_basic"),
                    eps_diluted=d.get("eps_diluted"),
                    dividends_per_share=d.get("dividends_per_share"),
                    shares_outstanding=d.get("shares_outstanding"),
                    shares_diluted=d.get("shares_diluted"),
                    depreciation_amortization=da,
                    amortization_of_intangibles=d.get("amortization_of_intangibles"),
                    stock_based_compensation=d.get("stock_based_compensation"),
                    ebitda=ebitda,
                    gross_margin=gross_margin,
                    operating_margin=op_margin,
                    net_margin=net_margin,
                ))

            if any(f in d for f in balance_f):
                balance_sheets.append(BalanceSheet(
                    fiscal_year=fy, period_end=end, form=form,
                    cash_and_equivalents=d.get("cash_and_equivalents"),
                    short_term_investments=d.get("short_term_investments"),
                    accounts_receivable=d.get("accounts_receivable"),
                    inventory=d.get("inventory"),
                    other_current_assets=d.get("other_current_assets"),
                    current_assets=d.get("current_assets"),
                    property_plant_equipment_net=d.get("property_plant_equipment_net"),
                    operating_lease_rou_asset=d.get("operating_lease_rou_asset"),
                    goodwill=d.get("goodwill"),
                    intangible_assets=d.get("intangible_assets"),
                    marketable_securities_noncurrent=d.get("marketable_securities_noncurrent"),
                    deferred_tax_assets=d.get("deferred_tax_assets"),
                    other_noncurrent_assets=d.get("other_noncurrent_assets"),
                    noncurrent_assets=d.get("noncurrent_assets"),
                    total_assets=d.get("total_assets"),
                    accounts_payable=d.get("accounts_payable"),
                    accrued_liabilities=d.get("accrued_liabilities"),
                    accrued_income_taxes=d.get("accrued_income_taxes"),
                    deferred_revenue_current=d.get("deferred_revenue_current"),
                    commercial_paper=d.get("commercial_paper"),
                    long_term_debt_current=d.get("long_term_debt_current"),
                    operating_lease_liability_current=d.get("operating_lease_liability_current"),
                    other_current_liabilities=d.get("other_current_liabilities"),
                    current_liabilities=d.get("current_liabilities"),
                    long_term_debt=d.get("long_term_debt"),
                    operating_lease_liability_noncurrent=d.get("operating_lease_liability_noncurrent"),
                    finance_lease_liability=d.get("finance_lease_liability"),
                    deferred_tax_liabilities=d.get("deferred_tax_liabilities"),
                    other_noncurrent_liabilities=d.get("other_noncurrent_liabilities"),
                    noncurrent_liabilities=d.get("noncurrent_liabilities"),
                    total_liabilities=d.get("total_liabilities"),
                    total_debt=d.get("total_debt"),
                    retained_earnings=d.get("retained_earnings"),
                    total_equity=d.get("total_equity"),
                    total_liabilities_and_equity=d.get("total_liabilities_and_equity"),
                ))

            if any(f in d for f in cashflow_f):
                cash_flows.append(CashFlow(
                    fiscal_year=fy, period_end=end, form=form,
                    operating_cash_flow=ocf,
                    net_income_cf=d.get("net_income_cf"),
                    depreciation_amortization_cf=d.get("depreciation_amortization_cf"),
                    stock_based_comp_cf=d.get("stock_based_comp_cf"),
                    deferred_income_tax_cf=d.get("deferred_income_tax_cf"),
                    investing_cash_flow=d.get("investing_cash_flow"),
                    capex=capex,
                    acquisitions=d.get("acquisitions"),
                    purchases_of_investments=d.get("purchases_of_investments"),
                    proceeds_from_investments=d.get("proceeds_from_investments"),
                    financing_cash_flow=d.get("financing_cash_flow"),
                    stock_repurchases=d.get("stock_repurchases"),
                    dividends_paid=d.get("dividends_paid"),
                    debt_proceeds=d.get("debt_proceeds"),
                    debt_repayments=d.get("debt_repayments"),
                    stock_issuance_proceeds=d.get("stock_issuance_proceeds"),
                    tax_withholding_on_equity_awards=d.get("tax_withholding_on_equity_awards"),
                    free_cash_flow=fcf,
                    net_change_in_cash=d.get("net_change_in_cash"),
                ))

        return CompanyFinancials(
            cik=cik,
            ticker=ticker.upper(),
            name=raw.get("entityName", ""),
            income_statements=income_statements,
            balance_sheets=balance_sheets,
            cash_flows=cash_flows,
        )
