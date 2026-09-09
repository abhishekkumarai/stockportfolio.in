# stockportfolio.in — Work In Progress (WIP)

> **Active Sprint**: Phase 14 — India Macro, Inter-Market Radar, Quant ML Alpha & Stitch MCP UI Redesign  
> **Last Updated**: 2026-09-09  
> **Repository**: [`stockportfolio.in`](file:///c:/Users/abhi3/Documents/work/stockportfolio_in)  
> **Current Status**: 🟡 **In-Flight / Active Planning & Implementation**

---

## 1. Executive Summary of Current State

All fundamental and quant foundations (**Phases 0 through 13**) are completed locally:
- ✅ Multi-asset holdings & Fyers bridge (`/portfolio`)
- ✅ Technical analysis engine & TradingView alignment
- ✅ Screener.in fundamental scraper, Piotroski F-Score, Altman Z-Score
- ✅ VaR, CVaR, HHI concentration traps, 1,000-path Monte Carlo cone
- ✅ NSE universe screener with presets (`/screener`)
- ✅ Option chain radar, PCR, Max Pain, OI walls (`/options`)
- ✅ Event-driven backtester v2 with next-bar-open fills (`/lab`)
- ✅ Hierarchical Risk Parity (HRP) & Indian tax-aware rebalancing (`/quant`)
- ✅ Paper trading ledger & backtest divergence tracking (`/paper`)
- ✅ Containerized stack (`docker-compose.yml`, Postgres 16, Redis 7, worker, api)
- ✅ Obsidian Craft design system (flat `#09090b` zinc, hairlines, fixed app shell, `/recommendations`)

**Current Focus (Phase 14)**:
Bridging macroeconomic transmission channels with empirical quantitative machine learning and modern UI consoles using **100% free & open APIs** and **Google Stitch MCP tools**.

---

## 2. Phase 14 Milestone Checklist & Task Breakdown

| # | Task / Deliverable | Status | Target File(s) | Key Specifications |
|---|---|:---:|---|---|
| **14.1** | **India Macro & Inter-Market Transmission Engine** | ✅ Completed | `backend/app/macro.py`<br>`backend/tests/test_macro.py` | • Ingest `BZ=F`, `INR=X`, `^TNX`, `GC=F`, `^INDIAVIX`<br>• Crude Pressure Index (`BENIGN`, `MODERATE`, `ELEVATED`)<br>• FX Rupee velocity tailwinds (IT/Pharma)<br>• Macro Regime Classifier (Goldilocks, Imported Inflation, Risk-Off)<br>• NIFTY Sector Relative Momentum vs NIFTY 50 |
| **14.2** | **NSE Live Market Pulse & Real-Time Scanners** | ✅ Completed | `backend/app/market_pulse.py`<br>`backend/tests/test_market_pulse.py` | • Live NSE Advance/Decline breadth ratio<br>• Volume Shockers ($Volume_t \ge 2\times SMA_{20}(Volume)$)<br>• 52-Week High Breakouts with VCP consolidation filter |
| **14.3** | **Quant ML Alpha Factor Matrix & Ranker** | ⬜ Pending | `backend/app/ml/dataset.py`<br>`backend/app/ml/labeling.py`<br>`backend/app/ml/validation.py`<br>`backend/app/ml/models/`<br>`backend/app/ml/pipeline.py` | • Point-in-time factor matrix augmented with Macro Betas<br>• Target: Forward 10-day excess return ($R_{i, t+10} - R_{\text{NIFTY}, t+10}$)<br>• Purged Walk-Forward CV with 5-day post-test embargo<br>• Honest benchmark against naive majority baseline<br>• Pure NumPy/SciPy L2 Ridge ranker + LightGBM fallback |
| **14.4** | **REST API Routes & Status Integration** | ⬜ Pending | `backend/app/routes/macro.py`<br>`backend/app/routes/market_pulse.py`<br>`backend/app/routes/ml.py` | • `/api/macro` (regime, inter-market tickers, sector rotation)<br>• `/api/market-pulse` (breadth, volume shockers, 52W breakouts)<br>• `/api/ml/rankings` (Decile 1–10, ATR $+2\sigma/-1.5\sigma$ levels)<br>• Schema validation with sub-500ms cached execution |
| **14.5** | **Google Stitch MCP UI Redesign** | ⬜ Pending | `frontend/src/app/macro/`<br>`frontend/src/app/pulse/`<br>`frontend/src/app/recommendations/` | • Connect to Stitch Project `17247566464105962351`<br>• Port Screen `876a35da...` → `/macro` console<br>• Port Screen `ed0e7c18...` → `/recommendations` AI Radar Tab<br>• Generate `/pulse` screen via Stitch MCP tool<br>• Match Obsidian Craft styling standards |
| **14.6** | **Automated Test Suite & Verification** | ⬜ Pending | `backend/tests/test_macro.py`<br>`backend/tests/test_market_pulse.py`<br>`backend/tests/test_ml_*.py` | • 100% test coverage on calculations and zero-leakage<br>• Verified free API endpoints without network failure traps |
| **14.7** | **Backend Dependency Management Migration to uv** | ✅ Completed | `backend/pyproject.toml`<br>`backend/uv.lock`<br>`backend/Dockerfile` | • Replace stdlib `venv` + `requirements.txt`/`requirements-dev.txt` with `uv` (pyproject.toml + uv.lock)<br>• Docker build uses `uv sync --frozen --no-dev`<br>• Activation/run commands documented in `llm.md`, `CLAUDE.md`, `wip.md` |

---

## 3. Verified 100% Free API Data Architecture

All feeds have been verified locally to require **zero paid subscriptions**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       100% FREE & OPEN DATA PIPELINES                       │
├──────────────────────┬──────────────────────┬───────────────────────────────┤
│ Domain               │ Free Provider        │ Key Ingested Series           │
├──────────────────────┼──────────────────────┼───────────────────────────────┤
│ Equities & Indices   │ Yahoo Finance (free) │ NIFTY 50/500, Sector Indices, │
│                      │                      │ 500+ NSE/BSE OHLCV & Volume   │
│ Live NSE Breadth     │ NSE India (curl_cffi)│ Advances/Declines, Status, OI │
│ Fundamentals         │ Screener.in          │ ROCE, D/E, Piotroski, Altman Z│
│ Global Inter-Market  │ Yahoo Finance (free) │ Brent Crude, USD/INR, US 10Y, │
│                      │                      │ Gold, India VIX, US Dollar Idx│
│ Macro Indicators     │ World Bank Open API  │ India Real GDP, CPI Inflation │
│ Monetary Policy      │ RBI Public Releases  │ Repo Rate (6.50%), Reserves   │
│ News & Catalysts     │ Google News RSS      │ Live Indian Financial Press   │
│ Sentiment Inference  │ Local NLTK VADER     │ CPU-based sentiment (0 cost)  │
└──────────────────────┴──────────────────────┴───────────────────────────────┘
```

---

## 4. Active Stitch MCP Screens (`stitch.google.com`)

- **Project ID**: `projects/17247566464105962351` (*StockPortfolio Analytics Dashboard*)
- **Target Screens**:
  - `876a35da55a14277b120acdbeb5b2ce9`: "Macro Economics & Govt Bonds" → Mapped to `/macro`
  - `ed0e7c184fab4af895b199c8c68f7621`: "Stock Recommendations & Ratings" → Mapped to `/recommendations`
  - `2f45b3c2d4784c91aa97c99cc5b696b0`: "Strategy Lab & Backtesting" → Mapped to `/lab`
  - `/pulse`: To be generated via Stitch MCP `generate_screen_from_text`

---

## 5. Non-Negotiable Engineering Guardrails

1. **Read-Only & Paper Trading Only**: No broker live-execution endpoints.
2. **Zero Invented / Mock Data**: Upstream errors must return `{ "available": false, "reason": "..." }`. Never substitute simulated random walks.
3. **No Direct Price Prediction**: Rank forward 10-day excess returns ($R_{i, t+10} - R_{\text{NIFTY50}, t+10}$), not raw price targets.
4. **Leakage Prevention**: Purged Walk-Forward Cross-Validation with 5-day embargoes against naive baselines.
5. **Indian Tax Rules**: Trade exits must calculate STCG @ 20% and LTCG @ 12.5% above ₹1.25L exemption (`quant/tax.py`).
6. **Obsidian Craft Design**: Zinc canvas (`#09090b`), hairline borders (`rgba(255,255,255,0.08)`), two typography voices (Inter + JetBrains Mono), zero decorative neon.

---

## 6. Local Development & Operational Commands

```bash
# Docker local containerized stack
docker compose up --build -d      # db, redis, migrate, api :8001, worker, frontend :3001
docker compose logs -f worker     # inspect scheduler execution
docker compose run --rm migrate   # apply Alembic migrations

# Local backend (without Docker) - deps/venv managed by uv, not pip
cd backend
uv sync                           # first time / after a dependency change
.\.venv\Scripts\Activate.ps1      # or: uv run uvicorn app.main:app --port 8001 --reload
uvicorn app.main:app --port 8001 --reload

# Local frontend (Next.js 16)
cd frontend
pnpm dev                          # http://localhost:3000

# Automated tests
cd backend && uv run pytest -v
```
