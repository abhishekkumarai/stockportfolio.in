"""Position sizers.

The old engine was all-in/all-out: every buy spent the entire account and
every sell liquidated. That makes the equity curve a leveraged bet on the last
signal and makes risk management impossible to express. These sizers answer
"how many shares", given cash, price and — for the risk-based ones — how
volatile the instrument currently is.

`VolatilityTargetSizer` is the one that matters. Sizing by rupees means a
stock with 6% daily swings gets the same allocation as one with 1%, so the
portfolio's risk is whatever the noisiest holding happens to be doing. Sizing
by ATR equalises *risk* instead: each position is allowed to lose the same
fraction of the account if its stop is hit.
"""

import logging
import math
from typing import Optional, Protocol

logger = logging.getLogger(__name__)


class Sizer(Protocol):
    def size(self, cash: float, equity: float, price: float,
             atr: Optional[float] = None) -> int: ...


class FixedSizer:
    """A constant share count. Useful as a control in comparisons."""

    def __init__(self, quantity: int = 1):
        self.quantity = max(1, int(quantity))

    def size(self, cash: float, equity: float, price: float,
             atr: Optional[float] = None) -> int:
        if price <= 0:
            return 0
        return min(self.quantity, int(cash // price))


class PercentSizer:
    """A fixed percentage of *equity*, capped by available cash.

    Percent of equity rather than of cash, so position size does not balloon
    after a big sale simply because the cash balance spiked.
    """

    def __init__(self, percent: float = 0.95):
        if not 0 < percent <= 1.0:
            raise ValueError("percent must be in (0, 1].")
        self.percent = percent

    def size(self, cash: float, equity: float, price: float,
             atr: Optional[float] = None) -> int:
        if price <= 0:
            return 0
        budget = min(equity * self.percent, cash)
        return max(0, int(budget // price))


class VolatilityTargetSizer:
    """Risk-parity sizing: every position risks the same slice of the account.

    With `risk_per_trade=0.01` and a stop `atr_multiple` ATRs away, a stopped-
    out trade costs about 1% of equity regardless of the instrument. Volatile
    names get fewer shares, quiet ones more, and the portfolio's risk stops
    depending on which stock happened to be in vogue.

    Falls back to `PercentSizer` when ATR is unavailable — early in a series,
    or on an instrument with no intraday range — rather than refusing to trade.
    """

    def __init__(self, risk_per_trade: float = 0.01, atr_multiple: float = 2.0,
                 max_percent: float = 0.95):
        if not 0 < risk_per_trade <= 0.25:
            raise ValueError("risk_per_trade must be in (0, 0.25].")
        self.risk_per_trade = risk_per_trade
        self.atr_multiple = atr_multiple
        self.max_percent = max_percent
        self._fallback = PercentSizer(max_percent)

    def size(self, cash: float, equity: float, price: float,
             atr: Optional[float] = None) -> int:
        if price <= 0:
            return 0
        if atr is None or not math.isfinite(atr) or atr <= 0:
            return self._fallback.size(cash, equity, price)

        risk_per_share = atr * self.atr_multiple
        quantity = int((equity * self.risk_per_trade) // risk_per_share)
        # Even a very quiet stock must not consume the whole account.
        cap = int(min(equity * self.max_percent, cash) // price)
        return max(0, min(quantity, cap))


class KellySizer:
    """Fractional Kelly from realised win rate and payoff ratio.

    Full Kelly maximises long-run growth and is far too aggressive in practice:
    it assumes the estimated edge is the true edge, and a backtest's win rate is
    an estimate from a small sample. `fraction` defaults to a quarter Kelly,
    and the whole thing falls back to a flat percentage until enough trades
    have accumulated to estimate anything.
    """

    def __init__(self, fraction: float = 0.25, min_trades: int = 20,
                 default_percent: float = 0.5, max_percent: float = 0.95):
        self.fraction = fraction
        self.min_trades = min_trades
        self.max_percent = max_percent
        self._fallback = PercentSizer(default_percent)
        self.wins: list = []
        self.losses: list = []

    def record(self, pnl_pct: float) -> None:
        (self.wins if pnl_pct > 0 else self.losses).append(abs(pnl_pct))

    def size(self, cash: float, equity: float, price: float,
             atr: Optional[float] = None) -> int:
        total = len(self.wins) + len(self.losses)
        if total < self.min_trades or not self.wins or not self.losses:
            return self._fallback.size(cash, equity, price)

        win_rate = len(self.wins) / total
        avg_win = sum(self.wins) / len(self.wins)
        avg_loss = sum(self.losses) / len(self.losses)
        if avg_loss <= 0:
            return self._fallback.size(cash, equity, price)

        payoff = avg_win / avg_loss
        kelly = win_rate - (1 - win_rate) / payoff
        allocation = max(0.0, min(self.max_percent, kelly * self.fraction))
        if allocation <= 0:
            return 0  # negative edge: the correct size is none
        budget = min(equity * allocation, cash)
        return max(0, int(budget // price))


SIZERS = {
    "fixed": FixedSizer,
    "percent": PercentSizer,
    "volatility": VolatilityTargetSizer,
    "kelly": KellySizer,
}


def build_sizer(name: str, **kwargs) -> Sizer:
    factory = SIZERS.get(name.lower())
    if factory is None:
        raise ValueError(f"Unknown sizer {name!r}. Known: {', '.join(sorted(SIZERS))}")
    return factory(**kwargs)
