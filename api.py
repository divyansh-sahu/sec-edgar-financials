from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse, Response
from sources.edgar import EdgarAPI

app = FastAPI(title="EDGAR Financials API", version="1.0")
edgar = EdgarAPI()


@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.api_route("/health", methods=["GET", "HEAD"], include_in_schema=False)
def health():
    return {"status": "ok"}


# ── Step 1: Search ─────────────────────────────────────────────────────────────

@app.get("/search")
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


# ── Step 2: List filings for a company ────────────────────────────────────────

@app.get("/company/{cik}/filings")
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


# ── Step 3: Get financials for a specific filing ───────────────────────────────

@app.get("/filing/{cik}/{accession_id}")
def get_filing_financials(cik: str, accession_id: str):
    """
    Get structured financials for one specific filing.
    Pass the accession_id from the /company/{cik}/filings response.
    Returns income statement, balance sheet, and cash flow for that filing year.
    """
    try:
        return edgar.get_filing_financials(cik, accession_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── All filings with financials ───────────────────────────────────────────────

@app.get("/company/{cik}/financials")
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


# ── Download raw filing document ──────────────────────────────────────────────

@app.get("/filing/{cik}/{accession_id}/download")
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
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return Response(
        content=content if isinstance(content, bytes) else content.encode("utf-8"),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/filing/{cik}/{accession_id}/viewer")
def view_filing(cik: str, accession_id: str):
    """
    Returns the official SEC EDGAR viewer URL for this filing.
    Open the url in a browser to see the full filing index on sec.gov.
    """
    url = edgar.get_viewer_url(cik, accession_id)
    return {"viewer_url": url}


@app.get("/filing/{cik}/{accession_id}/documents")
def list_filing_documents(cik: str, accession_id: str):
    """
    List all documents inside a filing.
    Shows filename, type, description, and size for each.
    Use this to see what's available before downloading.
    """
    try:
        return edgar.fetch_filing_index(cik, accession_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Extras ─────────────────────────────────────────────────────────────────────

@app.get("/company/{cik}/submissions")
def get_submissions(cik: str):
    """Raw EDGAR submissions — company metadata and full filing history."""
    try:
        return edgar.fetch_submissions(cik)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
