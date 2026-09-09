# Implementation Plan — Phase 14: India Macro, Inter-Market Radar, Quant ML Alpha & Stitch MCP UI Redesign

A zero-leakage quantitative intelligence and recommendation system focused on the **Indian stock market & macroeconomic transmission channels**, powered entirely by **verified 100% free & open APIs**, with the **frontend UI redesign executed via Google Stitch (`stitch.google.com`) MCP tools**.

---

## 1. Goal Description

The objective is to answer:
> *"What is happening in the Indian market right now, which macro currents are moving it, which stocks are breaking out or undervalued, why, and should I BUY/HOLD/SELL?"*

To achieve this without falling into the retail prediction traps (proven to fail out-of-sample in projects like `StockIntel`), Phase 14 builds:
1. **100% Free & Open Data Pipelines**: Zero paid subscriptions or proprietary data locks. Runs on Yahoo Finance, NSE official endpoints via `curl_cffi`, Screener.in, World Bank Open Data API, and Google News RSS with local VADER sentiment.
2. **Indian Macro & Inter-Market Transmission Engine (`macro.py`)**: Models how Brent Crude (`BZ=F`), USD/INR (`INR=X`), US 10Y Yields (`^TNX`), and India VIX (`^INDIAVIX`) cascade into Indian sector rotation and stock-level alpha.
3. **Live NSE Market Pulse & Scanners (`market_pulse.py`)**: Advances/Declines breadth, Volume Shockers ($Volume_t > 2\times SMA_{20}$), and 52-Week Breakouts.
4. **Quant ML Alpha Factor Ranker (`app/ml/`)**: Cross-sectional forward 10-day relative excess return ranking over NIFTY 50 ($R_{i, t+10} - R_{\text{NIFTY50}, t+10}$), validated under Marcos López de Prado's Purged Walk-Forward Cross-Validation with temporal embargoing and an honest naive baseline test.
5. **Trade Structuring & Indian Tax Integration**: ATR-scaled Entry, Target ($+2.0\sigma$), and Stop-Loss ($-1.5\sigma$) levels, integrated into `/recommendations` with Indian STCG @ 20% and LTCG @ 12.5% exit pricing.
6. **Stitch MCP UI Redesign (`stitch.google.com`)**: Connects to active Stitch project `17247566464105962351` to port and generate production screens for `/macro`, `/pulse`, and `/recommendations`.

---

## 2. User Review Required

> [!IMPORTANT]
> **100% Free API Guarantee (Zero Mandatory Subscriptions)**:
> Every data feed used across Phase 14 has been verified to be completely free and open. The platform does not require paid third-party market data subscriptions (Bloomberg, Refinitiv, or paid News APIs).
> - Market Data: Yahoo Finance (no key) + NSE official API via `curl_cffi` (no key).
> - Fundamentals: Screener.in via `curl_cffi` (no key).
> - Macroeconomics: World Bank Open REST API (no key) + FRED (free key) + RBI releases.
> - News: Google News RSS for Indian equities (no key) + Local VADER (runs on CPU in container).

> [!NOTE]
> **Stitch MCP Project Binding**:
> UI layouts are synchronized with active Stitch project `projects/17247566464105962351` (*StockPortfolio Analytics Dashboard*), translating Stitch's HTML/Tailwind specifications into Next.js 16 + shadcn/ui React components following [`DESIGN.md`](file:///c:/Users/abhi3/Documents/work/stockportfolio_in/DESIGN.md).

---

## 3. Verified Free & Open API Architecture

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

## 4. Architectural Overview & System Flow

```mermaid
graph TD
    subgraph 1. Free & Open Data Ingestion
        YF[Yahoo Finance: BZ=F, INR=X, ^TNX, ^INDIAVIX, NSE Equities] --> MACRO[macro.py: India Macro Engine]
        NSE_API[NSE India via curl_cffi: Advances/Declines] --> PULSE[market_pulse.py: Market Pulse Engine]
        WB_API[World Bank Open API: India GDP & Inflation] --> MACRO
        SCR[Screener.in via curl_cffi: ROCE, D/E, Piotroski] --> FUND[app/fundamentals.py]
        GNEWS[Google News RSS + Local VADER] --> NEWS[app/news.py]
    end

    subgraph 2. Macro Transmission & Sector Rotation
        MACRO --> M_REG[Macro Regime: Goldilocks vs Imported Inflation vs Risk-Off]
        MACRO --> M_BETA[Stock Macro Betas: Crude Beta, FX Beta, Yield Beta]
        MACRO --> M_ROT[NIFTY Sector Relative Strength vs NIFTY 50]
    end

    subgraph 3. Quant ML Alpha Engine backend/app/ml/
        M_BETA & M_ROT & FUND --> FEAT[dataset.py: Augmented Factor Matrix]
        FEAT --> VAL[validation.py: Purged Walk-Forward Splitter]
        VAL --> RNK[models/linear.py & models/gbm.py: Cross-Sectional Ranker]
        RNK --> CALIB[Calibration & Honest Abstention Gate]
    end

    subgraph 4. Trade Structuring & Indian Tax Integration
        CALIB --> DEC[Decile 1 to 10 Ranks]
        DEC --> ATR[ATR Target +2σ & Stop -1.5σ]
        ATR --> TAX[quant/tax.py: Indian STCG @ 20% & LTCG @ 12.5%]
    end

    subgraph 5. Stitch MCP Cloud & Next.js UI Redesign
        STITCH[Stitch Project 17247566464105962351] --> SC_MACRO[Screen 876a35da: Macro & Govt Bonds]
        STITCH --> SC_REC[Screen ed0e7c18: Stock Recommendations]
        STITCH --> SC_PULSE[Generated Screen: Market Pulse & Shockers]
        
        SC_MACRO --> UI_MACRO[/macro: Macro & Inter-Market Console]
        SC_PULSE --> UI_PULSE[/pulse: Live NSE Market Pulse Console]
        SC_REC --> UI_REC[/recommendations: AI Alpha Radar Tab]
    end
```

---

## 5. Detailed Component Specifications

### Track 1: Indian Macro & Inter-Market Engine (`backend/app/macro.py`)
- **Observable Tickers**:
  - `BZ=F` (Brent Crude Oil)
  - `INR=X` (USD/INR Exchange Rate)
  - `^TNX` (US 10-Year Treasury Yield)
  - `GC=F` (Gold)
  - `^INDIAVIX` (India VIX)
  - Sector Indices: `^NSEBANK`, `^CNXIT`, `^CNXAUTO`, `^CNXPHARMA`, `^CNXFMCG`, `^CNXMETAL`, `^CNXENERGY`, `^CNXREALTY`.
- **Calculations**:
  - **Crude Pressure Index**: 5-day and 20-day annualized rate of change in Brent Crude (categorized into `BENIGN`, `MODERATE`, `ELEVATED_PRESSURE`).
  - **Currency Headwind/Tailwind**: 20-day Rupee trajectory scoring export advantage (IT/Pharma) vs import pressure.
  - **Macro Regime Classification**:
    - `GOLDILOCKS_EXPANSION`: Low Crude + Stable INR + Low VIX (< 14).
    - `IMPORTED_INFLATION_PRESSURE`: High Crude + Weak INR + Rising Yields.
    - `GLOBAL_RISK_OFF`: Spiking VIX + US Dollar surge + Capital flight.
    - `DEFENSIVE_CONSOLIDATION`: Elevated VIX + Choppy Nifty.
  - **NIFTY Sector Rotation Matrix**: Ranked relative momentum of sectors vs. NIFTY 50.

---

### Track 2: Live Market Pulse & Scanning Engine (`backend/app/market_pulse.py`)
- **Advance/Decline Breadth**: Real-time ratio across NIFTY 50 / 500 via NSE live feed.
- **Volume Shockers** (inspired by `PKScreener`):
  $$\text{Volume Surge Ratio} = \frac{\text{Volume}_t}{\text{SMA}_{20}(\text{Volume})} \ge 2.0 \quad \text{with } \text{Return}_t > 0$$
- **52-Week Breakout Radar**:
  $$\text{Within 52W High} = \frac{\text{Price}_t}{\text{Max}_{252}(\text{High})} \ge 0.98 \quad \text{filtered by VCP consolidation}$$

---

### Track 3: Quant ML Alpha Engine (`backend/app/ml/`)
- **`dataset.py`**: Point-in-time factor matrix augmented with Macro Betas ($\beta_{\text{Crude}}, \beta_{\text{USDINR}}$) and Screener.in fundamentals.
- **`labeling.py`**: Forward 10-day relative excess return target ($R_{i, t+10} - R_{\text{NIFTY50}, t+10}$) + volatility-scaled ternary bands ($\pm 0.5\sigma_h$).
- **`validation.py`**: Purged walk-forward cross-validation with 5-day post-test embargo and naive baseline test.
- **`models/linear.py`**: L2-regularized ranker using pure NumPy/SciPy.
- **`models/gbm.py`**: LightGBM Ranker with graceful fallback.
- **`pipeline.py`**: Decile 1–10 ranking, ATR trade levels, driver pills, and calibration gate.

---

### Track 4: Stitch MCP UI Redesign Workflow (`mcp/stitch`)
- **Design System Synchronization**:
  - Upload [`DESIGN.md`](file:///c:/Users/abhi3/Documents/work/stockportfolio_in/DESIGN.md) to project `17247566464105962351` via `upload_design_md`.
- **Screen Extraction**:
  - Screen `876a35da55a14277b120acdbeb5b2ce9`: Extract *Macro Health Matrix* and *Sovereign Debt Explorer* for `/macro`.
  - Screen `ed0e7c184fab4af895b199c8c68f7621`: Extract *Stock Recommendations & Ratings* for `/recommendations`.
  - Screen `2f45b3c2d4784c91aa97c99cc5b696b0`: Extract *Strategy Lab & Backtesting* for `/lab`.
- **Screen Generation**:
  - Generate `/pulse` screen via Stitch MCP tool `generate_screen_from_text`.
- **Frontend Implementation**:
  - Implement in Next.js 16 + shadcn/ui with Obsidian craft tokens.

---

## 6. Verification Plan

### Automated Tests (`backend/tests/`)
1. **Free API & Macro Tests** (`tests/test_macro.py`):
   - Test Crude Pressure Index calculation.
   - Test USD/INR trajectory classification.
   - Test Macro Regime resolution.
   - Test Sector relative momentum vs NIFTY 50.
2. **Market Pulse Tests** (`tests/test_market_pulse.py`):
   - Test advance/decline ratio calculation.
   - Test volume shocker detection (`Volume > 2x 20d SMA`).
   - Test 52-Week breakout detection.
3. **Quant ML Labeling & Validation Tests** (`tests/test_ml_labeling.py`, `tests/test_ml_validation.py`):
   - Verify forward excess return math and zero-leakage shifting.
   - Verify volatility-scaled ternary band stability.
   - Test purged & embargoed walk-forward split validation.
4. **Pipeline & Model Tests** (`tests/test_ml_pipeline.py`):
   - Test linear ranker convergence on synthetic data.
   - Test decile assignment, ATR trade levels, and driver pills.
   - Verify execution latency < 500ms.
5. **API Route Tests** (`tests/test_macro_routes.py`, `tests/test_market_pulse_routes.py`, `tests/test_ml_routes.py`):
   - Verify HTTP 200 responses and Pydantic schema validation.

### Manual Verification
1. **API Verification**:
   - `curl http://127.0.0.1:8001/api/macro` → Check Crude, USD/INR, VIX, US 10Y, and sector rotation.
   - `curl http://127.0.0.1:8001/api/market-pulse` → Check advance/decline, volume shockers, breakouts.
   - `curl http://127.0.0.1:8001/api/ml/rankings` → Check Decile 1–10 rankings and ATR trade levels.
2. **Stitch UI Verification**:
   - Navigate to `http://localhost:3000/macro` → Verify Macro Health Matrix and live tickers match Stitch screen `876a35da...`.
   - Navigate to `http://localhost:3000/pulse` → Verify Volume Shockers and Breakouts match Stitch generated design.
   - Navigate to `http://localhost:3000/recommendations` → Verify AI Alpha Radar tab matches Stitch screen `ed0e7c18...`.
