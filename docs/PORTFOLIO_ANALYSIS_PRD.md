# Portfolio Analysis & Quant Research Engine — Design & Build Plan

## Context

The app today has three disconnected halves:

- **Stock research** (`backend/app/analysis.py`) — yfinance OHLCV + RSI/SMA/EMA + VADER news sentiment, one ticker at a time, with a mock-data fallback.
- **Mutual fund research** (`backend/app/mf_analysis.py`) — a genuinely solid single-scheme analytics library: trailing/rolling returns, CAGR, XIRR, Sharpe/Sortino, volatility, max drawdown, SIP/lumpsum simulation.
- **Fyers connectivity** (`backend/app/fyers_client.py`) — OAuth login plus exactly three endpoints: `profile`, `quotes`, `history`. No holdings, no positions, no funds.

What is missing is the thing the product is named after: **a portfolio**. Nothing aggregates multiple holdings, computes allocation, measures portfolio-level risk, or attributes return to positions. Every analysis is single-instrument.

This plan builds that layer — Fyers-sourced equity holdings plus manually entered mutual funds, run through combined **technical + fundamental + portfolio-risk** analysis — and then extends it with capabilities distilled from five reference projects the user supplied.

### Decisions taken (confirmed with the user)

| Question | Decision |
|---|---|
| Holdings source | Fyers holdings API for equity; manual entry for MFs, priced via mfapi.in |
| Fundamentals source | Scrape Screener.in / NSE (reusing the `curl_cffi` pattern in `scraper.py`), yfinance as fallback |
| Execution | **Analysis + paper trading only.** Never sends a live order to Fyers |
| Persistence | Stateless through Phase 5 (browser `localStorage`); Postgres introduced at Phase 6 when scheduled jobs need it |
| Extensions | All four prioritised: option chain, real backtesting engine, quant risk/optimisation, AI + MCP layer |
| Delivery | Phased, each phase independently shippable |

---

## What the five reference projects contribute

None of these is copyable wholesale — QuantDinger and Vibe-Trading are multi-worker platforms with Postgres, Celery, and 13-broker execution layers, far past what a Vercel + single Render service should become. What follows is the extracted, feasible subset.

| Project | What it actually is | What we take |
|---|---|---|
| **QuantDinger** | Self-hosted AI trading OS: Flask + Postgres + Redis + Celery, separate trading/scheduler workers, 8 broker adapters | The *separation of concerns*: scheduled scans as background jobs distinct from request handling. Strategy-runtime concept, paper-trading ledger, scoped-token agent gateway, LLM market analysis. **Not** its process topology — one Render worker suffices at this scale |
| **Vibe-Trading** | LLM agent (LangGraph) + 18 data sources + 13 brokers + `quantlib` (249 finance functions) + `alpha_zoo` (460 factors) | The quant substance: VaR/CVaR, Monte Carlo, factor attribution and regression, regime detection, portfolio optimisation, Monte Carlo permutation tests on backtests. Plus the **MCP server** pattern — exposing the portfolio as Claude-callable tools |
| **backtrader** | Mature event-driven Python backtesting framework: Cerebro/Strategy/Analyzer/Sizer/Broker, 122 indicators, commissions, slippage, bracket & OCO orders, resampling | Its architecture, adopted directly. Our `backtester.py` is a single-symbol all-in/all-out loop with a real flaw: it computes a signal from today's close and fills at that same close (`backtester.py:174-215`) — a trade nobody could have made. backtrader's next-bar-open fill model is the fix |
| **TradingView-API** | Node.js scraper for TradingView quotes, indicators, screener, replay | The *signals*, via Python equivalents rather than the Node library: `tradingview-ta` gives TradingView's own oscillator/MA consensus rating — a valuable independent cross-check on our technical score. Screener and hotlist ideas inform our own universe screener |
| **NSE Option Chain Analyzer** | Tkinter desktop app polling nseindia.com/option-chain, computing PCR and OI-change signals | The whole analytics model — PCR, OI build-up/unwinding, max pain, OI-wall support/resistance — but sourced from **Fyers' authenticated option-chain endpoint** instead of scraping NSE, which rate-limits and cookie-walls aggressively |

**Deliberate boundary:** no live order placement, in any phase. Signals, alerts and a simulated paper ledger only. This keeps the blast radius at zero and sidesteps SEBI research-analyst and algo-approval questions entirely.

---

## Architecture decisions

### 1. Stateless through Phase 5; Postgres from Phase 6

There is no database and no auth today, and Render's filesystem is ephemeral. Through Phase 5 the analysis endpoint is a **pure function of its request body**:

```
POST /api/portfolio/analyse
{
  "equity": [{"symbol": "NSE:RELIANCE-EQ", "quantity": 50, "avg_cost": 2380.5, "buy_date": "2024-03-11"}],
  "funds":  [{"scheme_code": 122639, "units": 412.331, "avg_nav": 61.24, "buy_date": "2023-08-01"}],
  "options": {"benchmark": "NSE:NIFTY50-INDEX", "risk_free_rate": 0.065}
}
```

The frontend persists holdings in `localStorage` under a versioned key. Working multi-user product, zero auth surface, ships fast.

Phase 6 introduces Render Postgres + SQLAlchemy + Alembic because alert history, scheduled scan results, paper-trade ledgers and factor time series are all inherently durable. Holdings migrate from `localStorage` to the DB at that point, behind a simple account model.

### 2. Fix the Fyers token model before building on it

`routes/fyers.py:74-76` writes `FYERS_ACCESS_TOKEN` into `backend/.env` on OAuth callback. Broken in production three ways: ephemeral container FS, no sharing across workers, and `/api/fyers/callback` is unauthenticated — anyone hitting the deployed URL overwrites the single shared server token.

**Fix:** the callback returns the token to the browser. The frontend stores it in `sessionStorage` and sends it as `X-Fyers-Token`. `get_client()` reads that header, falling back to the env var for local dev. Prerequisite for Phase 1, and small.

### 3. Symbol identity is the hard part

Four namespaces must reconcile: Fyers (`NSE:RELIANCE-EQ`), yfinance (`RELIANCE.NS`), Screener (`/company/RELIANCE/`), TradingView (`NSE:RELIANCE`). A single `symbols.py` owns all translation, backed by a checked-in `nse_symbols.json` (symbol, ISIN, name, sector, industry, index membership, lot size) refreshed from NSE's equity and F&O masters. Everything downstream keys off the canonical NSE trading symbol.

### 4. No mock-data fallbacks

`analysis.py:145-164` and `backtester.py:48-73` silently substitute invented prices and random-walk history when yfinance fails. In a portfolio tool where a user acts on the number, that is dangerous. All new code fails visibly — `{"available": false, "reason": "..."}` — and the two existing fallbacks are removed as part of Phase 2/3.

---

## The analysis model

Each holding gets independent 0–100 sub-scores, then a blended verdict. Scores are **always** returned alongside the raw inputs that produced them, so the UI explains itself rather than showing a mystery number.

### A. Technical score (equity)

From Fyers daily candles (`history`, 1D — capped at 366 days per call, so longer windows need chunking).

| Signal | Computation | Weight |
|---|---|---|
| Trend | Price vs SMA50 vs SMA200; golden/death cross state; ADX for trend strength | 25% |
| Momentum | RSI(14) — reuse `analysis.calculate_rsi` | 20% |
| MACD | EMA12 − EMA26, signal EMA9, histogram sign & slope | 20% |
| Volatility position | Bollinger %B (20, 2σ); ATR(14) as % of price | 15% |
| Volume | 20d vs 50d average volume; OBV slope | 10% |
| Relative strength | 3m/6m return vs Nifty 50 over the same window | 10% |

New `backend/app/technicals.py` — pure `pd.Series → dict` functions (`macd`, `bollinger`, `atr`, `obv`, `adx`, `supertrend`, `relative_strength`), mirroring the shape of `mf_analysis.py`. `calculate_rsi` is imported from `analysis.py`, not reimplemented.

**Cross-check:** `tradingview_ta.TA_Handler` returns TradingView's own consensus (oscillator rating, MA rating, summary) for `NSE:{symbol}`. Displayed beside our score as a second opinion. Where the two disagree sharply, that disagreement is itself the signal worth surfacing.

### B. Fundamental score (equity)

Scraped from Screener.in's company page (ratios block + quarterly/annual tables), cached 24h — fundamentals change quarterly.

| Pillar | Metrics | Weight |
|---|---|---|
| Valuation | P/E vs 5y median and vs sector median; P/B; EV/EBITDA | 30% |
| Profitability | ROE, ROCE, operating & net margin, 3y margin trend | 25% |
| Growth | 3y/5y revenue & PAT CAGR; latest QoQ and YoY | 25% |
| Balance sheet | Debt/equity, interest coverage, current ratio | 20% |

Scoring is **percentile-within-sector**, not absolute thresholds — 25× P/E means very different things for an FMCG name and a PSU bank. Sector medians computed across the covered universe and cached.

Scraping realities designed for up front: Screener rate-limits, its DOM changes, some tickers 404. `fundamentals.py` returns `{"available": false, "reason": ...}` rather than raising or fabricating; every field is `Optional`; yfinance `.info` is the secondary source.

### C. Fund score (mutual funds)

Mostly reuses `mf_analysis.py`. Added:

- **Benchmark-relative**: alpha, beta, R², tracking error, information ratio vs the category index (new `benchmarks.py` mapping `scheme_category → index`).
- **Consistency**: share of rolling 3y windows beating the benchmark — the single most useful fund metric, and `rolling_returns` (`mf_analysis.py:196`) already has the window machinery.
- **Capture ratios**: up-capture and down-capture.

Blend: rolling consistency 30%, risk-adjusted return 30%, alpha 20%, drawdown behaviour 20%.

### D. Portfolio-level analysis (`backend/app/portfolio.py`)

**Valuation & P&L** — live prices via `FyersClient.quotes` (batched at the documented 50-symbol cap) and `MFApiClient.get_latest_nav`. Per holding: current value, unrealised P&L absolute and %, weight. Portfolio XIRR from the buy-date cashflow ledger using the existing `mf_analysis.xirr` (`mf_analysis.py:239`) — already a general-purpose bisection solver, no changes needed.

**Allocation & concentration** — asset class, sector, market-cap bucket, fund category; Herfindahl-Hirschman Index and top-5 weight as concentration measures.

**Risk** — portfolio daily return series reconstructed at current weights (a static-weight approximation, documented as such). Volatility, Sharpe, Sortino, max drawdown all reuse `mf_analysis.risk_metrics` and `max_drawdown` on the synthesised series. Plus correlation matrix, portfolio beta vs Nifty, and **diversification ratio** (weighted average of individual vols ÷ portfolio vol — a value near 1.0 means the diversification is cosmetic).

**Attribution** — contribution to return per holding and per sector (weight × return), so the user sees which three positions actually drove the year.

**Alerts** — deterministic rules with severities: single holding > 20%; sector > 35%; holding down > 25% from cost; RSI > 75 on a large position; fund trailing its benchmark over 3y; portfolio beta > 1.3.

**Look-through overlap** — two equity funds may both be 8% HDFC Bank. Fund holdings are absent from mfapi.in, so real overlap needs scraped AMC monthly disclosures (Phase 4, best-effort). Until then overlap is category-level only, stated as such in the UI.

---

## Phases

### Core track

**Phase 0 — Foundations**
- `symbols.py` + `data/nse_symbols.json`: cross-namespace symbol translation, ISIN, sector, index and F&O membership.
- Promote `mfapi_client._TTLCache` (`mfapi_client.py:64`) into shared `backend/app/cache.py` — already thread-safe with eviction, and the fundamentals scraper and quote layer both need it. `mfapi_client.py` imports from the new location.
- `rate_limit.py`: token bucket for Fyers' 10/s, 200/min, 10k/day caps, which `fyers_client._get` ignores entirely today.
- Header-based Fyers token (architecture decision 2): `routes/fyers.py:17` and `:42-86`.

**Phase 1 — Holdings ingestion**
- Extend `FyersClient` with `holdings()`, `positions()`, `funds()`, and `history_range()` that chunks past the 366-day window.
- `schemas.py` with Pydantic models (`EquityHolding`, `FundHolding`, `PortfolioRequest`, `PortfolioAnalysis`) and normalisation of Fyers' `{s, code, candles: [[ts,o,h,l,c,v]]}` into typed objects. The codebase currently passes raw upstream dicts straight through (`routes/fyers.py:114-141`), which will not survive contact with an aggregator.
- `GET /api/fyers/holdings`; frontend `/portfolio` page with connect flow, holdings table, manual MF entry in `localStorage`.
- **Ships:** a real portfolio view with live values and P&L.

**Phase 2 — Technical analysis** — `technicals.py`, `score_technicals()`, `tradingview-ta` consensus, `GET /api/stocks/{symbol}/technicals`, per-holding score column and an expandable detail panel with a price + SMA overlay chart (Chart.js is already registered at `funds/[schemeCode]/page.tsx:29`). Removes the `analysis.py` mock fallback.

**Phase 3 — Fundamental analysis** — `fundamentals.py` (Screener via `curl_cffi impersonate="chrome"`, same technique as `scraper.py:25`), sector percentile scoring, 24h cache, `GET /api/stocks/{symbol}/fundamentals`, fundamentals card in the detail panel.

**Phase 4 — Portfolio analytics** — `portfolio.py` (valuation, allocation, HHI, risk, correlation, attribution, alerts, combined score), `POST /api/portfolio/analyse`, `benchmarks.py`, fund alpha/beta/capture added to `mf_analysis.py`. Frontend dashboard: allocation donuts, correlation heatmap, attribution bars, alerts panel, portfolio-vs-benchmark chart.

**Phase 5 — Screener** — score the full NSE universe on the same technical + fundamental model, rank and filter it (TradingView-screener inspired). Surfaces "what should I buy" next to "what do I hold", and reuses every scoring function already built. Needs the Phase 0 rate limiter and aggressive caching to be viable.

### Extension track

**Phase 6 — Persistence & scheduling** *(unlocks everything below)*
- Render Postgres + SQLAlchemy + Alembic; simple account model; holdings migrate out of `localStorage`.
- A background scheduler (APScheduler in-process, or a Render cron job hitting an authenticated endpoint — sufficient here; QuantDinger's Celery + dual-Redis topology is overkill at this scale).
- Nightly jobs: portfolio snapshot, fundamentals refresh, screener rescan, alert evaluation. Alert history and delivery (email/Telegram).

**Phase 7 — Option chain analytics** *(from the NSE analyzer)*
- `FyersClient.option_chain(symbol, strike_count, expiry)` via Fyers' authenticated option-chain endpoint — no NSE cookie-wall scraping.
- `options.py`: PCR (OI and volume), OI build-up classification (long build-up / short build-up / long unwinding / short covering from ΔOI vs Δprice), **max pain**, OI-wall support and resistance, IV skew and term structure.
- Black-Scholes Greeks (delta, gamma, theta, vega) and payoff diagrams for multi-leg positions.
- **Portfolio hedging**: given portfolio beta and value, size the Nifty put or collar that hedges a chosen drawdown, and price it.
- `GET /api/options/{symbol}/chain` and `/analysis`; frontend option-chain page with an OI-by-strike chart and payoff diagram.

**Phase 8 — Backtesting engine v2** *(from backtrader)*
- Adopt backtrader's abstractions in `backend/app/engine/`: `DataFeed`, `Strategy`, `Broker`, `Sizer`, `Analyzer`, `Order`. Either wrap the `backtrader` package directly or implement the same model — the wrapper is faster to ship, our own is lighter to deploy; decide at implementation time by measuring image size, which already matters for this Render service.
- Fixes the existing engine's real defects: **next-bar-open fills** instead of same-close (`backtester.py:174-215`), slippage, percentage and volatility-based position sizing, partial positions instead of all-in/all-out, multi-asset portfolio backtests, stop-loss/take-profit and trailing stops.
- Analyzers: Sharpe, Sortino, Calmar, SQN, max drawdown, trade-level stats, exposure, turnover.
- **Walk-forward optimisation** and **Monte Carlo permutation testing** (from Vibe-Trading) — shuffle returns and re-run to answer whether a strategy's edge beats luck. This is what stops the existing backtester from flattering overfit strategies.
- Strategy library: RSI, SMA crossover, MACD, Bollinger reversion, Supertrend, momentum rotation. Existing `run_backtest` stays as a thin adapter so `/api/backtest` and its frontend page keep working.

**Phase 9 — Quant risk & optimisation** *(from Vibe-Trading's `quantlib`)*
- `quant/risk.py`: historical, parametric and Cornish-Fisher **VaR/CVaR**; Monte Carlo portfolio projection (GBM and bootstrapped historical) with percentile fan charts; stress scenarios replaying 2008, March 2020 and the 2018 NBFC crisis against current holdings.
- `quant/factors.py`: factor exposure regression against market/size/value/momentum/quality/low-vol for Indian equities; rolling factor betas; return decomposition into factor vs idiosyncratic.
- `quant/regime.py`: market regime detection (trending/choppy/crisis) from volatility and correlation state, with hysteresis so it does not flap.
- `quant/optimise.py`: mean-variance efficient frontier, minimum variance, maximum Sharpe, **risk parity**, and **HRP** (hierarchical risk parity — robust where covariance estimation is noisy, which it always is with ~20 holdings). Constraints: max weight, sector caps, no-shorting, lot sizes.
- **Rebalancing engine**: current vs target weights → concrete buy/sell list, with tax awareness (Indian STCG/LTCG, the ₹1.25L LTCG exemption, and grandfathering) so it does not recommend a rebalance that costs more in tax than it gains.
- Frontend: efficient-frontier scatter, Monte Carlo fan chart, factor exposure bars, VaR gauges, rebalancing table.

**Phase 10 — Paper trading & signals** *(from QuantDinger)*
- Persisted paper-trade ledger: virtual cash, positions, order log, realised/unrealised P&L, benchmarked against buy-and-hold. **Never touches the Fyers order API.**
- Deploy a backtested strategy against live prices in paper mode; nightly evaluation generates signals with a full audit trail.
- Divergence tracking: paper performance vs the backtest that justified it — the honest test of whether a strategy survived contact with out-of-sample data.

**Phase 11 — AI layer & MCP server** *(from Vibe-Trading / QuantDinger)*
- `ai/narrative.py`: an LLM-written monthly portfolio report over the computed metrics — allocation drift, what drove returns, concentration risks, fund underperformance. Uses the Claude API (`claude-opus-5` for the report, `claude-haiku-4-5-20251001` for cheap per-holding summaries). **Strictly a narrator over computed numbers — it never invents a metric or issues a recommendation the deterministic scorers did not produce.** Load the `claude-api` skill before writing this module.
- Upgrade sentiment: `analysis.analyze_sentiment`'s VADER lexicon is trained on English social media and is close to useless on Indian financial headlines ("PAT up 12% YoY, margin guidance trimmed" scores neutral). Replace with an LLM classifier over the existing `GoogleNewsScraper` output, with VADER retained as a fallback.
- **MCP server** (`backend/mcp_server/`) exposing the portfolio as Claude-callable tools: `get_portfolio`, `analyse_holding`, `run_backtest`, `screen_stocks`, `option_chain`, `optimise_portfolio`. Read-only, token-scoped. This makes the whole system directly usable from Claude Code, which is the highest-leverage item in the extension track for this user specifically.

---

## Files

**New (core):** `backend/app/` → `symbols.py`, `cache.py`, `rate_limit.py`, `technicals.py`, `fundamentals.py`, `portfolio.py`, `benchmarks.py`, `schemas.py`, `screener.py`, `data/nse_symbols.json`, `routes/portfolio.py`, `routes/screener.py`; `frontend/src/app/portfolio/**`, `frontend/src/app/screener/**`, `frontend/src/lib/portfolioApi.ts`.

**New (extensions):** `backend/app/` → `db/` (models, session, Alembic), `scheduler.py`, `options.py`, `engine/` (feed, strategy, broker, sizer, analyzers, strategies), `quant/` (risk, factors, regime, optimise, rebalance), `paper/` (ledger, runner), `ai/` (narrative, sentiment), `routes/{options,quant,paper,ai}.py`; `backend/mcp_server/`; `frontend/src/app/{options,quant,paper}/**`.

**Modified:** `fyers_client.py` (holdings/positions/funds/option-chain, rate limiting, normalisation), `routes/fyers.py` (token model, holdings route), `main.py` (register routers; the title at `main.py:49` still reads "Stock Analyst & Backtesting API"), `mf_analysis.py` (benchmark-relative metrics), `mfapi_client.py` (shared cache import), `analysis.py` + `backtester.py` (remove mock fallbacks), `requirements.txt`, `.env.example` (document the undocumented `FYERS_REFRESH_TOKEN`).

**Reused as-is:** `mf_analysis.xirr`, `risk_metrics`, `max_drawdown`, `rolling_returns`, `to_series`, `_cagr`, `_round`; `analysis.calculate_rsi`; `GoogleNewsScraper`; the `curl_cffi` impersonation pattern (`scraper.py:25`); the `glass-panel` / `metric-card` / `custom-table` CSS vocabulary in `globals.css`; the debounce + `AbortController` + URL-sync pattern in `funds/FundSearch.tsx:49-78`.

**New dependencies:** `tradingview-ta`, `scipy` (optimisation, Cornish-Fisher), `statsmodels` (factor regression), `sqlalchemy` + `alembic` + `psycopg` (Phase 6), `apscheduler` (Phase 6), `anthropic` (Phase 11), `mcp` (Phase 11), optionally `backtrader` (Phase 8). Watch the Docker image size — it already matters for this Render service.

**Also on approval:** this document is copied to `docs/PORTFOLIO_ANALYSIS_PRD.md`, alongside the existing `docs/DEPLOYMENT_PRD.md`.

---

## Verification

Each phase is verified end-to-end before the next begins.

1. **Unit tests** — there is no test suite today, so add `backend/tests/` with pytest: technical indicators against hand-computed fixtures; Black-Scholes against published option values; VaR against a known normal distribution; the optimiser against a textbook two-asset frontier; portfolio aggregation over a synthetic 3-holding portfolio whose weights and XIRR are known by construction; `xirr` against a textbook cashflow.
2. **Look-ahead-bias test** *(Phase 8, the one that matters most)* — run a strategy that peeks at tomorrow's close and assert the engine rejects or cannot express it. Then confirm identical results running bar-by-bar versus batch.
3. **Live smoke** — `python -m app.main` (dev server on `127.0.0.1:8001`), exercise `/api/fyers/holdings`, `/api/stocks/{sym}/technicals`, `/api/stocks/{sym}/fundamentals`, `/api/options/{sym}/analysis`, `POST /api/portfolio/analyse`; confirm shapes match the Pydantic models via `/docs`.
4. **Cross-check the numbers against reality** — this matters more than the tests. RSI/MACD against TradingView for two or three liquid names; portfolio value and P&L against what the Fyers app itself shows; PCR and max pain against a public option-chain site; fund returns against Value Research. A portfolio tool that is subtly wrong is worse than no tool.
5. **Scraper resilience** — run the fundamentals scraper over ~30 symbols spanning large/mid/small cap; confirm failures degrade to `available: false` rather than raising or fabricating.
6. **Frontend** — `pnpm dev` in `frontend/`, walk the Fyers connect flow, add a manual MF holding, confirm the dashboard renders, `localStorage` survives reload, and the dark theme holds on the new charts.
7. **MCP** *(Phase 11)* — connect the server to Claude Code via `claude mcp add` and confirm each tool returns real portfolio data.

## Risks

- **Scope.** This is a long roadmap. Phases 0–4 are the product; everything after is optional depth. Phase 6 (persistence) gates 7–11, so it is the real decision point — stopping at Phase 5 leaves a complete, coherent app.
- **Screener scraping is brittle.** Mitigated by the `available: false` contract, caching and the yfinance fallback — but expect to fix selectors periodically. Same for AMC portfolio disclosures.
- **Fyers token lives one day**, and refresh-token minting needs the account PIN, deliberately unimplemented (`fyers_client.py:13-15`). Users re-login daily; surface that clearly rather than failing opaquely. Scheduled jobs (Phase 6+) cannot use a user's Fyers token at all — nightly work must run off mfapi.in and yfinance.
- **Backtests flatter overfit strategies.** Walk-forward and Monte Carlo permutation testing exist precisely to counter this and should not be treated as optional extras.
- **Static-weight portfolio return reconstruction** is an approximation; a true time-weighted series needs a transaction history that Fyers holdings does not provide. Label it in the UI.
- **Not investment advice.** Every score is a heuristic. Carry the existing disclaimer pattern (`funds/[schemeCode]/page.tsx:522`) onto every scored view, and make the AI narrative's role — narrator, not adviser — explicit on screen.
