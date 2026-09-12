"""Broker statement schema definition, parser, and portfolio converter.

Parses offline holdings statements (e.g., Zerodha console Excel exports)
containing Equity, Mutual Funds, and Combined sheets. Extracts statement
metadata (Client ID, As-Of Date), summaries, and position tables, and converts
them cleanly into the application's native PortfolioRequest format.
"""

import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import openpyxl
from pydantic import BaseModel, Field

from app import symbols as symbol_master
from app.mfapi_client import MFApiClient
from app.schemas import EquityHolding, FundHolding, PortfolioRequest

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Broker Statement Schemas (Pydantic models matching file structure)
# ---------------------------------------------------------------------------


class StatementMetadata(BaseModel):
    """Metadata parsed from header rows of the holdings statement."""

    client_id: str = Field(description="Client ID, e.g. OD7237")
    statement_title: str = Field(
        default="", description="Full statement title from file"
    )
    as_of_date: Optional[date] = Field(
        default=None, description="Statement snapshot date"
    )
    file_name: str = Field(default="", description="Source file name")
    sheet_names: List[str] = Field(
        default_factory=list, description="All sheets found in workbook"
    )


class StatementSummary(BaseModel):
    """High-level valuation summary block from statement header."""

    invested_value: float = Field(default=0.0, description="Total invested amount")
    present_value: float = Field(default=0.0, description="Current market valuation")
    unrealized_pnl: float = Field(default=0.0, description="Unrealized absolute profit/loss")
    unrealized_pnl_pct: float = Field(
        default=0.0, description="Unrealized P&L percentage"
    )


class EquityStatementRow(BaseModel):
    """One equity holding row as formatted in the broker statement."""

    symbol: str = Field(description="NSE / BSE symbol, e.g. BAJAJHFL")
    isin: str = Field(description="ISIN security code, e.g. INE377Y01014")
    sector: Optional[str] = Field(default=None, description="Sector classification")
    quantity_available: float = Field(
        default=0.0, description="Free available shares quantity"
    )
    quantity_discrepant: float = Field(
        default=0.0, description="Discrepant shares under corporate action"
    )
    quantity_long_term: float = Field(
        default=0.0, description="Shares eligible for long-term capital gains"
    )
    quantity_pledged_margin: float = Field(
        default=0.0, description="Pledged for trading margin"
    )
    quantity_pledged_loan: float = Field(
        default=0.0, description="Pledged against LAS loan"
    )
    average_price: float = Field(default=0.0, description="Average buy cost per share")
    previous_closing_price: Optional[float] = Field(
        default=None, description="LTP / Previous close price"
    )
    unrealized_pnl: Optional[float] = Field(
        default=None, description="Unrealized P&L from statement"
    )
    unrealized_pnl_pct: Optional[float] = Field(
        default=None, description="Unrealized P&L % from statement"
    )

    @property
    def total_quantity(self) -> float:
        """Total shares owned (available + discrepant + pledged)."""
        return (
            self.quantity_available
            + self.quantity_discrepant
            + self.quantity_pledged_margin
            + self.quantity_pledged_loan
        )


class MutualFundStatementRow(BaseModel):
    """One mutual fund holding row as formatted in the broker statement."""

    symbol: str = Field(description="Mutual fund scheme name, e.g. CANARA ROBECO LIQUID")
    isin: str = Field(description="Mutual fund ISIN, e.g. INF760K01FT8")
    instrument_type: Optional[str] = Field(
        default=None, description="Fund category, e.g. Debt - Liquid, Equity - ELSS"
    )
    quantity_available: float = Field(
        default=0.0, description="Available mutual fund units"
    )
    quantity_discrepant: float = Field(default=0.0, description="Discrepant units")
    quantity_pledged_margin: float = Field(
        default=0.0, description="Units pledged for margin"
    )
    quantity_pledged_loan: float = Field(
        default=0.0, description="Units pledged against loan"
    )
    average_price: float = Field(
        default=0.0, description="Average purchase NAV per unit"
    )
    previous_closing_price: Optional[float] = Field(
        default=None, description="Latest closing NAV per unit"
    )
    unrealized_pnl: Optional[float] = Field(
        default=None, description="Unrealized P&L from statement"
    )
    unrealized_pnl_pct: Optional[float] = Field(
        default=None, description="Unrealized P&L % from statement"
    )

    @property
    def total_units(self) -> float:
        """Total units held across available and pledged."""
        return (
            self.quantity_available
            + self.quantity_discrepant
            + self.quantity_pledged_margin
            + self.quantity_pledged_loan
        )


class BrokerStatement(BaseModel):
    """Complete parsed broker holdings statement file."""

    metadata: StatementMetadata
    equity_summary: Optional[StatementSummary] = None
    mf_summary: Optional[StatementSummary] = None
    combined_summary: Optional[StatementSummary] = None
    equity_holdings: List[EquityStatementRow] = Field(default_factory=list)
    mf_holdings: List[MutualFundStatementRow] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 2. Parsing Functions
# ---------------------------------------------------------------------------


def _clean_str(val: Any) -> str:
    """Normalize cell string value."""
    if val is None:
        return ""
    return str(val).strip()


def _to_float(val: Any, default: float = 0.0) -> float:
    """Safely parse float from string or number."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    text = str(val).strip().replace(",", "").replace("%", "")
    if not text or text == "-":
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _extract_date(text: str) -> Optional[date]:
    """Parse date from statement title string like '...as on 2026-09-07'."""
    match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass
    match_dmy = re.search(r"(\d{2}-\d{2}-\d{4})", text)
    if match_dmy:
        try:
            return datetime.strptime(match_dmy.group(1), "%d-%m-%Y").date()
        except ValueError:
            pass
    return None


def parse_excel_statement(
    file_path_or_bytes: Union[str, Path, bytes],
    file_name: str = "holdings.xlsx",
) -> BrokerStatement:
    """Parse a multi-sheet Zerodha/broker Excel holdings file.

    Handles Equity, Mutual Funds, and Combined sheets, extracting Client ID,
    as-of date, summary totals, and all holding rows into typed models.
    """
    if isinstance(file_path_or_bytes, (str, Path)):
        p = Path(file_path_or_bytes)
        file_name = p.name
        wb = openpyxl.load_workbook(p, data_only=True)
    else:
        import io

        wb = openpyxl.load_workbook(io.BytesIO(file_path_or_bytes), data_only=True)

    metadata = StatementMetadata(
        client_id="",
        statement_title="",
        as_of_date=None,
        file_name=file_name,
        sheet_names=wb.sheetnames,
    )

    equity_summary: Optional[StatementSummary] = None
    mf_summary: Optional[StatementSummary] = None
    combined_summary: Optional[StatementSummary] = None

    equity_holdings: List[EquityStatementRow] = []
    mf_holdings: List[MutualFundStatementRow] = []

    # Iterate sheets
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        lower_name = sheet_name.lower().strip()

        # Step A: Parse header block (Client ID, Title, Summary)
        client_id = ""
        stmt_title = ""
        as_of = None
        invested = 0.0
        present = 0.0
        pnl = 0.0
        pnl_pct = 0.0

        header_row_idx = None
        col_map: Dict[str, int] = {}

        for r in range(1, min(40, ws.max_row + 1)):
            row_vals = [ws.cell(r, c).value for c in range(1, ws.max_column + 1)]
            first_non_empty = [v for v in row_vals if v is not None and str(v).strip()]

            # Detect Client ID
            for idx, val in enumerate(row_vals):
                s = _clean_str(val).lower()
                if "client id" in s:
                    # Next non-empty cell is usually the client ID
                    for next_val in row_vals[idx + 1 :]:
                        clean_next = _clean_str(next_val)
                        if clean_next:
                            client_id = clean_next
                            break

            # Detect statement title
            for val in first_non_empty:
                s = _clean_str(val)
                if "holdings statement as on" in s.lower():
                    stmt_title = s
                    as_of = _extract_date(s)

            # Detect table headers (Row containing 'Symbol' and 'ISIN')
            lower_strs = [_clean_str(v).lower() for v in row_vals]
            if "symbol" in lower_strs and "isin" in lower_strs:
                header_row_idx = r
                for c_idx, h_val in enumerate(row_vals, start=1):
                    clean_h = _clean_str(h_val).lower()
                    if clean_h:
                        col_map[clean_h] = c_idx
                break

            # Detect Summary metrics (only in header summary block before table)
            for idx, val in enumerate(row_vals):
                s = _clean_str(val).lower()
                next_val = row_vals[idx + 1] if idx + 1 < len(row_vals) else None
                if "invested value" in s:
                    invested = _to_float(next_val)
                elif "present value" in s:
                    present = _to_float(next_val)
                elif ("pct" in s or "%" in s) and ("p&l" in s or "pnl" in s or "pl" in s):
                    pnl_pct = _to_float(next_val)
                elif ("p&l" in s or "pnl" in s or "pl" in s) and "unreal" in s:
                    pnl = _to_float(next_val)

        # Save global metadata if not set
        if client_id and not metadata.client_id:
            metadata.client_id = client_id
        if stmt_title and not metadata.statement_title:
            metadata.statement_title = stmt_title
        if as_of and not metadata.as_of_date:
            metadata.as_of_date = as_of

        summary = StatementSummary(
            invested_value=invested,
            present_value=present,
            unrealized_pnl=pnl,
            unrealized_pnl_pct=pnl_pct,
        )

        if "equity" in lower_name and not equity_summary:
            equity_summary = summary
        elif "mutual fund" in lower_name and not mf_summary:
            mf_summary = summary
        elif "combined" in lower_name and not combined_summary:
            combined_summary = summary

        # Step B: Parse data rows
        if header_row_idx is None:
            continue

        sym_col = col_map.get("symbol")
        isin_col = col_map.get("isin")
        sector_col = col_map.get("sector")
        type_col = col_map.get("instrument type")
        qty_avail_col = col_map.get("quantity available")
        qty_disc_col = col_map.get("quantity discrepant")
        qty_lt_col = col_map.get("quantity long term")
        qty_pm_col = col_map.get("quantity pledged (margin)")
        qty_pl_col = col_map.get("quantity pledged (loan)")
        avg_price_col = col_map.get("average price")
        prev_close_col = col_map.get("previous closing price")
        pnl_col = col_map.get("unrealized p&l")
        pnl_pct_col = col_map.get("unrealized p&l pct.") or col_map.get(
            "unrealize p&l pct."
        )

        if not sym_col or not isin_col:
            continue

        for r in range(header_row_idx + 1, ws.max_row + 1):
            sym_raw = _clean_str(ws.cell(r, sym_col).value)
            isin_raw = _clean_str(ws.cell(r, isin_col).value).upper()

            if not sym_raw or not isin_raw or sym_raw.lower() in ("total", "summary"):
                continue

            # Determine if this row is Mutual Fund or Equity
            # Criteria: ISIN starts with 'INF' OR instrument_type is non-empty and != '-' OR sheet is 'Mutual Funds'
            is_mf = (
                isin_raw.startswith("INF")
                or "mutual fund" in lower_name
                or (type_col and _clean_str(ws.cell(r, type_col).value) not in ("", "-"))
            )

            if is_mf:
                inst_type = (
                    _clean_str(ws.cell(r, type_col).value) if type_col else None
                )
                if inst_type == "-":
                    inst_type = None

                mf_row = MutualFundStatementRow(
                    symbol=sym_raw,
                    isin=isin_raw,
                    instrument_type=inst_type,
                    quantity_available=_to_float(
                        ws.cell(r, qty_avail_col).value if qty_avail_col else 0
                    ),
                    quantity_discrepant=_to_float(
                        ws.cell(r, qty_disc_col).value if qty_disc_col else 0
                    ),
                    quantity_pledged_margin=_to_float(
                        ws.cell(r, qty_pm_col).value if qty_pm_col else 0
                    ),
                    quantity_pledged_loan=_to_float(
                        ws.cell(r, qty_pl_col).value if qty_pl_col else 0
                    ),
                    average_price=_to_float(
                        ws.cell(r, avg_price_col).value if avg_price_col else 0
                    ),
                    previous_closing_price=(
                        _to_float(ws.cell(r, prev_close_col).value)
                        if prev_close_col
                        else None
                    ),
                    unrealized_pnl=(
                        _to_float(ws.cell(r, pnl_col).value) if pnl_col else None
                    ),
                    unrealized_pnl_pct=(
                        _to_float(ws.cell(r, pnl_pct_col).value)
                        if pnl_pct_col
                        else None
                    ),
                )
                # Avoid duplicates if Combined sheet is also processed
                if not any(m.isin == mf_row.isin for m in mf_holdings):
                    mf_holdings.append(mf_row)
            else:
                sector = (
                    _clean_str(ws.cell(r, sector_col).value) if sector_col else None
                )
                if sector == "-":
                    sector = None

                eq_row = EquityStatementRow(
                    symbol=sym_raw,
                    isin=isin_raw,
                    sector=sector,
                    quantity_available=_to_float(
                        ws.cell(r, qty_avail_col).value if qty_avail_col else 0
                    ),
                    quantity_discrepant=_to_float(
                        ws.cell(r, qty_disc_col).value if qty_disc_col else 0
                    ),
                    quantity_long_term=_to_float(
                        ws.cell(r, qty_lt_col).value if qty_lt_col else 0
                    ),
                    quantity_pledged_margin=_to_float(
                        ws.cell(r, qty_pm_col).value if qty_pm_col else 0
                    ),
                    quantity_pledged_loan=_to_float(
                        ws.cell(r, qty_pl_col).value if qty_pl_col else 0
                    ),
                    average_price=_to_float(
                        ws.cell(r, avg_price_col).value if avg_price_col else 0
                    ),
                    previous_closing_price=(
                        _to_float(ws.cell(r, prev_close_col).value)
                        if prev_close_col
                        else None
                    ),
                    unrealized_pnl=(
                        _to_float(ws.cell(r, pnl_col).value) if pnl_col else None
                    ),
                    unrealized_pnl_pct=(
                        _to_float(ws.cell(r, pnl_pct_col).value)
                        if pnl_pct_col
                        else None
                    ),
                )
                if not any(e.isin == eq_row.isin for e in equity_holdings):
                    equity_holdings.append(eq_row)

    return BrokerStatement(
        metadata=metadata,
        equity_summary=equity_summary,
        mf_summary=mf_summary,
        combined_summary=combined_summary,
        equity_holdings=equity_holdings,
        mf_holdings=mf_holdings,
    )


# ---------------------------------------------------------------------------
# 3. Conversion to App Native PortfolioRequest
# ---------------------------------------------------------------------------


def convert_statement_to_portfolio(
    statement: BrokerStatement,
    mf_client: Optional[MFApiClient] = None,
) -> Tuple[PortfolioRequest, Dict[str, Any]]:
    """Transform a BrokerStatement into the app's native PortfolioRequest.

    - Resolves equity symbols and ISINs with the symbol master.
    - Resolves mutual fund ISINs to AMFI scheme codes via AMFI / mfapi.in.
    - Preserves sovereign gold bonds and non-standard tickers.
    - Returns (PortfolioRequest, diagnostic_report).
    """
    if mf_client is None:
        mf_client = MFApiClient()

    mf_client._ensure_amfi_master()

    report: Dict[str, Any] = {
        "client_id": statement.metadata.client_id,
        "as_of_date": (
            statement.metadata.as_of_date.isoformat()
            if statement.metadata.as_of_date
            else None
        ),
        "equities_parsed": len(statement.equity_holdings),
        "equities_imported": 0,
        "funds_parsed": len(statement.mf_holdings),
        "funds_imported": 0,
        "unresolved_funds": [],
    }

    equity_list: List[EquityHolding] = []
    fund_list: List[FundHolding] = []

    # 1. Map Equities
    for eq_row in statement.equity_holdings:
        qty = eq_row.total_quantity
        if qty <= 0:
            continue

        # Look up canonical symbol from symbol master
        rec = symbol_master.lookup(eq_row.symbol) or symbol_master.lookup(eq_row.isin)
        canonical_symbol = rec.symbol if rec else eq_row.symbol.strip().upper()
        sector_val = rec.sector if (rec and rec.sector) else eq_row.sector

        # SGB / Sovereign Gold Bond check
        if not sector_val and "SGB" in canonical_symbol:
            sector_val = "Commodities / Sovereign Gold Bond"

        holding = EquityHolding(
            symbol=canonical_symbol,
            quantity=qty,
            avg_cost=max(eq_row.average_price, 0.01),
            buy_date=statement.metadata.as_of_date,
            ltp=eq_row.previous_closing_price,
            isin=eq_row.isin,
            sector=sector_val,
            source="manual",
        )
        equity_list.append(holding)

    report["equities_imported"] = len(equity_list)

    # 2. Map Mutual Funds
    for mf_row in statement.mf_holdings:
        units = mf_row.total_units
        if units <= 0:
            continue

        # Lookup AMFI scheme code by ISIN
        entry = mf_client._amfi_by_isin.get(mf_row.isin.upper())
        scheme_code = entry.get("scheme_code") if entry else None
        scheme_name = entry.get("scheme_name") if entry else mf_row.symbol
        latest_nav = entry.get("nav") if entry else mf_row.previous_closing_price

        if scheme_code is None:
            # Fallback search by fund name in amfi by_code
            for sc, edata in mf_client._amfi_by_code.items():
                if mf_row.symbol.lower() in edata.get("scheme_name", "").lower():
                    scheme_code = sc
                    scheme_name = edata.get("scheme_name", scheme_name)
                    latest_nav = edata.get("nav", latest_nav)
                    break

        if scheme_code is None:
            # Generate deterministic fallback scheme code from ISIN digits or hash
            # so the fund is not dropped
            clean_digits = "".join(c for c in mf_row.isin if c.isdigit())
            scheme_code = int(clean_digits[-6:]) if len(clean_digits) >= 5 else 999999
            report["unresolved_funds"].append(
                {"symbol": mf_row.symbol, "isin": mf_row.isin, "assigned_code": scheme_code}
            )

        fund_holding = FundHolding(
            scheme_code=scheme_code,
            units=units,
            avg_nav=max(mf_row.average_price, 0.01),
            buy_date=statement.metadata.as_of_date,
            scheme_name=scheme_name,
            category=mf_row.instrument_type,
            latest_nav=latest_nav,
        )
        fund_list.append(fund_holding)

    report["funds_imported"] = len(fund_list)

    portfolio_req = PortfolioRequest(
        equity=equity_list,
        funds=fund_list,
        cash=0.0,
    )

    return portfolio_req, report
