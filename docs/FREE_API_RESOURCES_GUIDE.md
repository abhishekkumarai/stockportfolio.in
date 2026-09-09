# Free & Open API Resources for Indian Stocks, Inter-Markets & Macroeconomics

A comprehensive, production-tested catalog of **100% free, open, and no-cost APIs** powering the data pipelines for **`stockportfolio.in`**.

---

## 1. Summary Matrix of Free Data Sources

| Domain | Provider / Endpoint | Auth / Key Needed? | Rate Limit / Quota | Primary Data Ingested |
|---|---|---|---|---|
| **NSE Equities & Indices** | **Yahoo Finance (`yfinance`)** | ❌ None (No key) | Generous / Batched | OHLCV daily/intraday, volumes, market cap, Beta, 52W high/low for all `.NS` / `.BO` tickers and NIFTY indices |
| **Live NSE Market Breadth** | **NSE Official APIs (`nseindia.com`)** | ❌ None (Cookie handshake via `curl_cffi`) | ~5 req/sec (polite) | Advances/Declines, Live Nifty 50 constituents, Option Chain, India VIX |
| **Corporate Fundamentals** | **Screener.in (via `curl_cffi`)** | ❌ None (No key) | Bounded worker pool (3 workers) | 10-year P&L, balance sheets, ROCE, ROE, Debt/Equity, Piotroski F-Score, Altman Z-Score, shareholding |
| **Indian Mutual Funds** | **MFAPI.in (`api.mfapi.in`)** | ❌ None (No key) | Unlimited / Open | Historical NAVs, scheme master, AMFI codes, category returns |
| **Global Inter-Markets & Commodities** | **Yahoo Finance Commodities/FX** | ❌ None (No key) | Generous / Batched | Brent Crude (`BZ=F`), Gold (`GC=F`), USD/INR (`INR=X`), US 10Y Yield (`^TNX`), US Dollar Index (`DX-Y.NYB`) |
| **Global Macroeconomics** | **World Bank Open Data API (`api.worldbank.org`)** | ❌ None (No key) | Open public REST | India Real GDP growth, CPI inflation, external debt, Current Account Balance |
| **US & International Macro** | **FRED (Federal Reserve Economic Data)** | ✅ Free key (free tier) | 120 req/min | US Treasury Yield Curve, Global Oil Benchmarks, Fed Funds rate, global policy uncertainty |
| **Indian Macro & Monetary Policy** | **RBI Public Releases / DBIE Portal** | ❌ None (Open web data) | Static daily/weekly | RBI Repo Rate, Cash Reserve Ratio (CRR), Forex Reserves, 10Y Sovereign G-Sec yield |
| **News & Live Catalysts** | **Google News RSS (Indian Equities)** | ❌ None (No key) | Open RSS feed | Real-time Indian financial press (Economic Times, Livemint, Moneycontrol, Business Standard) |
| **Sentiment Inference** | **NLTK VADER / Local Model** | ❌ None (Local container) | Unlimited (runs on CPU) | Headline sentiment score (-1.0 to +1.0) with zero external network overhead |

---

## 2. In-Depth Provider Specifications & Integration Patterns

### 1. Market Data: Yahoo Finance (`yfinance`)
- **Cost**: 100% Free.
- **Authentication**: None.
- **Integration**: Handled via `backend/app/yf_frames.py`.
- **Verified Tickers**:
  - Equities: `RELIANCE.NS`, `TCS.NS`, `HDFCBANK.NS`, `INFY.NS`, etc.
  - Sector Indices: `^NSEBANK`, `^CNXIT`, `^CNXAUTO`, `^CNXPHARMA`, `^CNXFMCG`, `^CNXMETAL`, `^CNXENERGY`, `^CNXREALTY`.
  - Benchmarks: `^NSEI` (NIFTY 50), `^CRSLDX` (NIFTY 500), `^CNXSC` (NIFTY Smallcap 100).
  - Inter-Markets: `BZ=F` (Brent Crude), `INR=X` (USD/INR), `^TNX` (US 10Y), `GC=F` (Gold), `^INDIAVIX` (India VIX).
- **Caching Strategy**: OHLCV frames are cached in-memory and persisted to SQLite/Parquet with a 1-hour TTL for historical bars and 60-second TTL for live quotes.

---

### 2. Live NSE Market Status & Breadth (`nseindia.com`)
- **Cost**: 100% Free.
- **Authentication**: None required. Requires standard browser user-agent and initial cookie handshake from `https://www.nseindia.com` before requesting API endpoints.
- **Library**: `curl_cffi` (impersonating Chrome/Edge TLS fingerprint to avoid Cloudflare/bot challenge blocks).
- **Key Endpoints**:
  - `https://www.nseindia.com/api/marketStatus` (Live market state, trading status).
  - `https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050` (Advance/decline count, total traded volume).
  - `https://www.nseindia.com/api/allIndices` (Real-time sectoral performance).
  - `https://www.nseindia.com/api/historical/vix` (India VIX history).

---

### 3. Corporate Fundamentals: Screener.in
- **Cost**: 100% Free.
- **Authentication**: None.
- **Integration**: Already active in `backend/app/screener.py` and `backend/app/fundamentals.py`.
- **Data Retrieved**:
  - Valuation: P/E, P/B, EV/EBITDA, Market Cap.
  - Capital Efficiency: ROCE (Return on Capital Employed), ROE, Operating Margin (OPM).
  - Balance Sheet Health: Debt-to-Equity, Interest Coverage Ratio, Current Ratio.
  - Forensic Diagnostics: 9-point **Piotroski F-Score**, **Altman Z-Score** distress ranking.
  - Ownership: Promoter holding, FII holding, DII holding, pledged shares.

---

### 4. Global Macroeconomics: World Bank Open REST API
- **Cost**: 100% Free.
- **Authentication**: **No API key required.**
- **Format**: Clean JSON REST endpoint.
- **Key Series for India**:
  - Real GDP Growth YoY: `http://api.worldbank.org/v2/country/IND/indicator/NY.GDP.MKTP.KD.ZG?format=json`
  - Inflation (Consumer Price Index): `http://api.worldbank.org/v2/country/IND/indicator/FP.CPI.TOTL.ZG?format=json`
  - Current Account Balance (% of GDP): `http://api.worldbank.org/v2/country/IND/indicator/BN.CAB.XOKA.GD.ZS?format=json`
- **Verified Response**:
  ```json
  [
    {"indicator": {"id": "NY.GDP.MKTP.KD.ZG", "value": "GDP growth (annual %)"}},
    [
      {"date": "2025", "value": 7.57},
      {"date": "2024", "value": 7.10},
      {"date": "2023", "value": 7.21}
    ]
  ]
  ```

---

### 5. US & International Macro: FRED (Federal Reserve Economic Data)
- **Cost**: 100% Free.
- **Authentication**: Free API Key (sign up in 30 seconds at `fred.stlouisfed.org`).
- **Endpoint**: `https://api.stlouisfed.org/fred/series/observations`
- **Key Series**:
  - `DCOILBRENTEU`: Brent Crude Oil Prices Daily.
  - `DGS10`: 10-Year Treasury Constant Maturity Rate.
  - `FEDFUNDS`: Federal Funds Effective Rate.
  - `DEXINUS`: U.S. Dollars to Indian Rupee Spot Exchange Rate.

---

### 6. News & Sentiment: Google News RSS (Indian Business Press)
- **Cost**: 100% Free.
- **Authentication**: None.
- **Format**: Open XML / RSS Feed.
- **Endpoint Pattern**:
  ```
  https://news.google.com/rss/search?q={TICKER}+NSE+stock&hl=en-IN&gl=IN&ceid=IN:en
  ```
- **Coverage**: Curates articles from Economic Times, Moneycontrol, Livemint, Business Standard, Reuters India, and Bloomberg.
- **Local Scoring**: Headlines are parsed and scored using local NLTK VADER (`backend/app/news.py`), completely offline with 0 API cost.

---

## 3. Guarantees for `stockportfolio.in`

1. **Zero Mandatory Paid Subscriptions**: The entire system—from stock prices, sector indices, options data, and fundamentals to international macro indicators and live news—runs entirely on free and open APIs.
2. **Graceful Degradation**: If any single external provider undergoes temporary maintenance, the system degrades gracefully with explicit `{ "available": false, "reason": "..." }` responses instead of inventing mock fallbacks.
3. **Optimized Caching & TTLs**:
   - Live Quotes: 60 seconds
   - Market Pulse & Breadth: 5 minutes
   - Macro Series (Crude, FX, Yields): 15 minutes
   - Fundamentals (Screener.in): 24 hours
   - News RSS: 15 minutes
