"""Rebuild app/data/nse_symbols.json from upstream masters.

Run manually when the universe drifts — new listings, index reconstitution
(NSE rebalances in March and September), or F&O inclusions:

    python -m scripts.refresh_symbols

Four sources are joined on the NSE trading symbol:

  * Fyers NSE_CM.csv  — the authoritative Fyers ticker, ISIN, lot and tick size.
    Used as the spine because a symbol Fyers cannot quote is useless to us.
  * Fyers NSE_FO.csv  — which names have derivatives, and their F&O lot size
    (which differs from the cash lot size and is what Phase 7 needs).
  * NSE EQUITY_L.csv  — proper company names and the listing date.
  * NSE index lists   — sector ("Industry"), index membership, and the cap
    bucket inferred from which cap index a name sits in.

The output is checked into git rather than fetched at runtime: it changes a few
times a year, and a cold Render container should not depend on nseindia.com
being reachable to answer its first request.
"""

import csv
import io
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from curl_cffi import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("refresh_symbols")

OUT_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "nse_symbols.json"

FYERS_CM = "https://public.fyers.in/sym_details/NSE_CM.csv"
FYERS_FO = "https://public.fyers.in/sym_details/NSE_FO.csv"
NSE_EQUITY_LIST = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"

# Membership drives both the sector label and the cap bucket. Order matters:
# a name in several lists takes the cap of the first one that claims it.
INDEX_LISTS = {
    "NIFTY50": "ind_nifty50list.csv",
    "NIFTYNEXT50": "ind_niftynext50list.csv",
    "NIFTY100": "ind_nifty100list.csv",
    "NIFTY200": "ind_nifty200list.csv",
    "NIFTY500": "ind_nifty500list.csv",
    # Total Market (750) and Microcap 250 exist mainly to widen sector coverage:
    # Industry labels only ship with these constituent files, so a name in no
    # index has no sector, and the fundamental score is graded within sector.
    "NIFTYTOTALMARKET": "ind_niftytotalmarket_list.csv",
    "NIFTYMICROCAP250": "ind_niftymicrocap250_list.csv",
    "NIFTYMIDCAP150": "ind_niftymidcap150list.csv",
    "NIFTYSMALLCAP250": "ind_niftysmallcap250list.csv",
    "NIFTYBANK": "ind_niftybanklist.csv",
    "NIFTYIT": "ind_niftyitlist.csv",
    "NIFTYAUTO": "ind_niftyautolist.csv",
    "NIFTYPHARMA": "ind_niftypharmalist.csv",
    "NIFTYFMCG": "ind_niftyfmcglist.csv",
    "NIFTYMETAL": "ind_niftymetallist.csv",
    "NIFTYENERGY": "ind_niftyenergylist.csv",
    "NIFTYREALTY": "ind_niftyrealtylist.csv",
    "NIFTYPSUBANK": "ind_niftypsubanklist.csv",
    "NIFTYFINSERVICE": "ind_niftyfinancelist.csv",
}
INDEX_BASE = "https://nsearchives.nseindia.com/content/indices/"

# SEBI defines the buckets by market-cap rank (1-100 large, 101-250 mid,
# 251+ small). These indices are built on exactly that ranking, so membership
# is a faithful proxy and avoids needing a market-cap feed.
CAP_FROM_INDEX = [
    ("NIFTY100", "large"),
    ("NIFTYMIDCAP150", "mid"),
    ("NIFTYSMALLCAP250", "small"),
    ("NIFTYMICROCAP250", "micro"),
]

# Benchmarks the analysis layer needs by name. Fyers exposes index history
# under these tickers; the values are verified against NSE_CM at build time.
BENCHMARK_INDICES = {
    "NIFTY50": "NSE:NIFTY50-INDEX",
    "NIFTY100": "NSE:NIFTY100-INDEX",
    "NIFTY200": "NSE:NIFTY200-INDEX",
    "NIFTY500": "NSE:NIFTY500-INDEX",
    "NIFTYBANK": "NSE:NIFTYBANK-INDEX",
    "NIFTYMIDCAP100": "NSE:NIFTYMIDCAP100-INDEX",
    "NIFTYSMLCAP100": "NSE:NIFTYSMLCAP100-INDEX",
    "NIFTYIT": "NSE:NIFTYIT-INDEX",
    "INDIAVIX": "NSE:INDIAVIX-INDEX",
}

# Series that represent ordinary tradeable equity. Everything else in the file
# (SG sovereign gold, MF units, N0/N1 debt, GS gilts) is not a stock.
EQUITY_SERIES = {"EQ", "BE"}


def fetch(url: str, timeout: int = 90) -> str:
    """GET with browser impersonation — nseindia.com blocks plain clients."""
    logger.info("fetching %s", url)
    response = requests.get(url, impersonate="chrome", timeout=timeout)
    if response.status_code != 200:
        raise RuntimeError(f"{url} returned HTTP {response.status_code}")
    return response.text


def _num(value: str, cast, default):
    try:
        return cast(value)
    except (TypeError, ValueError):
        return default


def load_fyers_cash() -> tuple[Dict[str, dict], Dict[str, dict]]:
    """Parse NSE_CM.csv into equity records and index tickers.

    The file has no header. Columns established by inspection:
      0 fytoken | 1 description | 3 lot | 4 tick | 5 ISIN | 9 fyers ticker
      12 exchange token | 13 trading symbol | 16 option type ("XX" for cash)
    """
    rows = list(csv.reader(io.StringIO(fetch(FYERS_CM))))
    equities: Dict[str, dict] = {}
    indices: Dict[str, dict] = {}

    for row in rows:
        if len(row) < 14:
            continue
        ticker = row[9]
        symbol = row[13].strip()
        if not ticker or not symbol:
            continue

        if ticker.endswith("-INDEX"):
            # Key off the ticker, not column 13: for indices that column holds
            # the derivatives alias ("NIFTY", "BANKNIFTY"), which does not match
            # the index name anywhere else. The alias is kept because the F&O
            # chain is looked up by it.
            name = ticker.removeprefix("NSE:").removesuffix("-INDEX")
            indices[name] = {"fyers": ticker, "fo_alias": symbol}
            continue

        series = ticker.rsplit("-", 1)[-1]
        if series not in EQUITY_SERIES:
            continue
        # A symbol can list as both EQ and BE; EQ is the normal segment, so it
        # wins and BE only fills in for names that trade nowhere else.
        if symbol in equities and equities[symbol]["series"] == "EQ":
            continue

        equities[symbol] = {
            "symbol": symbol,
            "name": row[1].strip(),
            "isin": row[5].strip(),
            "fyers": ticker,
            "series": series,
            "lot_size": _num(row[3], int, 1),
            "tick_size": _num(row[4], float, 0.05),
            "token": _num(row[12], int, None),
        }

    logger.info("fyers cash: %d equities, %d indices", len(equities), len(indices))
    return equities, indices


def load_fno_underlyings() -> Dict[str, int]:
    """Map underlying symbol -> F&O lot size from NSE_FO.csv.

    The derivatives lot size is not the cash lot size, and it is what sizes a
    hedge in Phase 7, so it is carried separately.
    """
    try:
        rows = list(csv.reader(io.StringIO(fetch(FYERS_FO))))
    except Exception as exc:
        logger.warning("F&O master unavailable (%s); marking nothing as F&O", exc)
        return {}

    lots: Dict[str, int] = {}
    for row in rows:
        if len(row) < 14:
            continue
        underlying = row[13].strip()
        lot = _num(row[3], int, 0)
        if underlying and lot > 0:
            # Same underlying appears once per strike and expiry; the lot is
            # identical across them, so first write wins.
            lots.setdefault(underlying, lot)
    logger.info("f&o underlyings: %d", len(lots))
    return lots


def load_nse_names() -> Dict[str, dict]:
    """Company names and listing dates from the NSE equity master."""
    text = fetch(NSE_EQUITY_LIST)
    out: Dict[str, dict] = {}
    for row in csv.DictReader(io.StringIO(text)):
        # This file's headers carry leading spaces (" SERIES", " ISIN NUMBER").
        clean = {k.strip(): (v or "").strip() for k, v in row.items() if k}
        symbol = clean.get("SYMBOL")
        if not symbol:
            continue
        out[symbol] = {
            "name": clean.get("NAME OF COMPANY", ""),
            "listing_date": clean.get("DATE OF LISTING", ""),
            "isin": clean.get("ISIN NUMBER", ""),
        }
    logger.info("nse equity master: %d rows", len(out))
    return out


def load_index_membership() -> tuple[Dict[str, list], Dict[str, str]]:
    """Index membership per symbol, plus the sector label NSE assigns."""
    membership: Dict[str, list] = {}
    sectors: Dict[str, str] = {}

    for index_name, filename in INDEX_LISTS.items():
        try:
            text = fetch(INDEX_BASE + filename, timeout=60)
        except Exception as exc:
            logger.warning("skipping %s: %s", index_name, exc)
            continue
        count = 0
        for row in csv.DictReader(io.StringIO(text)):
            clean = {k.strip(): (v or "").strip() for k, v in row.items() if k}
            symbol = clean.get("Symbol")
            if not symbol:
                continue
            membership.setdefault(symbol, []).append(index_name)
            industry = clean.get("Industry")
            # Broad indices carry the canonical sector; sectoral indices would
            # only ever restate it, so the first (broadest) label sticks.
            if industry and symbol not in sectors:
                sectors[symbol] = industry
            count += 1
        logger.info("  %-18s %d constituents", index_name, count)

    return membership, sectors


def cap_bucket(indices: list) -> Optional[str]:
    for index_name, bucket in CAP_FROM_INDEX:
        if index_name in indices:
            return bucket
    return None


def build() -> dict:
    equities, fyers_indices = load_fyers_cash()
    fno_lots = load_fno_underlyings()
    nse_names = load_nse_names()
    membership, sectors = load_index_membership()

    for symbol, record in equities.items():
        nse = nse_names.get(symbol, {})
        # NSE's "Reliance Industries Limited" beats Fyers' shouty
        # "RELIANCE INDUSTRIES LTD" for anything user-facing.
        if nse.get("name"):
            record["name"] = nse["name"]
        record["listing_date"] = nse.get("listing_date", "")
        if not record["isin"]:
            record["isin"] = nse.get("isin", "")

        indices = membership.get(symbol, [])
        record["indices"] = indices
        record["sector"] = sectors.get(symbol)
        record["cap"] = cap_bucket(indices)
        record["fno"] = symbol in fno_lots
        record["fno_lot_size"] = fno_lots.get(symbol)

    benchmarks = {}
    for name, ticker in BENCHMARK_INDICES.items():
        if name in fyers_indices:
            benchmarks[name] = fyers_indices[name]["fyers"]
        else:
            # Keep the hardcoded guess but say so, rather than silently
            # shipping a ticker Fyers will reject at query time.
            logger.warning("benchmark %s not found in Fyers master; keeping %s", name, ticker)
            benchmarks[name] = ticker

    with_sector = sum(1 for r in equities.values() if r["sector"])
    logger.info(
        "built %d equities (%d with sector, %d F&O), %d indices",
        len(equities), with_sector, len(fno_lots), len(fyers_indices),
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "counts": {
            "equities": len(equities),
            "with_sector": with_sector,
            "fno": sum(1 for r in equities.values() if r["fno"]),
            "indices": len(fyers_indices),
        },
        "benchmarks": benchmarks,
        "indices": fyers_indices,
        "equities": dict(sorted(equities.items())),
    }


def main() -> int:
    try:
        data = build()
    except Exception as exc:
        logger.error("refresh failed: %s", exc)
        return 1

    if data["counts"]["equities"] < 1000:
        logger.error(
            "only %d equities parsed — refusing to overwrite a good file",
            data["counts"]["equities"],
        )
        return 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    logger.info("wrote %s (%.1f KB)", OUT_PATH, OUT_PATH.stat().st_size / 1024)
    return 0


if __name__ == "__main__":
    sys.exit(main())
