# stockportfolio.in — Work In Progress (WIP)

> **Active Sprint**: Phase 16 — Tax Rebalancing, Holdings Catalysts, AI Monthly Memo & Layout Boundaries  
> **Last Updated**: 2026-09-09  
> **Repository**: [`stockportfolio.in`](file:///c:/Users/abhi3/Documents/work/stockportfolio_in)  
> **Current Status**: 🟢 **Active**

---

## 1. Executive Summary of Current State

All fundamental, quant, macro, and UI foundations (**Phases 0 through 16**) are completed:
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
- ✅ India Macro transmission engine & regime classifier (`/macro`)
- ✅ NSE Live Market Pulse & Real-Time Scanners (`/pulse`)
- ✅ Quant ML Alpha Factor Matrix & Purged Walk-Forward Ranker (`/recommendations`)
- ✅ Backend dependency management modernized with `uv` (`pyproject.toml`, `uv.lock`)
- ✅ Institutional Light Theme overhaul & Ant Design Pro console layout (`DESIGN.md`, `globals.css`)
- ✅ Indian tax-aware rebalancer, holdings news catalysts, verified AI monthly memo & boundary polish (`/portfolio`)

---

## 2. Phase 14 Milestone Checklist & Task Breakdown

| # | Task / Deliverable | Status | Target File(s) | Key Specifications |
|---|---|:---:|---|---|
| **14.1** | **India Macro & Inter-Market Transmission Engine** | ✅ Completed | `backend/app/macro.py`<br>`backend/tests/test_macro.py` | • Ingest `BZ=F`, `INR=X`, `^TNX`, `GC=F`, `^INDIAVIX`<br>• Crude Pressure Index (`BENIGN`, `MODERATE`, `ELEVATED`)<br>• FX Rupee velocity tailwinds (IT/Pharma)<br>• Macro Regime Classifier (Goldilocks, Imported Inflation, Risk-Off)<br>• NIFTY Sector Relative Momentum vs NIFTY 50 |
| **14.2** | **NSE Live Market Pulse & Real-Time Scanners** | ✅ Completed | `backend/app/market_pulse.py`<br>`backend/tests/test_market_pulse.py` | • Live NSE Advance/Decline breadth ratio<br>• Volume Shockers ($Volume_t \ge 2\times SMA_{20}(Volume)$)<br>• 52-Week High Breakouts with VCP consolidation filter |
| **14.3** | **Quant ML Alpha Factor Matrix & Ranker** | ✅ Completed | `backend/app/ml/dataset.py`<br>`backend/app/ml/labeling.py`<br>`backend/app/ml/validation.py`<br>`backend/app/ml/models/`<br>`backend/app/ml/pipeline.py` | • Point-in-time factor matrix augmented with Macro Betas<br>• Target: Forward 10-day excess return ($R_{i, t+10} - R_{\text{NIFTY}, t+10}$)<br>• Purged Walk-Forward CV with 5-day post-test embargo<br>• Honest benchmark against naive majority baseline<br>• Pure NumPy/SciPy L2 Ridge ranker + LightGBM fallback |
| **14.4** | **REST API Routes & Status Integration** | ✅ Completed | `backend/app/routes/macro.py`<br>`backend/app/routes/market_pulse.py`<br>`backend/app/routes/ml.py` | • `/api/macro` (regime, inter-market tickers, sector rotation)<br>• `/api/market-pulse` (breadth, volume shockers, 52W breakouts)<br>• `/api/ml/rankings` (Decile 1–10, ATR $+2\sigma/-1.5\sigma$ levels)<br>• Schema validation with sub-500ms cached execution |
| **14.5** | **Google Stitch MCP UI Redesign** | ✅ Completed | `frontend/src/app/macro/`<br>`frontend/src/app/pulse/`<br>`frontend/src/app/recommendations/` | • Connect to Stitch Project `17247566464105962351`<br>• Port Screen `876a35da...` → `/macro` console<br>• Port Screen `ed0e7c18...` → `/recommendations` AI Radar Tab<br>• Generate `/pulse` screen via Stitch MCP tool<br>• Match Obsidian Craft styling standards |
| **14.6** | **Automated Test Suite & Verification** | ✅ Completed | `backend/tests/test_macro.py`<br>`backend/tests/test_market_pulse.py`<br>`backend/tests/test_ml_*.py` | • 100% test coverage on calculations and zero-leakage<br>• Verified free API endpoints without network failure traps<br>• 185/185 tests passing across entire backend suite |
| **14.7** | **Backend Dependency Management Migration to uv** | ✅ Completed | `backend/pyproject.toml`<br>`backend/uv.lock`<br>`backend/Dockerfile` | • Replace stdlib `venv` + `requirements.txt`/`requirements-dev.txt` with `uv` (pyproject.toml + uv.lock)<br>• Docker build uses `uv sync --frozen --no-dev`<br>• Activation/run commands documented in `llm.md`, `CLAUDE.md`, `wip.md` |

---

## 3. Phase 15 Milestone Checklist: Institutional Light-Theme & Enterprise Console

> **Active Sprint**: Phase 15 — Institutional Light-Theme Overhaul & Ant Design Pro / Enterprise Tailwind Console Redesign  
> **Design Philosophy**: Ant Design Pro + Material UI 3 + Tailwind Enterprise. Zero dark neon AI-slop, zero cyan/purple glows.  
> **Stitch Project**: `projects/7660403129280757824` ("StockPortfolio Institutional Pro - Light Enterprise")

| # | Task / Deliverable | Status | Target File(s) | Key Specifications |
|---|---|:---:|---|---|
| **15.1** | **Institutional Light Foundations & Design Tokens** | ✅ Completed | `DESIGN.md`<br>`frontend/src/app/globals.css` | • Soft slate canvas (`#F8FAFC`), pure white cards (`#FFFFFF`), 1px slate borders (`#E2E8F0`)<br>• Restrained financial semantics: Emerald (`#059669`), Crimson (`#DC2626`), Sapphire (`#2563EB`)<br>• Monospace tabular numerals (`font-variant-numeric: tabular-nums`) |
| **15.2** | **Executive Top Command & Live Market Strip** | ✅ Completed | `frontend/src/components/TopBar.tsx`<br>`frontend/src/app/layout.tsx` | • Real-time benchmark strip: NIFTY 50, SENSEX, INDIA VIX, BRENT, USD/INR<br>• Universal symbol search bar (`Cmd+K` jump to `/analyse/[ticker]`)<br>• Fyers live broker connectivity badge and quick rebalance trigger |
| **15.3** | **Institutional Quant Alpha & Home Terminal** | ✅ Completed | `frontend/src/app/page.tsx` | • 4 KPI Metric Cards: Valuation, Health Score, 1-Day 95% VaR, Active Macro Regime<br>• High-density Ant Design Pro-style table with segmented tabs (Positions, Decile 1, Shockers)<br>• 1,000-Path Monte Carlo Wealth Cone SVG & Inter-market Transmission gauge |
| **15.4** | **Portfolio Intelligence Console Light Refactor** | ✅ Completed | `frontend/src/app/portfolio/`<br>`AllocationBars.tsx`<br>`HealthRadar.tsx`<br>`WealthCone.tsx`<br>`AiMemo.tsx` | • Convert `/portfolio` tabs to daylight-readable white cards & clean slate containers<br>• High-contrast radar charts, SVG wealth cones, and tax-loss harvesting panels |
| **15.5** | **Research & Alpha Discovery Consoles Refactor** | ✅ Completed | `frontend/src/app/recommendations/`<br>`frontend/src/app/pulse/`<br>`frontend/src/app/screener/`<br>`frontend/src/app/analyse/` | • Clean Ant Design tables for ML Alpha decile rankings, ATR target channels<br>• Light-mode Advance/Decline breadth meter and volume shocker cards<br>• Forensic screener sliders and ticker deep-dive cards |
| **15.6** | **Quant, Derivatives & Execution Consoles Refactor** | ✅ Completed | `frontend/src/app/macro/`<br>`frontend/src/app/quant/`<br>`frontend/src/app/options/`<br>`frontend/src/app/lab/`<br>`frontend/src/app/paper/` | • Inter-market transmission dials and macro regime classifier<br>• HRP dendrogram clustering & option chain Max Pain strike matrix<br>• Event-driven strategy backtester v2 & virtual paper trading ledger |
| **15.7** | **Stitch MCP Screen Generation & Build Verification** | ✅ Completed | `pnpm build`<br>`uv run pytest tests/`<br>`walkthrough.md` | • Stitch Project `7660403129280757824` Screen `4e946d8a...` generated<br>• Full TypeScript build validation (15/15 routes passed) & 185/185 pytest suite passed |

---

## 4. Phase 16 Milestone Checklist: Tax Rebalancing, Catalysts, AI Memo & Layout Boundaries

> **Active Sprint**: Phase 16 — Tax Rebalancing, Holdings Catalysts, AI Monthly Memo & Layout Boundaries Polish  
> **Status**: 🟢 **In Progress**  
> **Scope**: Indian tax-aware rebalancing optimization, zero-noise holdings news feed, deterministic verified AI memo, and project-wide boundary/padding standardization.

| # | Task / Deliverable | Status | Target File(s) | Key Specifications |
|---|---|:---:|---|---|
| **16.1** | **Indian Tax-Aware Rebalancer Engine** | ✅ Completed | `HealthRadar.tsx`<br>`backend/app/quant/tax.py`<br>`backend/app/quant/rebalance.py` | • STCG @ 20% (< 365d) and LTCG @ 12.5% (> ₹1.25L exemption)<br>• Zero-Tax Cash Inflow Mode directing fresh SIP capital to underweight assets with ₹0 sales<br>• Proximity warning alert for positions within 30 days of LTCG threshold<br>• Order execution sheet with actionable units, prices, and tax impact |
| **16.2** | **Holdings News Catalyst & Corporate Filings** | ✅ Completed | `HealthRadar.tsx`<br>`backend/app/routes/portfolio.py`<br>`backend/app/news.py` | • Zero generic market noise: whitelisted strictly to symbols in active portfolio<br>• Free Google News RSS ingestion & local NLTK VADER sentiment scoring<br>• Catalyst tags (Earnings, Regulatory/SEBI, Board Meeting, Dividend, Expansion)<br>• Daylight chip badges and monospace ticker tags |
| **16.3** | **Deterministic-First AI Monthly Memo** | ✅ Completed | `AiMemo.tsx`<br>`backend/app/routes/ai.py` | • LLM acts strictly as narrator over deterministic computed quant figures<br>• Fact verification regex engine cross-referencing all numbers against computed metrics<br>• Explicit status badge (Verified vs Partial Warning)<br>• Macro regime, sector concentration (HHI), and crash simulator audit dimensions |
| **16.4** | **Project-Wide Visual Boundaries & Layout Polish** | ✅ Completed | `globals.css`<br>`HealthRadar.tsx`<br>`AddHoldingForm.tsx`<br>`PortfolioDashboard.tsx`<br>`OptionsConsole.tsx` | • Standardized `.glass-panel` default padding to 20px in `globals.css`<br>• Padded hero containers (`HealthRadar`, `AddHoldingForm`, `OptionsConsole`)<br>• Replaced legacy dark input/select styles with daylight `#F8FAFC` slate inputs<br>• High-contrast alert banners (`#EFF6FF` info, `#FEF2F2` error) |

---

## 5. Verified 100% Free API Data Architecture

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

## 6. Active Stitch MCP Screens (`stitch.google.com`)

- **Project ID**: `projects/17247566464105962351` (*StockPortfolio Analytics Dashboard*)
- **Target Screens**:
  - `876a35da55a14277b120acdbeb5b2ce9`: "Macro Economics & Govt Bonds" → Mapped to `/macro`
  - `ed0e7c184fab4af895b199c8c68f7621`: "Stock Recommendations & Ratings" → Mapped to `/recommendations`
  - `2f45b3c2d4784c91aa97c99cc5b696b0`: "Strategy Lab & Backtesting" → Mapped to `/lab`
  - `/pulse`: Generated via Stitch MCP `generate_screen_from_text`
- **Light Theme Project ID**: `projects/7660403129280757824` (*StockPortfolio Institutional Pro - Light Enterprise*)

---

## 7. Non-Negotiable Engineering Guardrails

1. **Read-Only & Paper Trading Only**: No broker live-execution endpoints.
2. **Zero Invented / Mock Data**: Upstream errors must return `{ "available": false, "reason": "..." }`. Never substitute simulated random walks.
3. **No Direct Price Prediction**: Rank forward 10-day excess returns ($R_{i, t+10} - R_{\text{NIFTY50}, t+10}$), not raw price targets.
4. **Leakage Prevention**: Purged Walk-Forward Cross-Validation with 5-day embargoes against naive baselines.
5. **Indian Tax Rules**: Trade exits must calculate STCG @ 20% and LTCG @ 12.5% above ₹1.25L exemption (`quant/tax.py`).
6. **Institutional Light-Theme Design**: Soft slate canvas (`#F8FAFC`), pure white cards (`#FFFFFF`), hairline slate borders (`#E2E8F0`), two typography voices (Inter + JetBrains Mono), restrained financial semantics (Emerald / Crimson / Sapphire), zero dark neon AI-slop.

---

## 8. Local Development & Operational Commands

```bash
# Docker local containerized stack
# Note: Host ports are isolated to avoid colliding with other local services:
# - DB: 5434:5432 (pgvector PostgreSQL 16)
# - Redis: 6380:6379 (Redis 7)
# - API: 8002:8001 (FastAPI)
# - Frontend: 3001:3000 (Next.js 16)
docker compose up --build -d      # db, redis, migrate, api :8002, worker, frontend :3001
docker compose logs -f worker     # inspect scheduler execution
docker compose run --rm migrate   # apply Alembic migrations

# Local backend (without Docker) - deps/venv managed by uv, not pip
cd backend
uv sync                           # first time / after a dependency change
.\.venv\Scripts\Activate.ps1      # or: uv run uvicorn app.main:app --port 8001 --reload
uv run uvicorn app.main:app --port 8001 --reload

# Local frontend (Next.js 16)
cd frontend
pnpm dev                          # http://localhost:3000

# Automated tests (Full suite - 185 tests passing)
cd backend && uv run pytest -p no:cacheprovider tests/
```

---

## 9. Verification & Operational Evidence Log (2026-09-09)

1. **Backend Verification via `uv`**:
   - `uv run pytest -p no:cacheprovider tests/` passed cleanly with **185 passed** in ~25s (0 failures, 0 errors).
   - Includes full unit test coverage for Phase 14: Macro Engine (`test_macro.py`), Live Market Pulse (`test_market_pulse.py`), Quant ML dataset/labeling/validation/pipeline (`test_ml_*.py`), and REST endpoints (`test_*_routes.py`).

2. **Frontend Type Check & Build**:
   - `pnpm exec tsc --noEmit` passed with **0 errors**.
   - Next.js 16 Turbopack production build succeeded, compiling all 15 routes (`/`, `/macro`, `/pulse`, `/recommendations`, `/lab`, `/quant`, `/screener`, `/options`, `/paper`, `/portfolio`, `/funds`, etc.).

3. **Docker Multi-Container Stack (Verified & Healthy)**:
   - Configured non-conflicting host port bindings in [`docker-compose.yml`](file:///c:/Users/abhi3/Documents/work/stockportfolio_in/docker-compose.yml) to avoid colliding with other local services:
     - `db`: `5434:5432` (pgvector PostgreSQL 16) — **Healthy**
     - `redis`: `6380:6379` (Redis 7) — **Healthy**
     - `migrate`: Alembic upgrade head — **Completed (exit 0)**
     - `api`: `8002:8001` (FastAPI) — **Healthy**, `/status` returns `subsystems.database: true`, `subsystems.redis.reachable: true`, `subsystems.job_store: redis`
     - `worker`: APScheduler in Asia/Kolkata timezone with 5 scheduled nightly jobs (21:30, 22:00, 22:30, 22:45, 23:00 IST) — **Up & Active**
     - `frontend`: `3001:3000` (Next.js 16) — **Up**, serving `/macro`, `/pulse`, `/recommendations`, etc. (HTTP 200)
   - Integrated `uv` in backend Dockerfile (`ghcr.io/astral-sh/uv:0.12.7`) with frozen lockfile sync and baked VADER sentiment lexicon.

4. **Phase 15 & 16 Visual Boundary & Tax Polish Verification**:
   - **Padding & Container Boundaries**: Base `.glass-panel`, `.portfolio-card`, and `.stat-card` updated to `padding: 20px` in `globals.css`. Explicit 22px–26px hero padding added in `HealthRadar.tsx`, `AddHoldingForm.tsx`, `PortfolioDashboard.tsx`, `AiMemo.tsx`, and `OptionsConsole.tsx`.
   - **Indian Tax Engine**: Verified Budget 2024–25 tax calculations (STCG 20%, LTCG 12.5% over ₹1.25L exemption, zero-tax cash inflow routing with ₹0 sales).
   - **Holdings News Catalyst**: Verified company-whitelisted Google News RSS feed + local VADER sentiment classification with zero generic market noise.
   - **AI Monthly Memo**: Verified deterministic metric verification guard cross-checking numbers before rendering narrative.



