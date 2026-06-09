from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse, Response
from sources.edgar import EdgarAPI
from config import EDGAR

app = FastAPI(title="EDGAR Financials API", version="1.0")
edgar = EdgarAPI()


@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.api_route("/health", methods=["GET", "HEAD"], include_in_schema=False)
def health():
    return {"status": "ok"}


# ── Search ─────────────────────────────────────────────────────────────────────

@app.get("/search", tags=["Search"])
def search(
    name: str = Query(..., description="Company name"),
    limit: int = Query(10, ge=1, le=50),
):
    """
    Search for companies by name.
    Returns CIK + basic info. Use the CIK in the next step.
    """
    results = edgar.search(name, limit=limit)
    if not results:
        raise HTTPException(status_code=404, detail=f"No companies found for '{name}'")
    return results


# ── Filings ────────────────────────────────────────────────────────────────────

@app.get("/company/{cik}/filings", tags=["Filings"])
def get_filings(cik: str):
    """
    List all annual (10-K) filings for a company CIK.
    Returns filing year, period end, filed date, and accession_id.
    Use the accession_id in the next step to get the financials.
    """
    try:
        filings = edgar.get_filings(cik)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not filings:
        raise HTTPException(status_code=404, detail=f"No 10-K filings found for CIK {cik}")
    return filings


@app.get("/company/{cik}/financials", tags=["Filings"])
def get_all_financials(cik: str):
    """
    All 10-K filings for a company with full structured financials for each.
    2 EDGAR API calls total regardless of filing count.
    Returns list ordered newest → oldest.
    """
    try:
        return edgar.get_all_financials(cik)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/company/{cik}/submissions", tags=["Filings"])
def get_submissions(cik: str):
    """Raw EDGAR submissions — company metadata and full filing history."""
    try:
        return edgar.fetch_submissions(cik)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Financials ─────────────────────────────────────────────────────────────────

@app.get("/filing/{cik}/{accession_id}", tags=["Financials"])
def get_filing_financials(cik: str, accession_id: str):
    """
    Get structured financials for one specific filing.
    Pass the accession_id from the /company/{cik}/filings response.
    Returns income statement, balance sheet, and cash flow for that filing year.
    """
    try:
        return edgar.get_filing_financials(cik, accession_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Documents ──────────────────────────────────────────────────────────────────

@app.get("/filing/{cik}/{accession_id}/documents", tags=["Documents"])
def list_filing_documents(cik: str, accession_id: str):
    """
    List all documents inside a filing.
    Shows filename, type, description, and size for each.
    Use this to see what's available before downloading.
    """
    try:
        return edgar.fetch_filing_index(cik, accession_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/filing/{cik}/{accession_id}/download", tags=["Documents"])
def download_filing(
    cik: str,
    accession_id: str,
    format: str = Query("html", description="Document format: 'html' or 'pdf'"),
):
    """
    Download the official 10-K filing document.

    - format=html (default) — inline XBRL HTML exactly as filed with the SEC
    - format=pdf            — PDF version if the company included one; falls back to HTML

    Returns the file as a downloadable attachment.
    """
    try:
        content, filename, media_type = edgar.download_document_by_format(
            cik, accession_id, format
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return Response(
        content=content if isinstance(content, bytes) else content.encode("utf-8"),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/filing/{cik}/{accession_id}/viewer", tags=["Documents"])
def view_filing(cik: str, accession_id: str):
    """
    Returns the official SEC EDGAR viewer URL for this filing.
    Open the url in a browser to see the full filing index on sec.gov.
    """
    try:
        url = edgar.get_viewer_url(cik, accession_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"viewer_url": url}


# ── Raw Data ───────────────────────────────────────────────────────────────────

@app.get("/filing/{cik}/{accession_id}/raw", tags=["Raw Data"])
def get_raw(cik: str, accession_id: str):
    """
    All EDGAR company_facts records for this accession, exactly as returned by SEC.
    Every XBRL tag filed under this accession with its full record(s).
    A 10-K includes comparative data so one tag may have multiple records
    (e.g. current year + prior year). No filters applied.
    """
    try:
        return edgar.get_raw_for_accession(cik, accession_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/filing/{cik}/{accession_id}/raw/filtered", tags=["Raw Data"])
def get_raw_filtered(cik: str, accession_id: str):
    """
    Raw EDGAR data after applying all our filters:
    accn == accession_id AND form == 10-K AND end == period_end.

    Returns a flat { tag_name: value } snapshot — exactly one value per tag,
    for this specific year only. This is the input to our taxonomy mapping step.
    """
    try:
        return edgar.get_snapshot_for_accession(cik, accession_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/filing/{cik}/{accession_id}/raw/mapped", tags=["Raw Data"])
def get_raw_mapped(cik: str, accession_id: str):
    """
    Taxonomy mapping result for this filing.
    For each of our output fields, shows which XBRL tag was used and its value.
    null means no matching tag was found in this filing for that field.
    """
    try:
        return edgar.get_mapped_for_accession(cik, accession_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Taxonomy ───────────────────────────────────────────────────────────────────

@app.get("/taxonomy", tags=["Taxonomy"])
def get_taxonomy(
    year: int = Query(2024, ge=2009, le=2030, description="Fiscal year — tag names changed across GAAP versions"),
):
    """
    Our supported XBRL field mappings for a given fiscal year.

    For each output field shows:
    - description: what the field represents
    - statement: which financial statement it belongs to
    - tags: XBRL tag names we try in priority order for this year
            (first tag with data in a filing wins)
    """
    xbrl_map     = EDGAR["xbrl_map"]
    descriptions = EDGAR["field_descriptions"]
    income_f     = EDGAR["income_fields"]
    balance_f    = EDGAR["balance_fields"]
    cashflow_f   = EDGAR["cashflow_fields"]

    def statement_for(field: str) -> str:
        if field in income_f:   return "income_statement"
        if field in balance_f:  return "balance_sheet"
        if field in cashflow_f: return "cash_flow"
        return "other"

    # Use the taxonomy manager to get year-appropriate tag ordering
    from sources.edgar import EdgarAPI as _E
    resolved = _E()._tags_for_year(year)

    fields = {}
    for field in sorted(xbrl_map.keys()):
        fields[field] = {
            "description": descriptions.get(field, ""),
            "statement":   statement_for(field),
            "tags":        resolved.get(field, xbrl_map[field]),
        }

    return {
        "year":         year,
        "total_fields": len(fields),
        "fields":       fields,
    }
