"""Paper trading (Phase 10).

A persisted simulated ledger — virtual cash, positions, an append-only order
log — that runs a backtested strategy against live prices and tracks how far
its real behaviour diverges from the backtest that justified it.

Nothing in this package can place a live order. `FyersClient` implements market
data and login only; there is no order API to call.
"""

from app.paper.ledger import (
    InsufficientFunds,
    NoPosition,
    divergence,
    execute,
    list_accounts,
    open_account,
    order_log,
    record_signal,
    signal_log,
    valuation,
)

__all__ = [
    "InsufficientFunds", "NoPosition", "divergence", "execute", "list_accounts",
    "open_account", "order_log", "record_signal", "signal_log", "valuation",
]
