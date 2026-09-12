#!/usr/bin/env python3
"""Offline Broker Statement Importer & Schema Pipeline.

Scans the offline directory (e.g. `ignore_offline/`), parses Zerodha/broker Excel
holding statements according to the BrokerStatement schema, resolves equities
and mutual funds with AMFI and the NSE symbol master, generates a valid
PortfolioRequest JSON, and optionally persists holdings to the database.

Usage:
    # Inspect schema and run dry-run valuation:
    python -m scripts.import_offline_holdings

    # Sync holdings directly to PostgreSQL database:
    python -m scripts.import_offline_holdings --sync-db

    # Export to a custom JSON location:
    python -m scripts.import_offline_holdings --to-json path/to/portfolio.json

    # Specify custom directory or single file:
    python -m scripts.import_offline_holdings --file ignore_offline/holdings-OD7237.xlsx
"""

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure 'backend' directory is in Python path
BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app.broker_statement import (
    BrokerStatement,
    convert_statement_to_portfolio,
    parse_excel_statement,
)
from app.mfapi_client import MFApiClient
from app.portfolio import value_portfolio
from app.schemas import PortfolioRequest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("importer")


def format_currency(val: Optional[float]) -> str:
    """Format floating point numbers as currency string."""
    if val is None:
        return "N/A"
    return f"Rs. {val:,.2f}"


def format_pct(val: Optional[float]) -> str:
    """Format percentage with +/- sign."""
    if val is None:
        return "N/A"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.2f}%"


def print_banner(title: str, width: int = 80):
    print("\n" + "=" * width)
    print(f" {title.upper()} ".center(width, "="))
    print("=" * width)


def print_table(headers: List[str], rows: List[List[str]], col_widths: Optional[List[int]] = None):
    """Print formatted ASCII table."""
    if not rows:
        print("  (No rows)")
        return
    if not col_widths:
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, val in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(val)))

    header_line = " | ".join(f"{h:<{col_widths[i]}}" for i, h in enumerate(headers))
    sep_line = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
    print(header_line)
    print(sep_line)
    for row in rows:
        cells = [f"{str(row[i]) if i < len(row) else '':<{col_widths[i]}}" for i in range(len(headers))]
        print(" | ".join(cells))


def run_database_sync(
    portfolio: PortfolioRequest,
    client_id: str,
    as_of: Optional[date] = None,
    account_email: Optional[str] = None,
    account_name: Optional[str] = None,
    valuation: Optional[Dict[str, Any]] = None,
) -> bool:
    """Sync holdings into the PostgreSQL database."""
    try:
        import sqlalchemy
        from sqlalchemy.orm import Session
        from app.db.models import Account, Holding, PortfolioSnapshot
        from app.db import repo
    except ImportError as err:
        logger.error("Could not import database models: %s", err)
        return False

    # Connect to PostgreSQL: check DATABASE_URL or try host fallback
    db_url = os.environ.get("DATABASE_URL")
    if not db_url or "@db:" in db_url or "localhost:5432" in db_url:
        db_url = "postgresql+psycopg://postgres:postgres@127.0.0.1:5434/stockportfolio"
    elif db_url.startswith("postgresql://"):
        db_url = "postgresql+psycopg://" + db_url[len("postgresql://"):]

    logger.info("Connecting to database at %s...", db_url.split("@")[-1])
    try:
        engine = sqlalchemy.create_engine(db_url, connect_args={"connect_timeout": 5})
        with Session(engine) as session:
            # Check or create account
            email = account_email or (f"{client_id.lower()}@stockportfolio.in" if client_id else "offline@stockportfolio.in")
            name = account_name or (f"Account ({client_id})" if client_id else "Broker Offline Portfolio")

            # Lookup account by email or display name
            account = session.query(Account).filter(
                (Account.email == email) | (Account.display_name == name)
            ).first()

            if not account:
                logger.info("Creating new account for %s (%s)...", name, email)
                account, key = repo.create_account(session, email=email, display_name=name)
                print(f"\n[DB] Created new account: ID {account.id} | Access Key: {key}")
            else:
                logger.info("Found existing account: ID %d (%s)", account.id, account.display_name)

            # Sync / replace holdings
            stored_count = repo.replace_holdings(session, account, portfolio)
            logger.info("Stored %d holdings in database for Account ID %d", stored_count, account.id)

            # Save snapshot if valuation provided
            if valuation:
                totals = valuation.get("totals", {})
                as_of_date = as_of or date.today()
                snapshot = session.query(PortfolioSnapshot).filter(
                    PortfolioSnapshot.account_id == account.id,
                    PortfolioSnapshot.as_of == as_of_date,
                ).first()

                if not snapshot:
                    snapshot = PortfolioSnapshot(
                        account_id=account.id,
                        as_of=as_of_date,
                        invested=totals.get("invested", 0.0),
                        current_value=totals.get("current_value", 0.0),
                        pnl=totals.get("pnl", 0.0),
                        holdings_count=stored_count,
                        payload=valuation,
                    )
                    session.add(snapshot)
                else:
                    snapshot.invested = totals.get("invested", 0.0)
                    snapshot.current_value = totals.get("current_value", 0.0)
                    snapshot.pnl = totals.get("pnl", 0.0)
                    snapshot.holdings_count = stored_count
                    snapshot.payload = valuation

            session.commit()
            print(f"[DB] Successfully synchronized {stored_count} positions to PostgreSQL (Account #{account.id})!")
            return True
    except Exception as exc:
        logger.exception("Database sync error: %s", exc)
        return False


def process_file(
    file_path: Path,
    output_json: Optional[Path] = None,
    sync_db: bool = False,
    frontend_sync: bool = False,
    mf_client: Optional[MFApiClient] = None,
) -> bool:
    """Parse, inspect schema, convert, and optionally save a statement file."""
    print_banner(f"Importing Statement File: {file_path.name}")
    print(f"Path: {file_path.resolve()}")

    # 1. Parse Excel into BrokerStatement Schema
    try:
        statement: BrokerStatement = parse_excel_statement(file_path)
    except Exception as exc:
        logger.exception("Failed to parse statement: %s", exc)
        return False

    meta = statement.metadata
    print(f"\nStatement Metadata:")
    print(f"  * Client ID       : {meta.client_id or 'UNKNOWN'}")
    print(f"  * Title           : {meta.statement_title or 'N/A'}")
    print(f"  * As of Date      : {meta.as_of_date or 'N/A'}")
    print(f"  * Sheets Detected : {', '.join(meta.sheet_names)}")

    # 2. Print Statement Summary
    summary = statement.combined_summary or statement.equity_summary
    if summary:
        print(f"\nStatement Header Summary:")
        print(f"  * Invested Value  : {format_currency(summary.invested_value)}")
        print(f"  * Present Value   : {format_currency(summary.present_value)}")
        print(f"  * Unrealized P&L  : {format_currency(summary.unrealized_pnl)} ({format_pct(summary.unrealized_pnl_pct)})")

    # 3. Equities Table
    print_banner(f"Equity Positions ({len(statement.equity_holdings)} Holdings)")
    eq_rows = []
    for h in statement.equity_holdings:
        eq_rows.append([
            h.symbol,
            h.isin,
            (h.sector or "-")[:20],
            f"{h.total_quantity:.1f}",
            format_currency(h.average_price),
            format_currency(h.previous_closing_price),
            format_currency(h.unrealized_pnl),
            format_pct(h.unrealized_pnl_pct),
        ])
    print_table(
        ["Symbol", "ISIN", "Sector", "Qty", "Avg Buy", "LTP", "P&L", "P&L %"],
        eq_rows,
    )

    # 4. Mutual Funds Table
    print_banner(f"Mutual Fund Positions ({len(statement.mf_holdings)} Funds)")
    mf_rows = []
    for m in statement.mf_holdings:
        mf_rows.append([
            m.symbol[:32],
            m.isin,
            (m.instrument_type or "-")[:22],
            f"{m.total_units:.3f}",
            format_currency(m.average_price),
            format_currency(m.previous_closing_price),
            format_currency(m.unrealized_pnl),
            format_pct(m.unrealized_pnl_pct),
        ])
    print_table(
        ["Scheme Name", "ISIN", "Category", "Units", "Avg NAV", "Closing NAV", "P&L", "P&L %"],
        mf_rows,
    )

    # 5. Convert to Native PortfolioRequest Schema
    print_banner("Converting to Native PortfolioRequest Schema")
    portfolio_req, report = convert_statement_to_portfolio(statement, mf_client=mf_client)
    print(f"Conversion Report:")
    print(f"  * Equities Converted  : {report['equities_imported']} / {report['equities_parsed']}")
    print(f"  * Funds Converted     : {report['funds_imported']} / {report['funds_parsed']}")
    if report["unresolved_funds"]:
        print(f"  [WARN] Unresolved Funds: {report['unresolved_funds']}")
    else:
        print(f"  [OK] 100% of mutual funds successfully mapped to AMFI scheme codes!")

    # 6. Real-Time Portfolio Valuation
    print_banner("Real-Time Application Valuation & Analytics")
    try:
        val = value_portfolio(portfolio_req)
        totals = val.get("totals", {})
        print(f"Live Portfolio Analytics:")
        print(f"  * Total Invested       : {format_currency(totals.get('invested'))}")
        print(f"  * Current Portfolio NAV: {format_currency(totals.get('current_value'))}")
        print(f"  * Total Unrealized P&L : {format_currency(totals.get('pnl'))} ({format_pct(totals.get('pnl_pct'))})")
        print(f"  * Total Positions      : {totals.get('holdings')} (Priced: {totals.get('priced')}, Unpriced: {totals.get('unpriced')})")
    except Exception as exc:
        logger.warning("Could not calculate live valuation: %s", exc)
        val = None

    # 7. Write to JSON
    json_data = portfolio_req.model_dump(mode="json")
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(json_data, indent=2), encoding="utf-8")
        print(f"\n[OK] Exported PortfolioRequest JSON to: {output_json.resolve()}")

    if frontend_sync:
        frontend_target = REPO_ROOT / "frontend" / "public" / "imported_portfolio.json"
        try:
            frontend_target.parent.mkdir(parents=True, exist_ok=True)
            frontend_target.write_text(json.dumps(json_data, indent=2), encoding="utf-8")
            print(f"[OK] Synced directly to frontend: {frontend_target.resolve()}")
        except Exception as err:
            logger.warning("Could not sync to frontend: %s", err)

    # 8. Database Sync
    if sync_db:
        print_banner("Database Synchronization")
        run_database_sync(
            portfolio=portfolio_req,
            client_id=meta.client_id or "OFFLINE_CLIENT",
            as_of=meta.as_of_date,
            valuation=val,
        )

    print("\n" + "=" * 80)
    print(" IMPORT COMPLETED SUCCESSFULLY ".center(80, " "))
    print("=" * 80 + "\n")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Import offline broker holdings statements into StockPortfolio.in schema."
    )
    parser.add_argument(
        "--dir",
        "-d",
        type=Path,
        default=REPO_ROOT / "ignore_offline",
        help="Directory containing holdings statements (default: ignore_offline/)",
    )
    parser.add_argument(
        "--file",
        "-f",
        type=Path,
        default=None,
        help="Specific holdings file to import (e.g. ignore_offline/holdings-OD7237.xlsx)",
    )
    parser.add_argument(
        "--to-json",
        "-o",
        type=Path,
        default=None,
        help="Output path for PortfolioRequest JSON (default: <dir>/imported_portfolio.json)",
    )
    parser.add_argument(
        "--sync-db",
        action="store_true",
        help="Persist holdings and valuation snapshot directly to PostgreSQL database",
    )
    parser.add_argument(
        "--frontend-sync",
        action="store_true",
        default=True,
        help="Copy exported JSON into frontend/public/ for browser usage (default: True)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate without saving to disk or database",
    )

    args = parser.parse_args()

    # Pre-warm AMFI client once
    logger.info("Initializing AMFI Mutual Funds registry...")
    mf_client = MFApiClient()
    mf_client._ensure_amfi_master()

    target_files: List[Path] = []
    if args.file:
        if not args.file.exists():
            logger.error("Specified file not found: %s", args.file)
            sys.exit(1)
        target_files.append(args.file)
    else:
        search_dir = args.dir
        if not search_dir.exists():
            logger.error("Directory not found: %s", search_dir)
            sys.exit(1)
        # Search for .xlsx and .xls
        target_files = sorted(
            list(search_dir.glob("*.xlsx")) + list(search_dir.glob("*.xls"))
        )

    if not target_files:
        logger.warning("No Excel statements found in %s", args.dir)
        sys.exit(0)

    logger.info("Found %d statement file(s) to process.", len(target_files))

    for file_path in target_files:
        out_json = None
        if not args.dry_run:
            out_json = (
                args.to_json
                if args.to_json
                else file_path.parent / "imported_portfolio.json"
            )

        success = process_file(
            file_path=file_path,
            output_json=out_json,
            sync_db=args.sync_db,
            frontend_sync=(args.frontend_sync and not args.dry_run),
            mf_client=mf_client,
        )
        if not success:
            logger.error("Import failed for %s", file_path.name)


if __name__ == "__main__":
    main()
