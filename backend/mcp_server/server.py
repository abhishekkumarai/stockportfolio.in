"""MCP server for stockportfolio.in — the portfolio as Claude-callable tools.

Speaks JSON-RPC 2.0 over stdio, hand-rolled rather than via the `mcp` package.
The dependency would be one more thing in a Docker image whose size is already
a live concern, and the protocol surface a read-only tool server needs is four
methods: `initialize`, `notifications/initialized`, `tools/list`, `tools/call`.

The previous version of this file was missing `initialize` entirely, which
means it could not complete the handshake — a client would connect, wait for a
response that never came, and time out. That is fixed here, along with:

* framing: **one JSON object per line**, and *nothing else* may go to stdout.
  A stray `print` corrupts the stream and the client's error is a parse
  failure with no hint where it came from. Every diagnostic here goes to stderr.
* notifications (a request with no `id`) get no response, per spec. Replying to
  one is a protocol violation that some clients treat as fatal.
* errors return a JSON-RPC error object rather than crashing the loop, so one
  bad tool call does not end the session.

Every tool is read-only. There is no order placement anywhere in this codebase
to expose.

Register with:

    claude mcp add stockportfolio -- python backend/mcp_server/server.py
"""

import json
import logging
import os
import sys
import traceback
from typing import Any, Dict, List, Optional

# The server is launched as a script from the repo root, so `app` is not
# importable until the backend directory is on the path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import symbols as symbol_master  # noqa: E402
from app.schemas import EquityHolding, FundHolding, PortfolioRequest  # noqa: E402

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "stockportfolio.in", "version": "2.0.0"}

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
logger = logging.getLogger("stockportfolio.mcp")


def log(message: str) -> None:
    """Diagnostics to stderr. stdout is the protocol channel and nothing else."""
    print(message, file=sys.stderr, flush=True)


# ---- schema fragments ----------------------------------------------------

EQUITY_ITEM = {
    "type": "object",
    "properties": {
        "symbol": {"type": "string", "description": "NSE symbol, e.g. RELIANCE"},
        "quantity": {"type": "number"},
        "avg_cost": {"type": "number", "description": "Average buy price per share"},
        "buy_date": {"type": "string", "description": "YYYY-MM-DD; needed for tax treatment"},
    },
    "required": ["symbol", "quantity", "avg_cost"],
}

FUND_ITEM = {
    "type": "object",
    "properties": {
        "scheme_code": {"type": "integer", "description": "AMFI scheme code"},
        "units": {"type": "number"},
        "avg_nav": {"type": "number"},
        "buy_date": {"type": "string"},
    },
    "required": ["scheme_code", "units", "avg_nav"],
}

PORTFOLIO_PROPERTIES = {
    "equity": {"type": "array", "items": EQUITY_ITEM, "description": "Stock holdings"},
    "funds": {"type": "array", "items": FUND_ITEM, "description": "Mutual fund holdings"},
    "cash": {"type": "number", "description": "Cash balance in INR"},
}


def portfolio_from(arguments: Dict[str, Any]) -> PortfolioRequest:
    return PortfolioRequest(
        equity=[EquityHolding(**row) for row in arguments.get("equity", [])],
        funds=[FundHolding(**row) for row in arguments.get("funds", [])],
        cash=float(arguments.get("cash", 0.0)),
    )


# ---- tools ---------------------------------------------------------------


def tool_get_portfolio(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from app.portfolio import value_portfolio

    return value_portfolio(portfolio_from(arguments))


def tool_danger_growth_radar(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from app.portfolio import value_portfolio
    from app.quant.growth import evaluate_portfolio_growth
    from app.quant.risk import evaluate_portfolio_danger

    request = portfolio_from(arguments)
    valuation = value_portfolio(request)
    holdings = valuation.get("holdings", [])
    total = (valuation.get("totals") or {}).get("current_value", 0.0)

    danger = evaluate_portfolio_danger(holdings, total, request.cash)
    growth = evaluate_portfolio_growth(holdings, total)

    return {
        "danger_score": danger["danger_score"],
        "danger_level": danger["danger_level"],
        "resilience_score": danger["resilience_score"],
        "danger_flags": danger["flags"],
        "risk_metrics": danger["metrics"],
        "growth_score": growth["growth_score"],
        "growth_level": growth["growth_level"],
        "growth_pillars": growth["pillars"],
        "stress_scenarios": danger["stress_tests"],
        "monte_carlo": (growth.get("monte_carlo") or {}).get("summary"),
    }


def tool_analyse_holding(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from app import scoring
    from app.fundamentals import get_fundamentals, score_fundamentals

    symbol = arguments.get("symbol", "")
    canonical = symbol_master.canonical(symbol) or symbol.upper()
    record = symbol_master.lookup(canonical)

    fundamentals = get_fundamentals(canonical)
    fundamental_card = score_fundamentals(fundamentals)

    technicals: Dict[str, Any] = {}
    technical_card = None
    try:
        import yfinance as yf

        from app.technicals import extract_technicals, score_technicals

        yf_symbol = symbol_master.to_yfinance(canonical) or f"{canonical}.NS"
        history = yf.Ticker(yf_symbol).history(period="1y", interval="1d")
        if not history.empty:
            if history.index.tz is not None:
                history.index = history.index.tz_localize(None)
            technicals = extract_technicals(history)
            technical_card = score_technicals(technicals)
    except Exception as exc:
        technicals = {"available": False, "reason": str(exc)}

    cards = [(card, 0.5) for card in (technical_card, fundamental_card) if card is not None]
    overall = scoring.combine("overall", cards, min_coverage=0.3) if cards else None

    return {
        "symbol": canonical,
        "name": record.name if record else None,
        "sector": record.sector if record else None,
        "cap": record.cap if record else None,
        "overall": overall.as_dict() if overall else None,
        "technicals": {"indicators": technicals,
                       "scorecard": technical_card.as_dict() if technical_card else None},
        "fundamentals": {"data": fundamentals, "scorecard": fundamental_card.as_dict()},
    }


def tool_screen_stocks(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from app.screener import ScreenFilters, run_screen

    filters = ScreenFilters(
        index=arguments.get("index", "NIFTY500"),
        sector=arguments.get("sector"),
        cap=arguments.get("cap"),
        min_score=arguments.get("min_score"),
        rsi_max=arguments.get("rsi_max"),
        above_sma200=arguments.get("above_sma200"),
        min_roce=arguments.get("min_roce"),
        max_pe=arguments.get("max_pe"),
        max_debt_to_equity=arguments.get("max_debt_to_equity"),
    )
    return run_screen(
        filters=filters,
        limit=int(arguments.get("limit", 25)),
        universe_limit=int(arguments.get("universe_limit", 200)),
        fundamental_limit=int(arguments.get("fundamental_limit", 40)),
    )


def tool_rebalance(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from app.portfolio import value_portfolio
    from app.quant.rebalance import generate_rebalancing_plan

    request = portfolio_from(arguments)
    valuation = value_portfolio(request)
    return generate_rebalancing_plan(
        holdings=valuation.get("holdings", []),
        total_current_value=(valuation.get("totals") or {}).get("current_value", 0.0),
        cash_inflow=float(arguments.get("cash_inflow", 0.0)),
        mode=arguments.get("mode", "zero_tax_inflow"),
    )


def tool_optimise(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from app.portfolio import value_portfolio
    from app.quant import prices as price_engine
    from app.quant.optimise import OptimisationConstraints, optimise
    from app.quant.tax import generate_target_rebalance

    request = portfolio_from(arguments)
    valuation = value_portfolio(request)
    holdings = valuation.get("holdings", [])
    total = (valuation.get("totals") or {}).get("current_value", 0.0)

    returns, coverage = price_engine.holdings_returns(holdings, arguments.get("period", "2y"))
    if returns.empty or len(returns.columns) < 2:
        return {
            "available": False,
            "reason": "At least two equity holdings with overlapping price history are needed.",
            "coverage": coverage,
        }

    sectors = {
        h["key"]: h.get("sector") or "Unclassified"
        for h in holdings if h.get("kind") == "equity"
    }
    result = optimise(
        returns,
        arguments.get("method", "hrp"),
        OptimisationConstraints(
            max_weight=float(arguments.get("max_weight", 0.35)), sectors=sectors
        ),
    )
    result["coverage"] = coverage

    if arguments.get("include_orders", True):
        result["rebalance_plan"] = generate_target_rebalance(
            holdings=holdings,
            target_weights=result["weights"],
            total_current_value=total,
            cash_inflow=float(arguments.get("cash_inflow", 0.0)),
            allow_selling=bool(arguments.get("allow_selling", True)),
        )
    return result


def tool_backtest(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from app.engine import robustness
    from app.engine.runner import run_symbol

    symbol = arguments.get("symbol", "")
    yf_symbol = symbol_master.to_yfinance(symbol) or symbol.upper()

    result = run_symbol(
        symbol=yf_symbol,
        start=arguments.get("start", "2021-01-01"),
        end=arguments.get("end", "2026-01-01"),
        strategy_name=arguments.get("strategy", "rsi"),
        strategy_params=arguments.get("params") or {},
        initial_capital=float(arguments.get("initial_capital", 100000.0)),
    )

    # Trim the per-bar equity curve: it is thousands of points that an LLM
    # cannot use and that would dominate the context window.
    result.pop("equity_curve", None)
    result.pop("orders", None)
    result["trades"] = result.get("trades", [])[:25]

    if arguments.get("permutation_test", False):
        from app.engine.runner import run_symbol as rerun

        full = rerun(
            symbol=yf_symbol,
            start=arguments.get("start", "2021-01-01"),
            end=arguments.get("end", "2026-01-01"),
            strategy_name=arguments.get("strategy", "rsi"),
            strategy_params=arguments.get("params") or {},
        )
        result["permutation_test"] = robustness.permutation_test(
            robustness.returns_from_equity(full["equity_curve"]), permutations=1000
        )
    return result


def tool_option_hedge(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from app.options import size_collar, size_protective_put
    from app.portfolio import value_portfolio
    from app.quant.risk import evaluate_portfolio_danger

    value = arguments.get("portfolio_value")
    beta = arguments.get("portfolio_beta")

    if value is None or beta is None:
        request = portfolio_from(arguments)
        valuation = value_portfolio(request)
        totals = valuation.get("totals") or {}
        danger = evaluate_portfolio_danger(
            valuation.get("holdings", []), totals.get("current_value", 0.0)
        )
        value = value if value is not None else totals.get("current_value", 0.0)
        beta = beta if beta is not None else (danger.get("metrics") or {}).get("portfolio_beta", 1.0)

    sizer = size_collar if arguments.get("strategy") == "collar" else size_protective_put
    return sizer(
        portfolio_value=float(value),
        portfolio_beta=float(beta),
        index_spot=float(arguments.get("index_spot", 0.0)),
        target_max_drawdown=float(arguments.get("target_max_drawdown", 0.10)),
        days_to_expiry=float(arguments.get("days_to_expiry", 30.0)),
        volatility=float(arguments.get("volatility", 0.15)),
    )


def tool_news_catalysts(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from app.ai import sentiment as sentiment_engine
    from app.news import get_portfolio_news_digest

    symbols = arguments.get("symbols", [])
    digest = get_portfolio_news_digest(symbols)[: int(arguments.get("limit", 20))]

    if arguments.get("llm_sentiment", True) and digest:
        classified = sentiment_engine.classify_batch([item["title"] for item in digest])
        for item, result in zip(digest, classified):
            item["llm_impact"] = result["impact"]
            item["llm_score"] = result["score"]
            item["llm_rationale"] = result["rationale"]

    return {"count": len(digest), "articles": digest}


def tool_market_regime(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from app.quant import prices as price_engine
    from app.quant import regime as regime_engine

    benchmark = price_engine.benchmark_series(arguments.get("period", "2y"))
    if benchmark.empty:
        return {"available": False, "reason": "Benchmark history could not be fetched."}
    return regime_engine.classify(benchmark)


def tool_lookup_symbol(arguments: Dict[str, Any]) -> Dict[str, Any]:
    results = symbol_master.search(arguments.get("query", ""), int(arguments.get("limit", 10)))
    return {
        "count": len(results),
        "results": [
            {
                "symbol": record.symbol,
                "name": record.name,
                "sector": record.sector,
                "cap": record.cap,
                "isin": record.isin,
                "fyers": record.fyers,
                "fno": record.fno,
                "benchmark": record.benchmark,
            }
            for record in results
        ],
    }


TOOLS: List[Dict[str, Any]] = [
    {
        "name": "get_portfolio",
        "description": (
            "Price a portfolio of Indian stocks and mutual funds. Returns per-holding "
            "value, P&L, and allocation by asset class, sector and market cap. Prices "
            "come from yfinance and mfapi.in; a holding that cannot be priced is "
            "returned unpriced with a reason rather than valued at cost."
        ),
        "handler": tool_get_portfolio,
        "inputSchema": {"type": "object", "properties": PORTFOLIO_PROPERTIES, "required": ["equity"]},
    },
    {
        "name": "get_danger_growth_radar",
        "description": (
            "The two headline scores: a 0-100 danger score (concentration, tail risk, "
            "beta, small-cap exposure) and a 0-100 expected-growth score, with the "
            "specific red flags behind them, VaR/CVaR, HHI, and crisis replay stress "
            "tests against 2008, March 2020, 2018 midcaps and the 2022 rate shock."
        ),
        "handler": tool_danger_growth_radar,
        "inputSchema": {"type": "object", "properties": PORTFOLIO_PROPERTIES, "required": ["equity"]},
    },
    {
        "name": "analyse_holding",
        "description": (
            "Full scorecard for one NSE stock: technical indicators (RSI, MACD, ADX, "
            "moving averages, Supertrend), fundamentals scraped from Screener.in "
            "(P/E, ROCE, ROE, debt, promoter pledging), Piotroski F-Score, Altman "
            "Z-Score, and a blended 0-100 score with the evidence behind it."
        ),
        "handler": tool_analyse_holding,
        "inputSchema": {
            "type": "object",
            "properties": {"symbol": {"type": "string", "description": "NSE symbol, e.g. RELIANCE"}},
            "required": ["symbol"],
        },
    },
    {
        "name": "screen_stocks",
        "description": (
            "Rank the NSE universe on the same technical + fundamental model used for "
            "holdings, so screener hits and holdings are directly comparable. Filter "
            "by index, sector, cap, score, RSI, trend, ROCE, P/E and leverage. A cold "
            "run over 200 symbols takes tens of seconds; results are cached an hour."
        ),
        "handler": tool_screen_stocks,
        "inputSchema": {
            "type": "object",
            "properties": {
                "index": {"type": "string", "description": "e.g. NIFTY500, NIFTY50"},
                "sector": {"type": "string"},
                "cap": {"type": "string", "enum": ["large", "mid", "small", "micro"]},
                "min_score": {"type": "number"},
                "rsi_max": {"type": "number"},
                "above_sma200": {"type": "boolean"},
                "min_roce": {"type": "number"},
                "max_pe": {"type": "number"},
                "max_debt_to_equity": {"type": "number"},
                "limit": {"type": "integer"},
                "universe_limit": {"type": "integer"},
                "fundamental_limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "rebalance_portfolio",
        "description": (
            "Equal-weight rebalancing order sheet with Indian tax treatment: STCG at "
            "20%, LTCG at 12.5% above the 1.25 lakh annual exemption, and an alert "
            "when a holding is within days of crossing the one-year LTCG threshold. "
            "Zero-tax inflow mode routes fresh capital only and sells nothing."
        ),
        "handler": tool_rebalance,
        "inputSchema": {
            "type": "object",
            "properties": {
                **PORTFOLIO_PROPERTIES,
                "cash_inflow": {"type": "number", "description": "Fresh capital to deploy, INR"},
                "mode": {"type": "string", "enum": ["zero_tax_inflow", "drift_rebalance"]},
            },
            "required": ["equity"],
        },
    },
    {
        "name": "optimise_portfolio",
        "description": (
            "Target weights from hierarchical risk parity (default), risk parity, "
            "minimum variance or maximum Sharpe, with an optional tax-aware order "
            "sheet to reach them. HRP is the default because it never inverts the "
            "covariance matrix and stays stable on the noisy estimates a 20-holding "
            "portfolio produces."
        ),
        "handler": tool_optimise,
        "inputSchema": {
            "type": "object",
            "properties": {
                **PORTFOLIO_PROPERTIES,
                "method": {"type": "string", "enum": ["hrp", "risk_parity", "min_variance", "max_sharpe"]},
                "max_weight": {"type": "number"},
                "period": {"type": "string", "description": "History window, e.g. 2y"},
                "include_orders": {"type": "boolean"},
                "cash_inflow": {"type": "number"},
                "allow_selling": {"type": "boolean"},
            },
            "required": ["equity"],
        },
    },
    {
        "name": "run_backtest",
        "description": (
            "Event-driven backtest with next-bar-open fills, slippage and Indian "
            "transaction costs (brokerage, STT, exchange charges, GST, stamp duty). "
            "Strategies: rsi, sma_cross, macd, bollinger, supertrend, momentum. "
            "Optionally runs a Monte Carlo permutation test, which reports the "
            "probability the result is indistinguishable from luck."
        ),
        "handler": tool_backtest,
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "start": {"type": "string", "description": "YYYY-MM-DD"},
                "end": {"type": "string", "description": "YYYY-MM-DD"},
                "strategy": {
                    "type": "string",
                    "enum": ["rsi", "sma_cross", "macd", "bollinger", "supertrend", "momentum"],
                },
                "params": {"type": "object"},
                "initial_capital": {"type": "number"},
                "permutation_test": {"type": "boolean"},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "option_chain_hedging",
        "description": (
            "Size the Nifty put or collar that caps a portfolio's drawdown at a "
            "chosen level, with the Black-Scholes premium, Greeks, annualised cost "
            "as a share of the portfolio, and the basis-risk caveats. Sizing only - "
            "this system has no order API and cannot place the trade."
        ),
        "handler": tool_option_hedge,
        "inputSchema": {
            "type": "object",
            "properties": {
                **PORTFOLIO_PROPERTIES,
                "portfolio_value": {"type": "number"},
                "portfolio_beta": {"type": "number"},
                "index_spot": {"type": "number", "description": "Current Nifty level"},
                "target_max_drawdown": {"type": "number", "description": "e.g. 0.10 for 10%"},
                "days_to_expiry": {"type": "number"},
                "volatility": {"type": "number", "description": "Annualised, decimal"},
                "strategy": {"type": "string", "enum": ["protective_put", "collar"]},
            },
            "required": ["index_spot"],
        },
    },
    {
        "name": "get_portfolio_news_catalysts",
        "description": (
            "Tagged news for a set of holdings, from free sources, classified into "
            "earnings, governance, promoter/insider, order wins, corporate actions "
            "and macro, with an LLM sentiment read per headline (VADER fallback when "
            "no API key is configured)."
        ),
        "handler": tool_news_catalysts,
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbols": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer"},
                "llm_sentiment": {"type": "boolean"},
            },
            "required": ["symbols"],
        },
    },
    {
        "name": "market_regime",
        "description": (
            "Classify the current market as trending up, trending down, choppy or "
            "crisis, from realised volatility against its own history, trend "
            "efficiency and drawdown, with hysteresis so the state does not flap. "
            "Descriptive, not predictive."
        ),
        "handler": tool_market_regime,
        "inputSchema": {
            "type": "object",
            "properties": {"period": {"type": "string", "description": "e.g. 2y"}},
        },
    },
    {
        "name": "lookup_symbol",
        "description": (
            "Resolve a company name or ticker against the NSE symbol master. Returns "
            "the canonical NSE symbol, ISIN, sector, market-cap bucket, F&O "
            "eligibility and the benchmark index the stock should be graded against. "
            "Use this before any other tool when the exact symbol is uncertain."
        ),
        "handler": tool_lookup_symbol,
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
]

HANDLERS = {tool["name"]: tool["handler"] for tool in TOOLS}
TOOL_SPECS = [
    {k: v for k, v in tool.items() if k != "handler"} for tool in TOOLS
]


# ---- JSON-RPC ------------------------------------------------------------


def send(payload: Dict[str, Any]) -> None:
    """One JSON object per line on stdout. Nothing else may ever go there."""
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def result(request_id: Any, value: Dict[str, Any]) -> None:
    send({"jsonrpc": "2.0", "id": request_id, "result": value})


def error(request_id: Any, code: int, message: str, data: Any = None) -> None:
    payload: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        payload["data"] = data
    send({"jsonrpc": "2.0", "id": request_id, "error": payload})


def handle(request: Dict[str, Any]) -> None:
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params") or {}
    # A request with no id is a notification: per the JSON-RPC spec it gets no
    # response at all, and replying to one breaks strict clients.
    is_notification = "id" not in request

    if method == "initialize":
        result(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
                "instructions": (
                    "Portfolio intelligence for Indian markets (NSE, BSE, AMFI mutual "
                    "funds). Every tool is read-only and no tool can place an order.\n\n"
                    "Two things to know before calling anything:\n"
                    "1. Symbols are canonical NSE trading symbols (RELIANCE, not "
                    "RELIANCE.NS). Call lookup_symbol first when unsure.\n"
                    "2. Upstream failures return {\"available\": false, \"reason\": ...} "
                    "rather than substituting estimated data. When a field is missing, "
                    "it genuinely could not be fetched — say so rather than filling it in."
                ),
            },
        )
        return

    if method in {"notifications/initialized", "initialized"}:
        return  # notification; no response

    if method == "ping":
        result(request_id, {})
        return

    if method == "tools/list":
        result(request_id, {"tools": TOOL_SPECS})
        return

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        handler = HANDLERS.get(name)
        if handler is None:
            error(request_id, -32602, f"Unknown tool: {name}")
            return
        try:
            payload = handler(arguments)
        except Exception as exc:
            log(f"Tool {name} failed: {exc}\n{traceback.format_exc()}")
            # A tool failure is reported as a tool result with isError, not as
            # a protocol error: the client should show the model what broke so
            # it can adapt, rather than treating the session as damaged.
            result(
                request_id,
                {
                    "content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}],
                    "isError": True,
                },
            )
            return

        result(
            request_id,
            {
                "content": [
                    {"type": "text", "text": json.dumps(payload, indent=2, default=str)}
                ],
                "isError": False,
            },
        )
        return

    if is_notification:
        return
    error(request_id, -32601, f"Method not found: {method}")


def main() -> None:
    log(f"stockportfolio.in MCP server ready ({len(TOOLS)} tools, protocol {PROTOCOL_VERSION})")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            error(None, -32700, f"Parse error: {exc}")
            continue

        try:
            handle(request)
        except Exception as exc:
            log(f"Unhandled error: {exc}\n{traceback.format_exc()}")
            error(request.get("id"), -32603, f"Internal error: {exc}")


if __name__ == "__main__":
    main()
