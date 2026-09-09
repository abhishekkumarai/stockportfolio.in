"""The one place that knows what a symbol is.

Four namespaces have to reconcile for a single Indian stock:

    NSE trading symbol   RELIANCE            <- canonical here
    Fyers                NSE:RELIANCE-EQ     quotes, candles, holdings
    yfinance             RELIANCE.NS         fallback price/fundamental data
    Screener.in          /company/RELIANCE/  scraped fundamentals
    TradingView          NSE:RELIANCE        consensus technical rating

Everything downstream keys off the NSE symbol and converts at the edges. The
data comes from app/data/nse_symbols.json, rebuilt by scripts/refresh_symbols.py.

Beyond translation this module owns the *universe* — which is candidate
generation for the recommender. `universe()` answers "which names are even
eligible to be recommended", filtered by index, sector, cap and F&O presence.
"""

import json
import logging
import threading
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parent / "data" / "nse_symbols.json"

# Which benchmark a stock is measured against for relative strength and beta.
# Comparing a smallcap to the Nifty 50 mostly measures the size factor, not
# the stock, so the cap bucket picks the yardstick.
BENCHMARK_BY_CAP = {
    "large": "NIFTY50",
    "mid": "NIFTYMIDCAP100",
    "small": "NIFTYSMLCAP100",
    "micro": "NIFTYSMLCAP100",
}
DEFAULT_BENCHMARK = "NIFTY500"

# Ordering for search results and any other "biggest first" tiebreak.
_CAP_RANK = {"large": 0, "mid": 1, "small": 2, "micro": 3}


@dataclass(frozen=True)
class SymbolRecord:
    """One tradeable NSE equity, resolved across every namespace we use."""

    symbol: str
    name: str
    isin: str
    fyers: str
    series: str = "EQ"
    lot_size: int = 1
    tick_size: float = 0.05
    token: Optional[int] = None
    listing_date: str = ""
    sector: Optional[str] = None
    cap: Optional[str] = None
    indices: List[str] = field(default_factory=list)
    fno: bool = False
    fno_lot_size: Optional[int] = None

    @property
    def yfinance(self) -> str:
        return f"{self.symbol}.NS"

    @property
    def screener(self) -> str:
        return f"https://www.screener.in/company/{self.symbol}/"

    @property
    def tradingview(self) -> str:
        return f"NSE:{self.symbol}"

    @property
    def benchmark(self) -> str:
        """Index name this stock should be graded against."""
        return BENCHMARK_BY_CAP.get(self.cap or "", DEFAULT_BENCHMARK)

    def in_index(self, index_name: str) -> bool:
        return index_name.upper() in self.indices


class SymbolMaster:
    """Loaded once per process, then read-only."""

    def __init__(self, path: Path = DATA_PATH):
        self._path = path
        self._lock = threading.Lock()
        self._loaded = False
        self._records: Dict[str, SymbolRecord] = {}
        self._by_isin: Dict[str, str] = {}
        self._by_fyers: Dict[str, str] = {}
        self._benchmarks: Dict[str, str] = {}
        self._indices: Dict[str, dict] = {}
        self._generated_at = ""

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:  # another thread won the race
                return
            self._load()
            self._loaded = True

    def _load(self) -> None:
        if not self._path.exists():
            # Not fatal: MF-only analysis and the existing stock routes work
            # without it. Callers get "unknown symbol" and can still proceed.
            logger.error(
                "Symbol master missing at %s. Run: python -m scripts.refresh_symbols",
                self._path,
            )
            return

        raw = json.loads(self._path.read_text(encoding="utf-8"))
        self._generated_at = raw.get("generated_at", "")
        self._benchmarks = raw.get("benchmarks", {})
        self._indices = raw.get("indices", {})

        for symbol, entry in raw.get("equities", {}).items():
            record = SymbolRecord(
                symbol=symbol,
                name=entry.get("name") or symbol,
                isin=entry.get("isin", ""),
                fyers=entry["fyers"],
                series=entry.get("series", "EQ"),
                lot_size=entry.get("lot_size") or 1,
                tick_size=entry.get("tick_size") or 0.05,
                token=entry.get("token"),
                listing_date=entry.get("listing_date", ""),
                sector=entry.get("sector"),
                cap=entry.get("cap"),
                indices=list(entry.get("indices") or []),
                fno=bool(entry.get("fno")),
                fno_lot_size=entry.get("fno_lot_size"),
            )
            self._records[symbol] = record
            if record.isin:
                self._by_isin[record.isin] = symbol
            self._by_fyers[record.fyers.upper()] = symbol

        logger.info(
            "Symbol master loaded: %d equities, generated %s",
            len(self._records), self._generated_at or "unknown",
        )

    # ---- lookup ----------------------------------------------------------

    def lookup(self, text: str) -> Optional[SymbolRecord]:
        """Resolve any namespace's identifier to a record.

        Accepts "RELIANCE", "NSE:RELIANCE-EQ", "RELIANCE.NS", "reliance" and
        "INE002A01018". Returns None rather than raising — an unknown symbol is
        a normal outcome when a user types one in.
        """
        self._ensure_loaded()
        if not text:
            return None

        probe = text.strip().upper()
        if not probe:
            return None

        # Fyers form first: it is the only one containing a colon, so it can
        # never be confused with the others.
        if ":" in probe:
            symbol = self._by_fyers.get(probe)
            if symbol:
                return self._records[symbol]
            # Unknown series (a -BE name absent from the master, say): fall
            # through on the bare symbol between the colon and the suffix.
            probe = probe.split(":", 1)[1].rsplit("-", 1)[0]

        # ISINs are 12 chars, always INE/INF/IN9 for Indian securities.
        if len(probe) == 12 and probe[:2] == "IN":
            symbol = self._by_isin.get(probe)
            if symbol:
                return self._records[symbol]

        for suffix in (".NS", ".BO", "-EQ", "-BE"):
            if probe.endswith(suffix):
                probe = probe[: -len(suffix)]
                break

        return self._records.get(probe)

    def require(self, text: str) -> SymbolRecord:
        """lookup(), but raises. For paths where an unknown symbol is a bug."""
        record = self.lookup(text)
        if record is None:
            raise KeyError(f"Unknown NSE symbol: {text!r}")
        return record

    def search(self, query: str, limit: int = 20) -> List[SymbolRecord]:
        """Rank by how well the query matches the symbol or company name."""
        self._ensure_loaded()
        needle = (query or "").strip().upper()
        if len(needle) < 2:
            return []

        scored: List[tuple] = []
        for record in self._records.values():
            name = record.name.upper()
            if record.symbol == needle:
                rank = 0
            elif record.symbol.startswith(needle):
                rank = 1
            elif name.startswith(needle):
                rank = 2
            elif needle in record.symbol:
                rank = 3
            elif needle in name:
                rank = 4
            else:
                continue
            # Size breaks ties before name length does: a search for "BAJAJ"
            # should lead with Bajaj Auto and Bajaj Finserv, not whichever
            # namesake microcap happens to have the shortest ticker.
            scored.append(
                (rank, _CAP_RANK.get(record.cap, 9), len(record.symbol), record.symbol, record)
            )

        scored.sort(key=lambda row: row[:4])
        return [row[4] for row in scored[:limit]]

    # ---- universe (candidate generation) ---------------------------------

    def universe(
        self,
        index: Optional[str] = None,
        sector: Optional[str] = None,
        cap: Optional[str] = None,
        fno_only: bool = False,
        require_sector: bool = False,
        limit: Optional[int] = None,
    ) -> List[SymbolRecord]:
        """The pool of names eligible for scoring, narrowed by the usual axes.

        Defaults to everything, which is 2,700+ symbols including illiquid
        microcaps. Callers that fan out network calls per name should pass an
        index — NIFTY500 is the sane default for a screener run.
        """
        self._ensure_loaded()
        index_key = index.upper() if index else None

        out: List[SymbolRecord] = []
        for record in self._records.values():
            if index_key and not record.in_index(index_key):
                continue
            if sector and (record.sector or "").lower() != sector.lower():
                continue
            if cap and record.cap != cap:
                continue
            if fno_only and not record.fno:
                continue
            if require_sector and not record.sector:
                continue
            out.append(record)

        out.sort(key=lambda r: r.symbol)
        return out[:limit] if limit else out

    def sectors(self) -> List[str]:
        self._ensure_loaded()
        return sorted({r.sector for r in self._records.values() if r.sector})

    def benchmark_ticker(self, index_name: str) -> Optional[str]:
        """Fyers ticker for a benchmark index, e.g. NIFTY50 -> NSE:NIFTY50-INDEX."""
        self._ensure_loaded()
        key = index_name.upper()
        if key in self._benchmarks:
            return self._benchmarks[key]
        entry = self._indices.get(key)
        return entry.get("fyers") if entry else None

    def benchmark_for(self, text: str) -> str:
        """Fyers ticker of the index a given stock should be graded against."""
        record = self.lookup(text)
        index_name = record.benchmark if record else DEFAULT_BENCHMARK
        return self.benchmark_ticker(index_name) or "NSE:NIFTY50-INDEX"

    def stats(self) -> dict:
        self._ensure_loaded()
        return {
            "generated_at": self._generated_at,
            "equities": len(self._records),
            "with_sector": sum(1 for r in self._records.values() if r.sector),
            "fno": sum(1 for r in self._records.values() if r.fno),
            "indices": len(self._indices),
            "sectors": len(self.sectors()),
        }


# Single shared instance: the file is ~1 MB and immutable at runtime, so one
# copy per process is both correct and the cheapest option.
master = SymbolMaster()


# ---- module-level conveniences -------------------------------------------
# These are what the rest of the codebase calls. lru_cache because translation
# happens per holding per request and the answer never changes.


@lru_cache(maxsize=4096)
def to_fyers(symbol: str) -> Optional[str]:
    record = master.lookup(symbol)
    return record.fyers if record else None


@lru_cache(maxsize=4096)
def to_yfinance(symbol: str) -> Optional[str]:
    record = master.lookup(symbol)
    return record.yfinance if record else None


@lru_cache(maxsize=4096)
def to_screener(symbol: str) -> Optional[str]:
    record = master.lookup(symbol)
    return record.screener if record else None


@lru_cache(maxsize=4096)
def to_tradingview(symbol: str) -> Optional[str]:
    record = master.lookup(symbol)
    return record.tradingview if record else None


def canonical(symbol: str) -> Optional[str]:
    """The NSE trading symbol every other module should key off."""
    record = master.lookup(symbol)
    return record.symbol if record else None


def lookup(symbol: str) -> Optional[SymbolRecord]:
    return master.lookup(symbol)


def search(query: str, limit: int = 20) -> List[SymbolRecord]:
    return master.search(query, limit)


def universe(**kwargs) -> List[SymbolRecord]:
    return master.universe(**kwargs)


def batched(records: Iterable[SymbolRecord], size: int = 50) -> Iterable[List[str]]:
    """Chunk into Fyers-quote-sized batches (its documented cap is 50 symbols)."""
    batch: List[str] = []
    for record in records:
        batch.append(record.fyers)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch
