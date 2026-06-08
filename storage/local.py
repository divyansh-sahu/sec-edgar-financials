import json
import csv
import os
from pathlib import Path
from models.financials import CompanyFinancials

OUTPUT_DIR = Path("output")


def _ensure_dir(company: CompanyFinancials) -> Path:
    d = OUTPUT_DIR / company.ticker.upper()
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_json(company: CompanyFinancials) -> str:
    d = _ensure_dir(company)
    path = d / "financials.json"
    path.write_text(
        json.dumps(company.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )
    return str(path)


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def save_csv(company: CompanyFinancials) -> list[str]:
    d = _ensure_dir(company)
    paths = []

    if company.income_statements:
        p = d / "income_statement.csv"
        _write_csv(p, [s.model_dump() for s in company.income_statements])
        paths.append(str(p))

    if company.balance_sheets:
        p = d / "balance_sheet.csv"
        _write_csv(p, [s.model_dump() for s in company.balance_sheets])
        paths.append(str(p))

    if company.cash_flows:
        p = d / "cash_flow.csv"
        _write_csv(p, [s.model_dump() for s in company.cash_flows])
        paths.append(str(p))

    return paths


def save(company: CompanyFinancials) -> dict[str, list[str]]:
    json_path = save_json(company)
    csv_paths = save_csv(company)
    return {"json": [json_path], "csv": csv_paths}
