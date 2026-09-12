"""Tests for broker statement parsing, schema mapping, and portfolio conversion."""

from datetime import date
from pathlib import Path

import pytest
from app.broker_statement import (
    BrokerStatement,
    StatementMetadata,
    convert_statement_to_portfolio,
    parse_excel_statement,
)
from app.schemas import PortfolioRequest

SAMPLE_FILE = Path(__file__).resolve().parent.parent.parent / "ignore_offline" / "holdings-OD7237.xlsx"


@pytest.mark.skipif(not SAMPLE_FILE.exists(), reason="Sample statement file not found")
def test_parse_excel_statement_offline_file():
    """Verify parsing real Zerodha Excel holdings statement."""
    statement = parse_excel_statement(SAMPLE_FILE)

    assert isinstance(statement, BrokerStatement)
    assert statement.metadata.client_id == "OD7237"
    assert statement.metadata.as_of_date == date(2026, 9, 7)
    assert "Equity" in statement.metadata.sheet_names
    assert "Mutual Funds" in statement.metadata.sheet_names
    assert "Combined" in statement.metadata.sheet_names

    # Check Equities parsed
    assert len(statement.equity_holdings) == 8
    symbols = [h.symbol for h in statement.equity_holdings]
    assert "BAJAJHFL" in symbols
    assert "BHEL" in symbols
    assert "IDFCFIRSTB" in symbols
    assert "ITC" in symbols
    assert "SGBJU29III-GB" in symbols

    # Check Mutual Funds parsed
    assert len(statement.mf_holdings) == 5
    mf_isins = [m.isin for m in statement.mf_holdings]
    assert "INF760K01FT8" in mf_isins
    assert "INF740K01QA7" in mf_isins
    assert "INF959L01GR6" in mf_isins

    # Check summaries
    assert statement.combined_summary is not None
    assert statement.combined_summary.invested_value > 700000.0
    assert statement.combined_summary.present_value > 1000000.0


@pytest.mark.skipif(not SAMPLE_FILE.exists(), reason="Sample statement file not found")
def test_convert_statement_to_portfolio():
    """Verify converting parsed statement into valid PortfolioRequest."""
    statement = parse_excel_statement(SAMPLE_FILE)
    portfolio, report = convert_statement_to_portfolio(statement)

    assert isinstance(portfolio, PortfolioRequest)
    assert report["equities_imported"] == 8
    assert report["funds_imported"] == 5
    assert len(report["unresolved_funds"]) == 0

    # Verify positions
    assert len(portfolio.equity) == 8
    assert len(portfolio.funds) == 5

    # Check equity properties
    bhel = next(e for e in portfolio.equity if e.symbol == "BHEL")
    assert bhel.quantity == 89.0
    assert bhel.avg_cost > 200.0

    # Check mutual fund resolution
    liquid = next(f for f in portfolio.funds if f.units == 74.512)
    assert liquid.scheme_code == 118304
    assert liquid.avg_nav > 1800.0


def test_statement_api_routes():
    """Verify offline statement API endpoints."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # 1. Test listing offline files
    res_list = client.get("/api/portfolio/offline/files")
    assert res_list.status_code == 200
    data = res_list.json()
    assert "files" in data
    assert any(f["name"] == "holdings-OD7237.xlsx" for f in data["files"])

    # 2. Test importing statement
    res_import = client.post("/api/portfolio/offline/import?filename=holdings-OD7237.xlsx")
    assert res_import.status_code == 200
    import_data = res_import.json()
    assert import_data["status"] == "success"
    assert "valuation" in import_data
    assert import_data["report"]["equities_imported"] == 8
    assert import_data["report"]["funds_imported"] == 5

