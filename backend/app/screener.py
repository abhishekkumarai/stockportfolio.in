"""NSE universe screener — "what should I buy" beside "what do I hold".

Scores the whole eligible universe on the *same* technical and fundamental
model the portfolio uses, so a screener hit and a holding are directly
comparable numbers rather than two unrelated scales. Everything here is
composition: `technicals.score_technicals`, `fundamentals.score_fundamentals`
and `scoring.combine` already exist and are not reimplemented.

Three constraints shape the design:

1. **Network cost dominates.** Scoring 500 names one HTTP call at a time is
   minutes of latency. Prices come from one batched `yf.download` per chunk of
   symbols — one round trip for 50 names instead of 50.

2. **Fundamentals are scrapes, not an API.** Each uncached symbol is a
   Screener.in page fetch. They run on a small thread pool, are bounded by
   `fundamental_limit`, and go only to names that already passed the technical
   filter — grading the fundamentals of a stock in a confirmed downtrend is
   work nobody reads.

3. **A run is cacheable.** The universe does not re-rank between two requests a
   minute apart, and the frontend paginates and re-filters against the same
   scan. Runs are cached whole, keyed on every parameter that changes the
   result.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from app import scoring
from app import symbols as symbol_master
from app.cache import TTLCache, make_key
from app.fundamentals import get_fundamentals, score_fundamentals
from app.technicals import extract_technicals, score_technicals
from app.yf_frames import ticker_frame

logger = logging.getLogger(__name__)

# A scan is expensive and the underlying daily bars change once a day, so an
# hour of staleness costs nothing and saves every repeat request.
_SCREENER_CACHE = TTLCache(ttl=3600, max_entries=64)

# yfinance's batch endpoint degrades past roughly this many tickers per call —
# beyond it partial failures start appearing silently as missing columns.
PRICE_BATCH_SIZE = 50

# Scrapes are IO-bound, so threads help; but Screener.in is someone else's
# server and this is a courtesy limit as much as a performance one.
FUNDAMENTAL_WORKERS = 4

# Scoring needs a 200-day moving average, so a year of bars. Asking for more
# slows the download without changing SMA200 or RSI.
HISTORY_PERIOD = "1y"

# Below this many bars SMA50 is barely defined and SMA200 is not defined at
# all, so the "trend" score would be measuring the padding, not the stock.
MIN_BARS = 60

DEFAULT_INDEX = "NIFTY500"


@dataclass
class ScreenFilters:
    """Universe selectors plus post-scoring filters.

    The score filters run *after* scoring rather than as query predicates
    because the scores are what the user is really filtering on, and every raw
    metric is already in hand by then. All optional; unset means "do not filter
    on this".
    """

    index: Optional[str] = DEFAULT_INDEX
    sector: Optional[str] = None
    cap: Optional[str] = None
    fno_only: bool = False

    min_score: Optional[float] = None
    min_technical_score: Optional[float] = None
    min_fundamental_score: Optional[float] = None
    actions: Optional[Sequence[str]] = None

    rsi_min: Optional[float] = None
    rsi_max: Optional[float] = None
    above_sma200: Optional[bool] = None
    golden_cross: Optional[bool] = None
    min_adx: Optional[float] = None

    min_roce: Optional[float] = None
    min_roe: Optional[float] = None
    max_pe: Optional[float] = None
    max_debt_to_equity: Optional[float] = None
    max_pledged_pct: Optional[float] = None
    min_sales_growth: Optional[float] = None

    def cache_key_parts(self) -> tuple:
        return tuple(
            sorted(
                (key, tuple(value) if isinstance(value, (list, tuple)) else value)
                for key, value in self.__dict__.items()
            )
        )


@dataclass
class ScreenRow:
    """One scored candidate."""

    symbol: str
    name: str
    sector: Optional[str]
    cap: Optional[str]
    price: Optional[float]
    recommendation: scoring.Recommendation
    technicals: Dict[str, Any] = field(default_factory=dict)
    fundamentals: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        payload = self.recommendation.as_dict()
        payload.update(
            {
                "name": self.name,
                "sector": self.sector,
                "cap": self.cap,
                "price": self.price,
                # Flattened for the results table; the full evidence stays
                # under `components` on the recommendation.
                "rsi14": self.technicals.get("rsi14"),
                "adx": self.technicals.get("adx"),
                "above_sma200": self.technicals.get("above_sma200"),
                "golden_cross": self.technicals.get("golden_cross"),
                "pe_ratio": self.fundamentals.get("pe_ratio"),
                "roce_pct": self.fundamentals.get("roce_pct"),
                "roe_pct": self.fundamentals.get("roe_pct"),
                "debt_to_equity": self.fundamentals.get("debt_to_equity"),
                "pledged_pct": self.fundamentals.get("pledged_pct"),
                "sales_growth_pct": self.fundamentals.get("sales_growth_pct"),
            }
        )
        return payload


# ---- price ingestion -----------------------------------------------------


def fetch_price_frames(yf_tickers: List[str]) -> Dict[str, pd.DataFrame]:
    """One year of daily OHLCV per ticker, downloaded in batches.

    Failures are per-ticker and quiet by design: over 500 names a handful are
    always freshly listed, suspended or renamed. Those simply do not appear in
    the result, and the caller reports them as skipped rather than aborting the
    whole scan over one dead ticker.
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance unavailable; screener cannot fetch prices")
        return {}

    frames: Dict[str, pd.DataFrame] = {}
    for start in range(0, len(yf_tickers), PRICE_BATCH_SIZE):
        chunk = yf_tickers[start : start + PRICE_BATCH_SIZE]
        try:
            data = yf.download(
                chunk,
                period=HISTORY_PERIOD,
                interval="1d",
                progress=False,
                auto_adjust=False,
                group_by="ticker",
                threads=True,
            )
        except Exception as exc:
            logger.warning("Price batch %d-%d failed: %s", start, start + len(chunk), exc)
            continue

        if data is None or data.empty:
            continue

        for ticker in chunk:
            frame = ticker_frame(data, ticker)
            if frame is None:
                continue
            frame = frame.dropna(subset=["Close"])
            if len(frame) >= MIN_BARS:
                frames[ticker] = frame

    return frames


# ---- filtering -----------------------------------------------------------


def passes_technical_filters(tech: Dict[str, Any], filters: ScreenFilters) -> bool:
    if filters.rsi_min is not None and (tech.get("rsi14") or 0.0) < filters.rsi_min:
        return False
    if filters.rsi_max is not None and (tech.get("rsi14") or 100.0) > filters.rsi_max:
        return False
    if filters.above_sma200 is not None and bool(tech.get("above_sma200")) != filters.above_sma200:
        return False
    if filters.golden_cross is not None and bool(tech.get("golden_cross")) != filters.golden_cross:
        return False
    if filters.min_adx is not None and (tech.get("adx") or 0.0) < filters.min_adx:
        return False
    return True


def passes_fundamental_filters(fund: Dict[str, Any], filters: ScreenFilters) -> bool:
    """Filter on fundamentals, treating a *missing* metric as a failure.

    That asymmetry is deliberate. "ROCE above 20%" is a claim about the
    company; a name whose ROCE could not be scraped has not made that claim, so
    admitting it would silently widen the filter the user asked for.
    """
    checks = (
        (filters.min_roce, fund.get("roce_pct"), True),
        (filters.min_roe, fund.get("roe_pct"), True),
        (filters.min_sales_growth, fund.get("sales_growth_pct"), True),
        (filters.max_pe, fund.get("pe_ratio"), False),
        (filters.max_debt_to_equity, fund.get("debt_to_equity"), False),
        (filters.max_pledged_pct, fund.get("pledged_pct"), False),
    )
    for bound, value, higher_is_better in checks:
        if bound is None:
            continue
        if not scoring.is_usable(value):
            return False
        if higher_is_better and float(value) < bound:
            return False
        if not higher_is_better and float(value) > bound:
            return False
    return True


def wants_fundamentals(filters: ScreenFilters) -> bool:
    """True when any filter can only be decided with fundamental data."""
    return any(
        value is not None
        for value in (
            filters.min_fundamental_score,
            filters.min_roce,
            filters.min_roe,
            filters.max_pe,
            filters.max_debt_to_equity,
            filters.max_pledged_pct,
            filters.min_sales_growth,
        )
    )


# ---- the scan ------------------------------------------------------------


def run_screen(
    filters: Optional[ScreenFilters] = None,
    limit: int = 50,
    universe_limit: int = 300,
    with_fundamentals: bool = True,
    fundamental_limit: int = 60,
) -> Dict[str, Any]:
    """Score the universe, filter it, and return the ranked survivors.

    `universe_limit` caps how many names are priced and `fundamental_limit` how
    many of the technical survivors are additionally scraped — the two knobs
    that decide whether a run takes five seconds or five minutes.
    """
    filters = filters or ScreenFilters()

    cache_key = make_key(
        "screen",
        filters.cache_key_parts(),
        limit,
        universe_limit,
        with_fundamentals,
        fundamental_limit,
    )
    cached = _SCREENER_CACHE.get(cache_key)
    if cached is not None:
        return {**cached, "cached": True}

    candidates = symbol_master.universe(
        index=filters.index,
        sector=filters.sector,
        cap=filters.cap,
        fno_only=filters.fno_only,
        limit=universe_limit,
    )
    if not candidates:
        return {
            "count": 0,
            "scanned": 0,
            "universe": 0,
            "index": filters.index,
            "fundamentals_scored": 0,
            "results": [],
            "cached": False,
            "notes": [
                "No symbols matched the universe filters. If the symbol master "
                "is missing, run: python -m scripts.refresh_symbols"
            ],
        }

    by_yf = {record.yfinance: record for record in candidates}
    frames = fetch_price_frames(list(by_yf))

    # Pass 1: technicals for everything that priced.
    scored: List[Dict[str, Any]] = []
    for ticker, frame in frames.items():
        record = by_yf[ticker]
        tech = extract_technicals(frame)
        if not tech.get("available"):
            continue
        if not passes_technical_filters(tech, filters):
            continue
        tech_card = score_technicals(tech)
        if filters.min_technical_score is not None and (
            tech_card.score is None or tech_card.score < filters.min_technical_score
        ):
            continue
        scored.append({"record": record, "tech": tech, "tech_card": tech_card})

    # Rank by technical score before spending scrapes: fundamentals are the
    # expensive half, so the budget goes to the names most likely to survive.
    scored.sort(key=lambda row: row["tech_card"].score or 0.0, reverse=True)

    fundamentals_needed = with_fundamentals or wants_fundamentals(filters)
    if fundamentals_needed and scored:
        targets = scored[:fundamental_limit]
        with ThreadPoolExecutor(max_workers=FUNDAMENTAL_WORKERS) as pool:
            payloads = list(
                pool.map(lambda row: get_fundamentals(row["record"].symbol), targets)
            )
        for row, payload in zip(targets, payloads):
            row["fund"] = payload
            row["fund_card"] = score_fundamentals(payload)

    # Pass 2: combine, apply score filters, assemble recommendations.
    rows: List[ScreenRow] = []
    for row in scored:
        record = row["record"]
        fund = row.get("fund") or {}
        fund_card = row.get("fund_card")

        if wants_fundamentals(filters) and not passes_fundamental_filters(fund, filters):
            continue
        if filters.min_fundamental_score is not None and (
            fund_card is None
            or fund_card.score is None
            or fund_card.score < filters.min_fundamental_score
        ):
            continue

        components = {"technicals": row["tech_card"]}
        cards = [(row["tech_card"], 0.5)]
        if fund_card is not None:
            components["fundamentals"] = fund_card
            cards.append((fund_card, 0.5))

        # min_coverage=0.3 so a name with working technicals and no scrapable
        # fundamentals is still ranked, with its lower coverage visible rather
        # than being dropped without explanation.
        overall = scoring.combine("overall", cards, min_coverage=0.3)

        if filters.min_score is not None and (
            overall.score is None or overall.score < filters.min_score
        ):
            continue

        recommendation = scoring.recommend(record.symbol, overall, components)
        if filters.actions and recommendation.action not in filters.actions:
            continue

        rows.append(
            ScreenRow(
                symbol=record.symbol,
                name=record.name,
                sector=record.sector,
                cap=record.cap,
                price=row["tech"].get("current_price"),
                recommendation=recommendation,
                technicals=row["tech"],
                fundamentals=fund,
            )
        )

    ranked = scoring.rank([row.recommendation for row in rows])
    order = {rec.symbol: index for index, rec in enumerate(ranked)}
    rows.sort(key=lambda row: order.get(row.symbol, len(order)))

    notes: List[str] = []
    if len(frames) < len(candidates):
        notes.append(
            f"{len(candidates) - len(frames)} of {len(candidates)} symbols had no "
            "usable price history and were skipped."
        )

    result = {
        "count": len(rows),
        "scanned": len(frames),
        "universe": len(candidates),
        "index": filters.index,
        "fundamentals_scored": sum(1 for row in scored if "fund_card" in row),
        "results": [row.as_dict() for row in rows[:limit]],
        "cached": False,
        "notes": notes,
    }
    _SCREENER_CACHE.set(cache_key, result)
    return result


def available_filters() -> Dict[str, Any]:
    """The filter vocabulary, for populating the UI's controls."""
    return {
        "indices": [
            "NIFTY50", "NIFTYNEXT50", "NIFTY100", "NIFTY200", "NIFTY500",
            "NIFTYMIDCAP100", "NIFTYSMLCAP100",
        ],
        "sectors": symbol_master.master.sectors(),
        "caps": ["large", "mid", "small", "micro"],
        "actions": [action for _, action in scoring.ACTION_BANDS],
        "symbol_master": symbol_master.master.stats(),
    }
