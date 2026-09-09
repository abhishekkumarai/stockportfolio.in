# ChatGPT Research Archive: Stock Prediction Repositories & Indian Market Intelligence

*Source*: [https://chatgpt.com/share/6aa0e93e-6608-83e8-93ef-bc43b3886b39](https://chatgpt.com/share/6aa0e93e-6608-83e8-93ef-bc43b3886b39)  
*Archived on*: 2026-09-09  
*Topic*: GitHub repositories covering stock prediction, factor ranking, market intelligence, and live NSE recommendation engines.

---

## Turn 1

### User Prompt
> Gorhub repo which does all sort of stock prediction

### ChatGPT Response
If you mean **one GitHub repo that covers almost the whole stock-prediction stack**, these are the strongest options I found:

#### 1. Best overall: QuantStock
* **GitHub**: [MXGao-A/QuantStock](https://github.com/MXGao-A/QuantStock)
* **Architectures**:
  - Transformer
  - LSTM / GRU / TCN
  - GAT / GCN
  - Mamba
  - XGBoost / LightGBM
* **Capabilities**:
  - Backtesting engine
  - Metrics: Sharpe, Sortino, max drawdown, returns
  - Portfolio Top-K selection
  - Pre-configured datasets: DOW30, NASDAQ100, SSE50

This is probably the closest to *"throw every serious ML approach at stock prediction"*.

---

#### 2. Best if you want GenAI + stocks: FinGPT
* **GitHub**: [AI4Finance-Foundation/FinGPT](https://github.com/AI4Finance-Foundation/FinGPT)
* **Capabilities**:
  - Financial LLM fine-tuning
  - News sentiment analysis
  - Financial forecasting (`FinGPT-Forecaster`)
  - Blends fundamental information + news + market data
  - Hugging Face models and datasets

Particularly relevant given your GenAI background.

---

#### 3. Best full-stack example for Indian + US stocks: StockIntel
* **GitHub**: [zhaymn/StockIntel](https://github.com/zhaymn/StockIntel)
* **Coverage**: Indian equities (NSE) + US equities (S&P 500)
* **Architectures & Stack**:
  - LSTM
  - LightGBM
  - Stacked Ensemble
  - Technical indicators (34 scale-free, stationary features)
  - FinBERT sentiment
  - LLM event analysis
  - Purged walk-forward validation
  - FastAPI backend + Next.js frontend
  - Backtesting and fundamentals integration
  - News pipeline

> **Key takeaway**: This one is particularly interesting because it explicitly tests whether the models actually beat a naive baseline instead of producing another beautiful AI dashboard that confidently predicts nonsense.

---

#### 4. StockAI
* **GitHub**: [digantk31/StockAI](https://github.com/digantk31/StockAI)
* **Models**: SARIMAX, LSTM, MLP, Random Forest, Gradient Boosting
* **Features**:
  - FinBERT sentiment
  - Portfolio optimization (Markowitz Efficient Frontier)
  - Backtesting with transaction costs
  - NIFTY 50 benchmark comparison

Good if you want a more approachable implementation.

---

### What I'd pick for you
**StockIntel + FinGPT + QuantStock.**

Build an architecture like:

```
Market Data ───────┐
                   │
Technical Features ├──> ML Models
                   │     ├── LightGBM
News ─> FinBERT ───┤     ├── LSTM
                   │     ├── Transformer
Fundamentals ──────┘     └── Ensemble
                              │
                              ▼
                       Signal Generator
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
                 BUY/SELL             HOLD
                    │
                    ▼
              Risk Management
                    │
                    ▼
               Backtesting
                    │
                    ▼
             Portfolio Strategy
```

> **Important**: Don't optimize for *raw price prediction accuracy*. For an actual trading system, optimize and evaluate:
> - **Directional accuracy**
> - **Precision of signals**
> - **Sharpe ratio & max drawdown**
> - **Turnover and transaction friction**
> - **Purged walk-forward performance**  
> StockIntel's methodology is especially useful here.

---

## Turn 2

### User Prompt
> Yes. What you want is not just a stock-price prediction repo. You want a stock intelligence + recommendation engine that answers: “What is happening in the market right now, which stocks are interesting, why, and should I BUY/HOLD/SELL?” For Indian stocks

### ChatGPT Response
For **Indian stocks**, these are much closer to what you're describing:

#### 🥇 Best match: StockBot India
* **GitHub**: [bllubhai/stockbot-india](https://github.com/bllubhai/stockbot-india)
* **Features**:
  - Scans **Nifty 500**
  - Produces: **BUY / HOLD / SELL / STRONG SELL**
  - Cross-sectional ranking of stocks
  - Technical analysis (RSI, MACD, EMAs)
  - Fundamentals: P/E, ROE, D/E, etc.
  - News analysis & NSE corporate filings
  - Chart analysis & Confidence score
  - Backtesting of previous recommendations
  - Portfolio allocation based on a budget
  - Risk flags

This is probably the *closest to your exact requirement*.

---

#### 🥈 PKScreener
* **GitHub**: [pkjmesra/PKScreener](https://github.com/pkjmesra/PKScreener)
* **Specialty**: Advanced market scanner
  - 40+ scanners
  - Breakouts & Momentum
  - RSI / MACD / CCI / ATR
  - Volume analysis & Volume shockers
  - Chart patterns & VCP (Minervini-style screening)
  - ML signals
  - Nifty trend prediction
  - Telegram alerts

Good for answering: *"Which stocks are moving or breaking out right now?"*

---

#### 🥉 NSE Stock Scanner
* **GitHub**: [deshwalmahesh/NSE-Stock-Scanner](https://github.com/deshwalmahesh/NSE-Stock-Scanner)
* **Focus**: Swing and intraday trading
  - Breakout detection
  - Momentum & Market mood
  - Sector analysis
  - RSI / MACD / Stochastic / Ichimoku
  - Moving average crossovers
  - Option-chain analysis
  - Risk management & backtesting
  - Broker integration

---

#### 🏅 One particularly interesting newer repo: Indian Stock Analysis Tool
* **GitHub**: [biswajitmohanty/ind-stock-analysis](https://github.com/biswajitmohanty/ind-stock-analysis)
* **Combines**:
  - 9 technical indicators
  - 10 chart patterns
  - India VIX regime conditioning
  - Calibrated BUY / SELL / HOLD probabilities
  - ATR-scaled stop-loss and take-profit targets

---

### What I would build
Given your GenAI background, combine these concepts rather than blindly trusting one repository:

```
                 NSE / Market Data
                        │
        ┌───────────────┼────────────────┐
        ↓               ↓                ↓
    Technical       Fundamentals       News
    Analysis          Analysis        + Events
        │               │                │
        └───────────────┼────────────────┘
                        ↓
                 Feature Engine
                        ↓
               ML / Quant Models
         ┌──────────┬───────────┐
         ↓          ↓           ↓
      LightGBM    LSTM       Transformer
         └──────────┬───────────┘
                    ↓
              Signal Ensemble
                    ↓
        ┌───────────┼────────────┐
        ↓           ↓            ↓
       BUY         HOLD         SELL
        │
        ↓
   Risk Engine
        │
        ├── Entry
        ├── Target
        ├── Stop Loss
        ├── Expected return
        └── Confidence
                    ↓
              LLM Explanation
                    ↓
     "Why should I buy RELIANCE?"
```

> **Core Insight**: The LLM should **explain and rank the evidence**, not magically predict prices. Even StockIntel's extensive testing found its ML models did *not* reliably beat a naive baseline out-of-sample. That's a useful reality check rather than another AI project pretending the stock market has finally been solved.

---

### Comparison of Candidate Repositories

| Repo | Activity | Stock selection | News | Fundamentals | AI/ML | India |
|---|---|---|---|---|---|---|
| **StockBot India** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **PKScreener** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **NSE Stock Scanner** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **StockIntel** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

Start with **StockBot India** as the functional base, then add a proper **FinBERT/LLM news layer + quantitative ranking + backtesting**. That gets you much closer to an actual *"What should I buy today and why?"* system.

---

## Turn 3

### User Prompt
> Does it come with the UI?

### ChatGPT Response
Yes, but there's an important distinction across the options:

1. **StockBot India**:
   - **Yes, it has a UI.**
   - Includes a local **Streamlit + Plotly web dashboard** with:
     - Market Pulse
     - Sector Performance
     - Universe Explorer
     - Deep Dive individual stock pages

2. **PKScreener**:
   - Primarily **CLI-based**, with Telegram alerts and generated HTML/backtest reports.
   - It is not a polished, continuous web dashboard.

3. **KJ Screener** ([85599/kjscreener](https://github.com/85599/kjscreener)):
   - Has a more explicit dashboard-style UI, including real-time screening, charts, backtesting, and AI insights.

#### For what you're asking:
Pick **StockBot India** if you want:
> Dashboard → market activity → stock ranking → BUY/HOLD/SELL → stock deep dive → news → fundamentals → portfolio allocation.

And importantly, **it runs locally**, so you can execute the whole pipeline on your machine rather than handing your financial data plumbing to an external SaaS.

---

## Turn 4

### User Prompt
> Its not synced

### ChatGPT Response
You're right. If by **“synced”** you mean **live/current market data**, I would **not rely on the StockBot India repo I previously recommended**. My earlier answer overstated how suitable it is.

For what you actually want, the system requires:
1. Live / near-real-time market data
2. Automatic refresh & cache invalidation
3. Market-wide activity / heatmap
4. Stock screener (breakouts, volume shockers, technical setups)
5. Actionable BUY / HOLD / SELL signals
6. News + sentiment analysis
7. Fundamental health metrics (ROCE, D/E, Piotroski)
8. Technical indicators (RSI, MACD, Bollinger, ATR)
9. Analyst consensus & price targets
10. Walk-forward backtesting
11. Web UI (modern, responsive)
12. Native NSE / BSE exchange support

---

### Alternative: StockBot powered by Groq
* **GitHub**: [bklieger-groq/stockbot-on-groq](https://github.com/bklieger-groq/stockbot-on-groq)
* Features a proper web UI, interactive TradingView charts, financials, news, and screeners powered by fast Llama 3 70B inference via Groq.
* **Limitation**: It is oriented toward US equities and is not an Indian-stock recommendation engine out of the box.

---

### Final Architectural Conclusion

If your actual requirement is:
> **“Open dashboard → see what is happening in NSE today → see top movers → unusual volume → sectors → news → AI analysis → get ranked BUY recommendations.”**

Then **build directly on top of a live NSE market-data source rather than trying to find one magical GitHub repo.** Humanity has apparently decided that stock prediction and reliable data synchronization should be separate problems.

The ultimate production architecture combines:
- **Live NSE Ingestion Layer**: Continuous price & volume feeds via broker API or live quotes.
- **Scanning Primitives (inspired by PKScreener)**: Volume shockers, 52-week breakouts, consolidation scans.
- **Factor Ranking & Purged Walk-Forward Alpha (inspired by StockIntel & QuantStock)**: Cross-sectional decile ranking, zero-leakage validation, and comparison against a naive baseline.
- **ATR Risk Levels & Trade Structuring (inspired by ind-stock-analysis)**: Entry, Stop-Loss, and Target bands scaled by volatility.
- **Institutional Tax & Capital Preservation Layer (native to `stockportfolio.in`)**: STCG @ 20%, LTCG @ 12.5%, and evidence-backed explainability.
