"""The simulated broker: orders, fills, costs, positions and equity.

The single most important behaviour here is **next-bar-open fills**. The old
engine decided on today's close and filled at today's close, which is a
guarantee no broker offers and quietly adds a day of free foresight to every
signal. An order submitted while processing bar `i` is queued and filled at
bar `i+1`'s open, at that open plus slippage. If there is no bar `i+1` — the
signal fired on the last day of the test — the order expires unfilled, which
is the honest outcome.

Costs are modelled as they actually bite in India:

* **Brokerage** — a percentage with a per-order cap, matching the flat-fee
  discount brokers most retail users are on.
* **STT** — 0.1% on both legs of a delivery trade, and it is charged on the
  turnover, not the profit, so it is a real drag on high-turnover strategies.
* **Slippage** — a percentage of the fill price, adverse in the direction of
  the trade. Buying pays up; selling gets hit.

Stop-loss, take-profit and trailing stops are evaluated *intrabar* against the
bar's high and low, filled at the trigger price. That is optimistic on a gap —
a stop at 100 on a bar that opens at 92 fills at 92 here, not 100, because the
gap check runs first.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


@dataclass
class Order:
    symbol: str
    side: Side
    quantity: float
    submitted_index: int
    reason: str = ""
    status: OrderStatus = OrderStatus.PENDING
    fill_index: Optional[int] = None
    fill_price: Optional[float] = None
    fill_timestamp: Optional[datetime] = None
    fees: float = 0.0
    reject_reason: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": round(self.quantity, 4),
            "status": self.status.value,
            "fill_price": round(self.fill_price, 4) if self.fill_price else None,
            "fill_date": self.fill_timestamp.isoformat() if self.fill_timestamp else None,
            "fees": round(self.fees, 2),
            "reason": self.reason,
            "reject_reason": self.reject_reason,
        }


@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    avg_cost: float = 0.0
    opened_index: Optional[int] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_pct: Optional[float] = None
    highest_close: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.quantity > 0

    def market_value(self, price: float) -> float:
        return self.quantity * price

    def unrealised(self, price: float) -> float:
        return (price - self.avg_cost) * self.quantity


@dataclass
class Trade:
    """A round trip, recorded on exit. The unit every trade statistic uses."""

    symbol: str
    quantity: float
    entry_index: int
    entry_date: datetime
    entry_price: float
    exit_index: int
    exit_date: datetime
    exit_price: float
    fees: float
    pnl: float
    reason: str = ""

    @property
    def return_pct(self) -> float:
        cost = self.entry_price * self.quantity
        return (self.pnl / cost * 100.0) if cost else 0.0

    @property
    def bars_held(self) -> int:
        return self.exit_index - self.entry_index

    def as_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quantity": round(self.quantity, 4),
            "entry_date": self.entry_date.isoformat(),
            "entry_price": round(self.entry_price, 4),
            "exit_date": self.exit_date.isoformat(),
            "exit_price": round(self.exit_price, 4),
            "pnl": round(self.pnl, 2),
            "return_pct": round(self.return_pct, 2),
            "bars_held": self.bars_held,
            "fees": round(self.fees, 2),
            "reason": self.reason,
        }


@dataclass
class CostModel:
    """Indian delivery-equity transaction costs."""

    brokerage_pct: float = 0.0003        # 0.03%, typical discount-broker delivery
    brokerage_cap: float = 20.0          # per order, the flat-fee ceiling
    stt_pct: float = 0.001               # 0.1% each leg on delivery
    exchange_pct: float = 0.0000345      # NSE transaction charge
    gst_pct: float = 0.18                # on brokerage + exchange charges
    stamp_duty_pct: float = 0.00015      # buy side only
    slippage_pct: float = 0.0005         # 5bps adverse

    def charges(self, turnover: float, side: Side) -> float:
        """All-in cost of one leg. Turnover is quantity times price."""
        if turnover <= 0:
            return 0.0
        brokerage = min(turnover * self.brokerage_pct, self.brokerage_cap)
        exchange = turnover * self.exchange_pct
        stt = turnover * self.stt_pct
        gst = (brokerage + exchange) * self.gst_pct
        stamp = turnover * self.stamp_duty_pct if side is Side.BUY else 0.0
        return brokerage + exchange + stt + gst + stamp

    def fill_price(self, price: float, side: Side) -> float:
        """Apply slippage adversely — buys pay up, sells get hit."""
        drift = 1.0 + self.slippage_pct if side is Side.BUY else 1.0 - self.slippage_pct
        return price * drift


class Broker:
    """Cash, positions, the pending-order queue, and the equity curve."""

    def __init__(self, initial_cash: float, cost_model: Optional[CostModel] = None):
        if initial_cash <= 0:
            raise ValueError("Initial cash must be positive.")
        self.initial_cash = float(initial_cash)
        self.cash = float(initial_cash)
        self.costs = cost_model or CostModel()

        self.positions: Dict[str, Position] = {}
        self.pending: List[Order] = []
        self.orders: List[Order] = []
        self.trades: List[Trade] = []
        # Parallel arrays rather than a list of dicts: the analyzers do numpy
        # maths over these and a dict-per-bar would be converted anyway.
        self.equity_curve: List[float] = []
        self.equity_dates: List[datetime] = []
        self.cash_curve: List[float] = []

    # ---- orders ----------------------------------------------------------

    def submit(self, symbol: str, side: Side, quantity: float, bar_index: int,
               reason: str = "") -> Optional[Order]:
        """Queue an order for the next bar's open. Returns None for a no-op."""
        if quantity <= 0:
            return None
        order = Order(
            symbol=symbol, side=side, quantity=quantity,
            submitted_index=bar_index, reason=reason,
        )
        self.pending.append(order)
        self.orders.append(order)
        return order

    def position(self, symbol: str) -> Position:
        return self.positions.setdefault(symbol, Position(symbol=symbol))

    # ---- execution -------------------------------------------------------

    def execute_pending(self, feeds: Dict[str, Any], bar_index: int) -> List[Order]:
        """Fill every queued order at this bar's open. Called once per bar.

        Orders are sorted sells-first so that a strategy rotating out of one
        name and into another has the proceeds available in the same bar,
        rather than being rejected for insufficient cash on an arbitrary
        dictionary ordering.
        """
        if not self.pending:
            return []

        queue = sorted(self.pending, key=lambda o: 0 if o.side is Side.SELL else 1)
        self.pending = []
        filled: List[Order] = []

        for order in queue:
            feed = feeds.get(order.symbol)
            if feed is None or bar_index >= len(feed):
                order.status = OrderStatus.EXPIRED
                order.reject_reason = "No bar available to fill against."
                continue

            bar = feed.bar_at(bar_index)
            price = self.costs.fill_price(bar.open, order.side)

            if order.side is Side.BUY:
                self._fill_buy(order, price, bar)
            else:
                self._fill_sell(order, price, bar, bar_index)

            if order.status is OrderStatus.FILLED:
                filled.append(order)

        return filled

    def _fill_buy(self, order: Order, price: float, bar) -> None:
        turnover = order.quantity * price
        fees = self.costs.charges(turnover, Side.BUY)

        if turnover + fees > self.cash:
            # Shrink to what the cash affords rather than rejecting outright: a
            # sizer that asked for 101 shares when 100 are affordable should
            # buy 100, not nothing.
            affordable = int(self.cash / (price * (1 + self.costs.stt_pct + self.costs.brokerage_pct) + 0.01))
            if affordable <= 0:
                order.status = OrderStatus.REJECTED
                order.reject_reason = f"Insufficient cash: needed {turnover + fees:.2f}, have {self.cash:.2f}"
                return
            order.quantity = affordable
            turnover = affordable * price
            fees = self.costs.charges(turnover, Side.BUY)

        position = self.position(order.symbol)
        total_cost = position.avg_cost * position.quantity + turnover
        position.quantity += order.quantity
        position.avg_cost = total_cost / position.quantity if position.quantity else 0.0
        if position.opened_index is None:
            position.opened_index = bar.index
            position.highest_close = bar.close

        self.cash -= turnover + fees
        order.status = OrderStatus.FILLED
        order.fill_price = price
        order.fill_index = bar.index
        order.fill_timestamp = bar.timestamp
        order.fees = fees

    def _fill_sell(self, order: Order, price: float, bar, bar_index: int) -> None:
        position = self.position(order.symbol)
        quantity = min(order.quantity, position.quantity)
        if quantity <= 0:
            order.status = OrderStatus.REJECTED
            order.reject_reason = "No position to sell (shorting is not supported)."
            return

        order.quantity = quantity
        turnover = quantity * price
        fees = self.costs.charges(turnover, Side.SELL)
        pnl = (price - position.avg_cost) * quantity - fees

        self.cash += turnover - fees
        order.status = OrderStatus.FILLED
        order.fill_price = price
        order.fill_index = bar.index
        order.fill_timestamp = bar.timestamp
        order.fees = fees

        entry_index = position.opened_index if position.opened_index is not None else bar_index
        self.trades.append(
            Trade(
                symbol=order.symbol,
                quantity=quantity,
                entry_index=entry_index,
                entry_date=bar.timestamp,  # replaced by the runner, which knows entry dates
                entry_price=position.avg_cost,
                exit_index=bar.index,
                exit_date=bar.timestamp,
                exit_price=price,
                fees=fees,
                pnl=pnl,
                reason=order.reason,
            )
        )

        position.quantity -= quantity
        if position.quantity <= 1e-9:
            position.quantity = 0.0
            position.avg_cost = 0.0
            position.opened_index = None
            position.stop_loss = None
            position.take_profit = None
            position.trailing_pct = None
            position.highest_close = 0.0

    # ---- protective exits ------------------------------------------------

    def check_protective_exits(self, feeds: Dict[str, Any], bar_index: int) -> List[Order]:
        """Trigger stops and targets intrabar, before the strategy runs.

        Evaluated against this bar's high and low, and filled at the trigger
        price — except on a gap, where the open is worse than the trigger and
        the fill is the open. Skipping that gap check is the classic way a
        backtest reports a clean -5% stop on a bar that opened -20%.
        """
        triggered: List[Order] = []

        for symbol, position in self.positions.items():
            if not position.is_open:
                continue
            feed = feeds.get(symbol)
            if feed is None or bar_index >= len(feed):
                continue

            bar = feed.bar_at(bar_index)

            if position.trailing_pct:
                position.highest_close = max(position.highest_close, bar.close)
                trail_level = position.highest_close * (1 - position.trailing_pct)
                position.stop_loss = max(position.stop_loss or 0.0, trail_level)

            exit_price: Optional[float] = None
            reason = ""

            if position.stop_loss and bar.low <= position.stop_loss:
                exit_price = min(position.stop_loss, bar.open)
                reason = f"Stop-loss at {position.stop_loss:.2f}"
            elif position.take_profit and bar.high >= position.take_profit:
                exit_price = max(position.take_profit, bar.open)
                reason = f"Take-profit at {position.take_profit:.2f}"

            if exit_price is None:
                continue

            order = Order(
                symbol=symbol, side=Side.SELL, quantity=position.quantity,
                submitted_index=bar_index, reason=reason,
            )
            self.orders.append(order)
            self._fill_sell(order, exit_price, bar, bar_index)
            if order.status is OrderStatus.FILLED:
                triggered.append(order)

        return triggered

    # ---- accounting ------------------------------------------------------

    def mark_to_market(self, feeds: Dict[str, Any], bar_index: int, timestamp: datetime) -> float:
        holdings = 0.0
        for symbol, position in self.positions.items():
            if not position.is_open:
                continue
            feed = feeds.get(symbol)
            if feed is None or bar_index >= len(feed):
                continue
            holdings += position.market_value(feed.bar_at(bar_index).close)

        equity = self.cash + holdings
        self.equity_curve.append(equity)
        self.equity_dates.append(timestamp)
        self.cash_curve.append(self.cash)
        return equity

    @property
    def equity(self) -> float:
        return self.equity_curve[-1] if self.equity_curve else self.initial_cash

    def open_positions(self) -> List[Position]:
        return [p for p in self.positions.values() if p.is_open]
