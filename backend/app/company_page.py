"""Company-page data: financial statements and shareholding from Screener.in.

`fundamentals.py` only keeps the top-ratios block and a few latest values. The
company page needs the full tables (quarterly results, P&L, balance sheet,
cash flow, ratios, shareholding history), so this module parses them
generically: each table becomes ``{"periods": [...], "rows": [{"label",
"values"}]}`` with numbers parsed and blanks as ``None``.

Source: https://www.screener.in/company/<SYMBOL>/consolidated/ (falling back to
the standalone page). Cached 24 hours like the rest of the fundamentals. When
the source is unreachable the result is ``{"available": False, "reason": ...}``;
nothing is ever invented.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from app import symbols as symbol_master
from app.cache import TTLCache, make_key

logger = logging.getLogger(__name__)

_PAGE_CACHE = TTLCache(ttl=86400, max_entries=256)

# Screener section id -> response key.
_FINANCIAL_SECTIONS = {
    "quarters": "quarterly_results",
    "profit-loss": "profit_loss",
    "balance-sheet": "balance_sheet",
    "cash-flow": "cash_flow",
    "ratios": "ratios",
}


def _number(text: str) -> Optional[float]:
    """'1,234' -> 1234.0, '72.30%' -> 72.3, '' / '-' -> None."""
    cleaned = text.replace(",", "").replace("%", "").replace("₹", "").strip()
    if cleaned in ("", "-", "—"):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _clean_label(text: str) -> str:
    # Expandable rows carry a trailing "+" and sometimes non-breaking spaces.
    return re.sub(r"\s*\+\s*$", "", text.replace("\xa0", " ").strip())


def parse_table(table) -> Dict[str, Any]:
    """Turn a Screener data table into periods + labelled numeric rows."""
    rows = table.find_all("tr")
    if not rows:
        return {"periods": [], "rows": []}
    header = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]
    periods = header[1:]
    parsed: List[Dict[str, Any]] = []
    for tr in rows[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if len(cells) < 2 or not cells[0].strip():
            continue
        values = [_number(c) for c in cells[1:]]
        # Pad / trim so every row lines up with the period header.
        values = (values + [None] * len(periods))[: len(periods)]
        parsed.append({"label": _clean_label(cells[0]), "values": values})
    return {"periods": periods, "rows": parsed}


def parse_company_page(html: str) -> Dict[str, Any]:
    """Parse a Screener company page into the sections the company page needs."""
    soup = BeautifulSoup(html, "html.parser")
    out: Dict[str, Any] = {"available": True}

    for section_id, key in _FINANCIAL_SECTIONS.items():
        section = soup.find("section", id=section_id)
        table = section.find("table", class_="data-table") if section else None
        out[key] = parse_table(table) if table is not None else None

    shareholding: Dict[str, Any] = {"quarterly": None, "yearly": None}
    section = soup.find("section", id="shareholding")
    if section is not None:
        for div_id, key in (("quarterly-shp", "quarterly"), ("yearly-shp", "yearly")):
            div = section.find("div", id=div_id)
            table = div.find("table") if div else None
            if table is not None:
                shareholding[key] = parse_table(table)
    out["shareholding"] = shareholding
    return out


def _fetch_html(symbol: str) -> Optional[str]:
    from curl_cffi import requests

    session = requests.Session(impersonate="chrome")
    base = f"https://www.screener.in/company/{symbol}/"
    response = session.get(base + "consolidated/", timeout=15)
    if response.status_code == 404:
        response = session.get(base, timeout=15)
    if response.status_code != 200:
        raise RuntimeError(f"Screener returned HTTP {response.status_code}")
    return response.text


def get_company_page(symbol: str) -> Dict[str, Any]:
    """Cached statements + shareholding for one symbol (never raises)."""
    canonical = symbol_master.canonical(symbol) or symbol.upper()
    cache_key = make_key("company_page", canonical)

    def _load() -> Dict[str, Any]:
        try:
            html = _fetch_html(canonical)
            data = parse_company_page(html or "")
            data["symbol"] = canonical
            data["source"] = "screener"
            return data
        except Exception as exc:  # network, parsing, blocked
            logger.warning("Company page fetch failed for %s: %s", canonical, exc)
            return {"available": False, "symbol": canonical, "reason": str(exc)}

    result = _PAGE_CACHE.get_or_set(cache_key, _load)
    if not result.get("available"):
        # Do not pin a failure for 24 hours.
        _PAGE_CACHE.invalidate(cache_key)
    return result


def get_financials(symbol: str) -> Dict[str, Any]:
    page = get_company_page(symbol)
    if not page.get("available"):
        return page
    sections = {key: page.get(key) for key in _FINANCIAL_SECTIONS.values()}
    if not any(sections.values()):
        return {"available": False, "symbol": page["symbol"], "reason": "No financial statements found for this company."}
    return {"available": True, "symbol": page["symbol"], "source": "screener", "unit": "INR crore", **sections}


def get_shareholding(symbol: str) -> Dict[str, Any]:
    page = get_company_page(symbol)
    if not page.get("available"):
        return page
    sh = page.get("shareholding") or {}
    if not (sh.get("quarterly") or sh.get("yearly")):
        return {"available": False, "symbol": page["symbol"], "reason": "No shareholding data found for this company."}
    return {"available": True, "symbol": page["symbol"], "source": "screener", **sh}
