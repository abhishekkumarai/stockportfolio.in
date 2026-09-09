"""Fundamental analysis scraper, forensic red-flag analyzer, and scoring engine.

Extracts financial statements and ratios from Screener.in using curl_cffi with
Chrome TLS impersonation (cached 24h) and falls back to yfinance .info.
Computes Piotroski F-Score (0-9), Altman Z-Score, and blended fundamental ScoreCard.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup


from app import scoring
from app import symbols as symbol_master
from app.cache import TTLCache, make_key

logger = logging.getLogger(__name__)

# Fundamentals change quarterly, so a 24-hour cache is optimal.
_FUNDAMENTALS_CACHE = TTLCache(ttl=86400, max_entries=1024)


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val) if scoring.is_usable(val) else None
    try:
        cleaned = str(val).replace(",", "").replace("%", "").replace("Cr.", "").replace("₹", "").strip()
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def fetch_screener_fundamentals(symbol: str) -> Dict[str, Any]:
    """Scrape company financial ratios and quarters from Screener.in."""
    canonical = symbol_master.canonical(symbol) or symbol.upper()
    url = f"https://www.screener.in/company/{canonical}/consolidated/"

    try:
        from curl_cffi import requests
        session = requests.Session(impersonate="chrome")
        response = session.get(url, timeout=12)

        # Fallback to standalone page if consolidated 404s
        if response.status_code == 404:
            url = f"https://www.screener.in/company/{canonical}/"
            response = session.get(url, timeout=12)

        if response.status_code != 200:
            return {"available": False, "reason": f"Screener returned HTTP {response.status_code}"}

        soup = BeautifulSoup(response.text, "html.parser")
        ratios: Dict[str, Any] = {"available": True, "symbol": canonical, "source": "screener"}

        # 1. Extract Top Ratios Block
        top_ratios = soup.find("ul", id="top-ratios")
        if top_ratios:
            for item in top_ratios.find_all("li"):
                name_span = item.find("span", class_="name")
                val_span = item.find("span", class_="value") or item.find("span", class_="number")
                if name_span and val_span:
                    key = name_span.text.strip().lower()
                    val = _safe_float(val_span.text.strip())
                    if "market cap" in key:
                        ratios["market_cap_cr"] = val
                    elif "current price" in key:
                        ratios["current_price"] = val
                    elif "stock p/e" in key or "p/e" in key:
                        ratios["pe_ratio"] = val
                    elif "book value" in key:
                        ratios["book_value"] = val
                    elif "dividend yield" in key:
                        ratios["dividend_yield_pct"] = val
                    elif "roce" in key:
                        ratios["roce_pct"] = val
                    elif "roe" in key:
                        ratios["roe_pct"] = val
                    elif "face value" in key:
                        ratios["face_value"] = val

        # 2. Extract Additional Ratios from Data Tables (Profit & Loss / Balance Sheet)
        # Search for Debt to Equity, Pledged percentage, Interest Coverage
        for row in soup.find_all("tr"):
            text = row.text.lower()
            cols = [td.text.strip() for td in row.find_all("td")]
            if not cols or len(cols) < 2:
                continue

            row_name = cols[0].lower()
            latest_val = _safe_float(cols[-1])

            if "pledged" in row_name and "pledged_pct" not in ratios:
                ratios["pledged_pct"] = latest_val or 0.0
            elif "borrowings" in row_name and "borrowings_cr" not in ratios:
                ratios["borrowings_cr"] = latest_val
            elif "sales" in row_name and "latest_sales_cr" not in ratios:
                ratios["latest_sales_cr"] = latest_val
            elif "net profit" in row_name and "latest_pat_cr" not in ratios:
                ratios["latest_pat_cr"] = latest_val

        # Defaults and sanitization
        ratios["pledged_pct"] = ratios.get("pledged_pct", 0.0)
        return ratios

    except Exception as exc:
        logger.warning("Screener scraping failed for %s: %s", canonical, exc)
        return {"available": False, "reason": str(exc)}


def fetch_yfinance_fundamentals(symbol: str) -> Dict[str, Any]:
    """Fallback fundamental data from yfinance."""
    yf_symbol = symbol_master.to_yfinance(symbol) or f"{symbol}.NS"
    try:
        import yfinance as yf
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info or {}

        if not info or not info.get("regularMarketPrice"):
            return {"available": False, "reason": "No yfinance data"}

        pe = info.get("trailingPE") or info.get("forwardPE")
        pb = info.get("priceToBook")
        roe = (info.get("returnOnEquity") * 100.0) if info.get("returnOnEquity") else None
        debt_to_equity = (info.get("debtToEquity") / 100.0) if info.get("debtToEquity") else None
        peg = info.get("pegRatio")
        revenue_growth = (info.get("revenueGrowth") * 100.0) if info.get("revenueGrowth") else None
        profit_growth = (info.get("earningsGrowth") * 100.0) if info.get("earningsGrowth") else None

        return {
            "available": True,
            "symbol": symbol,
            "source": "yfinance",
            "current_price": info.get("regularMarketPrice") or info.get("currentPrice"),
            "market_cap_cr": round(info.get("marketCap", 0) / 1e7, 2) if info.get("marketCap") else None,
            "pe_ratio": round(pe, 2) if pe else None,
            "pb_ratio": round(pb, 2) if pb else None,
            "roe_pct": round(roe, 2) if roe else None,
            "debt_to_equity": round(debt_to_equity, 2) if debt_to_equity else None,
            "peg_ratio": round(peg, 2) if peg else None,
            "sales_growth_pct": round(revenue_growth, 2) if revenue_growth else None,
            "pat_growth_pct": round(profit_growth, 2) if profit_growth else None,
            "pledged_pct": 0.0,
        }
    except Exception as exc:
        logger.warning("yfinance fundamental fetch failed for %s: %s", yf_symbol, exc)
        return {"available": False, "reason": str(exc)}


def get_fundamentals(symbol: str) -> Dict[str, Any]:
    """Retrieve fundamentals with cache and multi-source fallback."""
    canonical = symbol_master.canonical(symbol) or symbol.upper()
    cache_key = make_key("fundamentals", canonical)

    def _fetch():
        data = fetch_screener_fundamentals(canonical)
        if not data.get("available"):
            logger.info("Falling back to yfinance fundamentals for %s", canonical)
            data = fetch_yfinance_fundamentals(canonical)
        # Sector and cap come from the symbol master rather than either scraper,
        # so every row is classified the same way. Sector-relative grading and
        # the screener both key off these, and a peer group assembled from two
        # different taxonomies is not a peer group.
        record = symbol_master.lookup(canonical)
        if record is not None:
            data.setdefault("name", record.name)
            data["sector"] = record.sector
            data["cap"] = record.cap
        return data

    return _FUNDAMENTALS_CACHE.get_or_set(cache_key, _fetch)


def calculate_piotroski_f_score(fund: Dict[str, Any]) -> int:
    """Calculates approximate Piotroski F-Score (0-9) from available accounting metrics."""
    score = 0
    # Profitability signals
    if (fund.get("latest_pat_cr") or 0) > 0 or (fund.get("roe_pct") or 0) > 0:
        score += 1  # Positive Net Income
    if (fund.get("roce_pct") or 0) > 12:
        score += 1  # Healthy Return on Capital
    if (fund.get("roe_pct") or 0) > 15:
        score += 1  # High ROE

    # Leverage & Liquidity
    debt_equity = fund.get("debt_to_equity", 0.5)
    if debt_equity is not None and debt_equity < 1.0:
        score += 1  # Low/Moderate Debt
    if fund.get("pledged_pct", 0) <= 5.0:
        score += 1  # Low/No promoter pledging

    # Operating Efficiency & Valuation
    if (fund.get("sales_growth_pct") or 0) > 10:
        score += 1  # Expanding sales
    if (fund.get("pat_growth_pct") or 0) > 12:
        score += 1  # Expanding profits
    if (fund.get("peg_ratio") or 1.5) < 2.0:
        score += 1  # Reasonable PEG
    if (fund.get("pe_ratio") or 25) < 50:
        score += 1  # Not extremely overvalued

    return min(9, max(0, score))


def calculate_altman_z_score(fund: Dict[str, Any]) -> Tuple[float, str]:
    """Computes simplified Altman Z-Score for non-manufacturing/manufacturing firms.
    Returns (score, classification: "Safe" | "Grey" | "Distress").
    """
    roce = fund.get("roce_pct", 15.0) or 15.0
    de = fund.get("debt_to_equity", 0.5) or 0.5
    pledged = fund.get("pledged_pct", 0.0) or 0.0

    # Synthetic Z approximation calibrated to Indian market fundamentals
    z = 1.2 * (roce / 10.0) + 1.4 * (1.0 / (de + 0.1)) - 0.5 * (pledged / 10.0)

    if z >= 2.99:
        classification = "Safe"
    elif z >= 1.81:
        classification = "Grey"
    else:
        classification = "Distress"

    return round(z, 2), classification


def score_fundamentals(fund: Dict[str, Any]) -> scoring.ScoreCard:
    """Evaluates fundamentals across Valuation, Profitability, Growth, and Solvency."""
    if not fund.get("available"):
        return scoring.ScoreCard(name="fundamentals", score=None, coverage=0.0, notes=[fund.get("reason", "No data")])

    signals: List[scoring.Signal] = []

    # 1. Profitability & Capital Efficiency (ROCE / ROE) - Weight: 30%
    roce = fund.get("roce_pct")
    roe = fund.get("roe_pct")
    prof_score = 50.0
    prof_reason = "Moderate capital efficiency"

    if roce and roce >= 20.0 and roe and roe >= 18.0:
        prof_score = 90.0
        prof_reason = f"Excellent capital efficiency: ROCE {roce:.1f}% and ROE {roe:.1f}% (High Moat)"
    elif (roce and roce >= 15.0) or (roe and roe >= 12.0):
        prof_score = 70.0
        prof_reason = f"Healthy returns: ROCE {roce or 0:.1f}%, ROE {roe or 0:.1f}%"
    elif (roce and roce < 10.0) or (roe and roe < 8.0):
        prof_score = 25.0
        prof_reason = f"Sub-par capital efficiency: ROCE {roce or 0:.1f}%, ROE {roe or 0:.1f}%"

    signals.append(
        scoring.Signal(
            key="profitability_roce_roe",
            score=prof_score,
            value={"roce_pct": roce, "roe_pct": roe},
            weight=0.30,
            reason=prof_reason,
        )
    )

    # 2. Valuation (P/E & PEG) - Weight: 30%
    pe = fund.get("pe_ratio")
    peg = fund.get("peg_ratio")
    val_score = 50.0
    val_reason = "Valuation is fair"

    if pe is not None:
        if pe <= 20.0 and (peg is None or peg <= 1.5):
            val_score = 85.0
            val_reason = f"Attractive valuation: P/E at {pe:.1f}x (GARP)"
        elif 20.0 < pe <= 35.0:
            val_score = 65.0
            val_reason = f"Reasonable valuation: P/E at {pe:.1f}x"
        elif 35.0 < pe <= 60.0:
            val_score = 40.0
            val_reason = f"Rich valuation: P/E at {pe:.1f}x (pricing in high growth)"
        elif pe > 60.0:
            val_score = 20.0
            val_reason = f"Extremely expensive: P/E at {pe:.1f}x (elevated multiple contraction risk)"

    signals.append(
        scoring.Signal(
            key="valuation_pe_peg",
            score=val_score,
            value={"pe": pe, "peg": peg},
            weight=0.30,
            reason=val_reason,
        )
    )

    # 3. Solvency & Debt / Promoter Pledging - Weight: 25%
    pledged = fund.get("pledged_pct", 0.0)
    debt_eq = fund.get("debt_to_equity", 0.3)
    solv_score = 50.0
    solv_reason = "Healthy balance sheet"

    if pledged > 20.0:
        solv_score = 15.0
        solv_reason = f"CRITICAL DANGER: Promoter pledging is elevated at {pledged:.1f}%"
    elif debt_eq and debt_eq > 2.0:
        solv_score = 25.0
        solv_reason = f"High leverage: Debt-to-Equity is {debt_eq:.2f}x"
    elif pledged <= 5.0 and (debt_eq is None or debt_eq <= 0.5):
        solv_score = 90.0
        solv_reason = f"Virtually debt-free (D/E: {debt_eq or 0:.2f}x) with zero significant promoter pledging"

    signals.append(
        scoring.Signal(
            key="solvency_and_governance",
            score=solv_score,
            value={"pledged_pct": pledged, "debt_to_equity": debt_eq},
            weight=0.25,
            reason=solv_reason,
        )
    )

    # 4. Forensic Scores (Piotroski F-Score & Altman Z) - Weight: 15%
    f_score = calculate_piotroski_f_score(fund)
    z_score, z_class = calculate_altman_z_score(fund)

    if f_score >= 7 and z_class == "Safe":
        forensic_score = 90.0
        forensic_reason = f"Robust accounting health: Piotroski F-Score {f_score}/9, Altman Z-Score {z_score} (Safe)"
    elif f_score <= 3 or z_class == "Distress":
        forensic_score = 20.0
        forensic_reason = f"DANGER: Weak forensic indicators: Piotroski F-Score {f_score}/9, Altman Z-Score in {z_class} zone"
    else:
        forensic_score = 60.0
        forensic_reason = f"Stable forensic health: Piotroski F-Score {f_score}/9"

    signals.append(
        scoring.Signal(
            key="forensic_health",
            score=forensic_score,
            value={"piotroski_f_score": f_score, "altman_z_score": z_score, "z_class": z_class},
            weight=0.15,
            reason=forensic_reason,
        )
    )

    return scoring.blend("fundamentals", signals, min_coverage=0.6)


# ---- sector-relative grading ---------------------------------------------
# Absolute thresholds are the wrong yardstick for valuation. A 25x P/E is
# expensive for a PSU bank and cheap for a branded-FMCG name, so the block
# above ("P/E <= 20 is attractive") systematically flags whole sectors as
# overvalued and whole others as bargains. Grading against sector peers
# removes that size- and sector-bias; `scoring.percentile_score` refuses to
# rank against fewer than three peers, so a thin sector falls back to the
# absolute bands rather than producing a percentile from noise.

# Metrics graded by peer percentile, and whether more is better.
SECTOR_RELATIVE_METRICS: Dict[str, bool] = {
    "pe_ratio": False,
    "pb_ratio": False,
    "roce_pct": True,
    "roe_pct": True,
    "debt_to_equity": False,
    "sales_growth_pct": True,
    "pat_growth_pct": True,
}

# How many peers to pull. Each miss is a live scrape, so this is a latency
# budget as much as a statistical one; a dozen liquid names in the same sector
# is enough for a stable percentile without a minute-long request.
MAX_SECTOR_PEERS = 12


def sector_peer_fundamentals(
    symbol: str, max_peers: int = MAX_SECTOR_PEERS
) -> List[Dict[str, Any]]:
    """Fundamentals for the peer group a symbol should be graded against.

    Peers are drawn from the same sector, preferring the same cap bucket and
    index membership so a microcap is not ranked against Nifty 50 constituents
    — which would measure size, not quality. Only cached-or-fetchable peers
    that actually returned data are included; the caller sees a smaller
    population rather than one padded with unavailable names.
    """
    record = symbol_master.lookup(symbol)
    if record is None or not record.sector:
        return []

    candidates = [
        peer
        for peer in symbol_master.universe(sector=record.sector)
        if peer.symbol != record.symbol
    ]
    if not candidates:
        return []

    # Same cap first, then index-listed names, then the rest. Sorting rather
    # than filtering keeps the group populated when a sector is thin.
    candidates.sort(
        key=lambda p: (
            0 if p.cap == record.cap else 1,
            0 if p.indices else 1,
            p.symbol,
        )
    )

    peers: List[Dict[str, Any]] = []
    for peer in candidates[:max_peers]:
        data = get_fundamentals(peer.symbol)
        if data.get("available"):
            peers.append(data)
    return peers


def _peer_population(peers: List[Dict[str, Any]], metric: str) -> List[float]:
    return [
        value
        for value in (peer.get(metric) for peer in peers)
        if scoring.is_usable(value)
    ]


def score_sector_relative(
    fund: Dict[str, Any], peers: List[Dict[str, Any]]
) -> scoring.ScoreCard:
    """Grade one company against its sector peer group, metric by metric.

    Returns an unscored card when no metric had a usable peer population, which
    lets `score_fundamentals` fall back to absolute bands instead of pretending
    the comparison happened.
    """
    if not fund.get("available"):
        return scoring.ScoreCard(
            name="sector_relative", score=None, coverage=0.0,
            notes=[fund.get("reason", "No data")],
        )

    sector = fund.get("sector") or "sector"
    signals: List[scoring.Signal] = []

    for metric, higher_is_better in SECTOR_RELATIVE_METRICS.items():
        value = fund.get(metric)
        population = _peer_population(peers, metric)
        percentile = scoring.percentile_score(value, population, higher_is_better)

        label = metric.replace("_pct", "").replace("_", " ").upper()
        if percentile is None:
            reason = (
                f"{label}: no value for this company"
                if not scoring.is_usable(value)
                else f"{label}: only {len(population)} peers with data, too few to rank"
            )
            signals.append(scoring.Signal.missing(f"sector_{metric}", reason))
            continue

        signals.append(
            scoring.Signal(
                key=f"sector_{metric}",
                score=percentile,
                value={"value": value, "peers": len(population)},
                reason=(
                    f"{label} of {value} ranks in the {percentile:.0f}th percentile "
                    f"of {len(population)} {sector} peers"
                ),
            )
        )

    # A third of the metrics is enough to say something useful about relative
    # standing; below that the absolute bands are the more honest answer.
    return scoring.blend("sector_relative", signals, min_coverage=0.33)


def score_fundamentals_relative(symbol: str) -> Tuple[scoring.ScoreCard, Dict[str, Any]]:
    """Fundamental score with sector-relative grading folded in.

    The absolute card still carries three quarters of the weight: sector
    percentiles say who is best *within* a sector, and say nothing about a
    sector that is uniformly leveraged or uniformly overvalued. Both readings
    matter, and this keeps the absolute one dominant.
    """
    fund = get_fundamentals(symbol)
    absolute = score_fundamentals(fund)
    peers = sector_peer_fundamentals(symbol)
    relative = score_sector_relative(fund, peers)

    combined = scoring.combine(
        "fundamentals",
        [(absolute, 0.75), (relative, 0.25)],
        min_coverage=0.4,
    )
    combined.notes.append(f"Sector peer group: {len(peers)} companies.")
    return combined, fund
