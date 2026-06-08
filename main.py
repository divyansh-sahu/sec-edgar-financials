import sys
import json
import click
from rich.console import Console
from rich.table import Table
from rich import box

from sources.edgar import EdgarAPI
from storage.local import save
from models.financials import CompanyFinancials

console = Console()

# Registry — add new sources here as they are implemented
SOURCES = {
    "edgar": EdgarAPI,
}


def _get_source(source: str):
    cls = SOURCES.get(source.lower())
    if not cls:
        console.print(f"[red]Unknown source '{source}'. Available: {', '.join(SOURCES)}[/]")
        sys.exit(1)
    return cls()


# ── Display helpers ────────────────────────────────────────────────────────────

def _fmt(val: float | None, scale: str = "B") -> str:
    if val is None:
        return "—"
    divisor = {"B": 1e9, "M": 1e6}.get(scale, 1)
    prefix = "$" if scale in ("B", "M") else ""
    return f"{prefix}{val / divisor:,.2f}{scale}"


def _print_financials(company: CompanyFinancials) -> None:
    console.print(
        f"\n[bold cyan]{company.name}[/] ([yellow]{company.ticker}[/])"
        f"  ·  CIK [dim]{company.cik}[/]\n"
    )

    if company.income_statements:
        t = Table(title="Income Statement", box=box.SIMPLE_HEAVY)
        for col, just in [
            ("Year", "left"), ("Revenue", "right"), ("Gross Profit", "right"),
            ("Op. Income", "right"), ("Net Income", "right"),
            ("EPS (dil.)", "right"), ("EBITDA", "right"),
        ]:
            t.add_column(col, justify=just)
        for s in sorted(company.income_statements, key=lambda x: x.period_end)[-10:]:
            t.add_row(
                str(s.fiscal_year),
                _fmt(s.revenue),
                _fmt(s.gross_profit),
                _fmt(s.operating_income),
                _fmt(s.net_income),
                f"${s.eps_diluted:.2f}" if s.eps_diluted else "—",
                _fmt(s.ebitda),
            )
        console.print(t)

    if company.balance_sheets:
        t = Table(title="Balance Sheet", box=box.SIMPLE_HEAVY)
        for col, just in [
            ("Year", "left"), ("Total Assets", "right"), ("Total Liabilities", "right"),
            ("Equity", "right"), ("Cash", "right"), ("LT Debt", "right"),
        ]:
            t.add_column(col, justify=just)
        for s in sorted(company.balance_sheets, key=lambda x: x.period_end)[-10:]:
            t.add_row(
                str(s.fiscal_year),
                _fmt(s.total_assets),
                _fmt(s.total_liabilities),
                _fmt(s.total_equity),
                _fmt(s.cash_and_equivalents),
                _fmt(s.long_term_debt),
            )
        console.print(t)

    if company.cash_flows:
        t = Table(title="Cash Flow", box=box.SIMPLE_HEAVY)
        for col, just in [
            ("Year", "left"), ("Operating", "right"), ("Investing", "right"),
            ("Financing", "right"), ("CapEx", "right"), ("Free CF", "right"),
        ]:
            t.add_column(col, justify=just)
        for s in sorted(company.cash_flows, key=lambda x: x.period_end)[-10:]:
            t.add_row(
                str(s.fiscal_year),
                _fmt(s.operating_cash_flow),
                _fmt(s.investing_cash_flow),
                _fmt(s.financing_cash_flow),
                _fmt(s.capex),
                _fmt(s.free_cash_flow),
            )
        console.print(t)


# ── CLI commands ───────────────────────────────────────────────────────────────

@click.group()
def cli():
    """Financial scraper — pulls structured financials from official filings."""


@cli.command()
@click.argument("ticker")
@click.option("--source", default="edgar", show_default=True, help="Data source to use.")
@click.option("--no-save", is_flag=True, help="Print only, skip file output.")
def fetch(ticker: str, source: str, no_save: bool):
    """Fetch financials for TICKER (e.g. AAPL, MSFT, TSLA)."""
    api = _get_source(source)
    with console.status(f"[green]Fetching {ticker.upper()} from {source.upper()}…"):
        try:
            company = api.get_financials(ticker)
        except ValueError as e:
            console.print(f"[red]Error:[/] {e}")
            sys.exit(1)

    _print_financials(company)

    if not no_save:
        paths = save(company)
        console.print("\n[green]Saved:[/]")
        for p in paths["json"] + paths["csv"]:
            console.print(f"  {p}")


@cli.command("fetch-many")
@click.argument("tickers", nargs=-1, required=True)
@click.option("--source", default="edgar", show_default=True)
@click.option("--no-save", is_flag=True)
def fetch_many(tickers: tuple[str, ...], source: str, no_save: bool):
    """Fetch financials for multiple TICKERS at once."""
    api = _get_source(source)
    for ticker in tickers:
        with console.status(f"[green]Fetching {ticker.upper()}…"):
            try:
                company = api.get_financials(ticker)
            except Exception as e:
                console.print(f"[red]{ticker}: {e}[/]")
                continue
        _print_financials(company)
        if not no_save:
            paths = save(company)
            console.print(f"[green]Saved {ticker.upper()}:[/] {paths['json'][0]}\n")


@cli.command()
@click.argument("name")
@click.option("--source", default="edgar", show_default=True)
@click.option("--limit", default=10, show_default=True, help="Max results to return.")
def search(name: str, source: str, limit: int):
    """Search for companies matching NAME. Returns ranked JSON results."""
    api = _get_source(source)
    with console.status(f"[green]Searching '{name}'…"):
        results = api.search(name, limit=limit)

    if not results:
        console.print("[yellow]No results.[/]")
        return

    console.print(json.dumps(results, indent=2))


if __name__ == "__main__":
    cli()
