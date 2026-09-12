# Stitch Design Specification & Generation Prompts: StockPortfolio.in

> **Target Platform**: [stitch.withgoogle.com](https://stitch.withgoogle.com)  
> **Design Theme**: `stockportfolio-enterprise-light` (Institutional Daylight Console)  
> **Source Design System**: [`DESIGN.md`](./DESIGN.md)  
> **Reference Project ID (Stitch)**: `projects/11821548636130176926`  
> **Design System Asset**: `assets/21025ff2f8224247b64d021182afbc71`  

---

## 1. Design System Rules & Tokens (Strict Stitch Guardrails)

All Stitch screens generated for this project must strictly comply with the following architectural rules:

### Visual Hierarchy & Tone
- **Atmosphere**: Institutional decision-support terminal modeled on Ant Design Pro, FactSet, Material UI 3, and Stripe Dashboard. Zero dark crypto/AI-slop aesthetics, neon glows, or blurry gradients.
- **Canvas Backdrop**: Slate-50 (`#F8FAFC`).
- **Cards & Surfaces**: Pure White (`#FFFFFF`) with razor-sharp `1px solid #E2E8F0` hairline structural borders and subtle elevation (`0 1px 2px 0 rgba(15, 23, 42, 0.04)`).
- **Subtle Panels / Insets**: Slate-100 (`#F1F5F9`) for table headers, nested trays, and secondary search wells.

### Color Palette (Color is Financial Data)
```css
/* Chrome & Foundations */
--canvas:           #F8FAFC;  /* Daylight workspace background */
--surface-card:     #FFFFFF;  /* Card surface */
--surface-subtle:   #F1F5F9;  /* Table headers & nested panels */
--border-subtle:    #E2E8F0;  /* Structural 1px hairlines */
--border-strong:    #CBD5E1;  /* Focus rings & input borders */

/* Typography & Ink */
--ink:              #0F172A;  /* Primary headings and financial metrics */
--ink-secondary:    #475569;  /* Labels, subtitles, metadata */
--ink-muted:        #94A3B8;  /* Timestamps, column heads, units */

/* Primary Action & Brand */
--primary:          #2563EB;  /* Royal Sapphire: Primary CTAs, active states */
--primary-hover:    #1D4ED8;  /* Deepened sapphire */
--primary-subtle:   #EFF6FF;  /* Active nav background, selected tab */

/* Semantic Financial Signals */
--buy:              #059669;  /* Pine Emerald: Gains, Buy signals, Pristine */
--buy-surface:      #ECFDF5;  /* Soft emerald pill fill */
--sell:             #DC2626;  /* Crisp Crimson: Losses, Drawdown, Sell calls */
--sell-surface:     #FEF2F2;  /* Soft crimson pill fill */
--hold:             #D97706;  /* Warm Ochre Amber: Warnings, Proximity gate */
--hold-surface:     #FFFBEB;  /* Soft amber pill fill */
```

### Typography Hierarchy & Monospace Discipline
- **Display**: `Inter 700`, `24px - 28px`, tracking `-0.02em` (Page headers).
- **Heading**: `Inter 600`, `16px - 18px`, tracking `-0.01em` (Card titles, section headers).
- **Body**: `Inter 400`, `13px - 14px`, line-height `1.45` (Descriptions, prose).
- **Micro Label**: `Inter / JetBrains Mono 500`, `11px`, UPPERCASE, tracking `0.05em` (Column heads, pill tags).
- **Financial Numbers**: `JetBrains Mono 500/600` with `font-variant-numeric: tabular-nums` (Mandatory for all ₹ amounts, % returns, strike prices, and ratios to prevent column jitter).

---

## 2. Feature Inventory & UI Trigger Catalog

Below is the exhaustive catalog of every feature in the application requiring interactive UI triggers (buttons, forms, sliders, inputs, toggles, and table actions):

### Module 1: Global Platform Chrome & Broker Streaming
*Files: `frontend/src/components/TopBar.tsx`, `Sidebar.tsx`*
- **T1.1 Fyers OAuth Handshake**:
  - `Connect Fyers` button (initiates OAuth flow).
  - `Disconnect` button (revokes session token).
  - Live Broker Status badge with pulsing green dot (`Fyers Live WebSocket`).
- **T1.2 Universal Command Search (`Cmd + K`)**:
  - Global Search Input with instant search modal for 500+ NSE equities, F&O contracts, and AMFI mutual funds.
  - Search result item click (routes to deep dive).
- **T1.3 Streaming Benchmark Ticker Ribbon**:
  - Live tick cards for NIFTY 50, SENSEX, INDIA VIX, BRENT CRUDE, and USD/INR with delta indicators.
- **T1.4 Enterprise Navigation Rail (240px)**:
  - 4 Partitioned groups: *Portfolio Intelligence*, *Research & Discovery*, *Quant & Derivatives*, *Lab & Agent Tools*.
  - Active item indicator with 3px sapphire left accent and `#EFF6FF` fill.
  - Mobile hamburger toggle (`Menu / X`).

### Module 2: Portfolio Intelligence & Asset Allocation (`/portfolio`)
*Files: `frontend/src/app/portfolio/PortfolioDashboard.tsx`, `AddHoldingForm.tsx`, `AllocationBars.tsx`*
- **T2.1 Fyers One-Click Sync**:
  - `Import from Fyers` primary button (imports all live delivery holdings).
  - `Refresh Analytics` button (triggers fresh valuation and risk recalculation).
- **T2.2 Manual Lot Ingestion Form**:
  - Asset Type Tab Switcher: `Equity` vs `Mutual Fund`.
  - Symbol search input with autocomplete.
  - Quantity numeric input (`step="1"`).
  - Average Cost numeric input (`₹`).
  - Purchase Date datepicker (locks holding period for tax analysis).
  - `Add to Portfolio` submit button.
- **T2.3 Cash Drag Adjustment**:
  - Cash Balance input (`₹`) for total portfolio NAV weighting.
- **T2.4 Holdings Ledger Actions**:
  - Sortable column headers: `Weight %`, `Total Value`, `Unrealized P&L`, `VaR Contribution`.
  - Inline `Analyse` button (opens `/analyse/[ticker]`).
  - Inline `Remove` (trash icon) button with confirmation.
- **T2.5 Wealth Cone & Monte Carlo Projection**:
  - Time horizon slider (1 to 20 years).
  - Monthly SIP injection input (`₹5,000` to `₹1,00,000`).
  - Projection confidence interval toggle (5th/50th/95th percentile).

### Module 3: Indian Tax-Aware Rebalancer & Proximity Gate (`/portfolio?tab=rebalance`)
*Files: `frontend/src/app/portfolio/HealthRadar.tsx`, `backend/app/quant/tax.py`*
- **T3.1 Rebalancing Mode Switcher**:
  - Segmented toggle: `Zero-Tax Cash Inflow` vs `Full Drift Trimming`.
- **T3.2 Fresh Capital Inflow Allocator**:
  - Inflow Capital input (`₹25,000`, `₹50,000`, etc.).
  - `Compute Rebalance Plan` CTA button.
- **T3.3 LTCG Proximity Gate Alert**:
  - Proximity warning banner (e.g. *"HDFCBANK: Day 342. Hold 23 more days to transition from 20% STCG to 12.5% LTCG"*).
  - `Hold for LTCG` action lock button.
- **T3.4 Actionable Order Sheet**:
  - Order table with action tags (`BUY` / `SELL`), target quantities, and tax drag.
  - `Export Order Sheet (CSV)` button.
  - `Send to Virtual Paper Ledger` button.

### Module 4: Danger Matrix & Historical Crash Stress Simulator (`/portfolio?tab=overview`, `tab=stress`)
*Files: `frontend/src/app/portfolio/HealthRadar.tsx`*
- **T4.1 Danger vs Growth Health Radar**:
  - Concentration risk threshold toggle (flags top 3 holdings > 50%).
  - Market cap exposure filter: `All` | `Large Cap` | `Mid/Small Cap`.
- **T4.2 Historical Crash Simulator**:
  - Scenario Selector dropdown:
    - *2020 COVID Flash Crash (-38%)*
    - *2008 Global Financial Crisis (-55%)*
    - *2016 Demonetization Shock (-12%)*
    - *2022 Crude Spike & Inflation (-16%)*
  - `Run Stress Simulation` button.
  - Projected recovery time toggle (months to breakeven).

### Module 5: Holding News Catalysts & AI Monthly Memo (`/portfolio?tab=news`, `tab=memo`)
*Files: `frontend/src/app/portfolio/HealthRadar.tsx`, `AiMemo.tsx`*
- **T5.1 Whitelist Catalyst Feed**:
  - Category filter pills: `ALL`, `EARNINGS`, `BOARD_MEETING`, `SEBI_DISCLOSURE`, `DIVIDEND`.
  - Sentiment filter buttons: `All`, `Positive Only (VADER > +0.3)`, `Adverse Only`.
  - `Refresh News Feed` button.
- **T5.2 AI Executive Narrative Memo**:
  - `Generate Monthly Memo` button.
  - Tone selector: `Institutional Risk Officer` vs `Action-Oriented Portfolio Manager`.
  - `Copy Memo to Clipboard` button.
  - `Export Markdown` button.

### Module 6: Live Market Pulse & Institutional Breadth (`/pulse`)
*Files: `frontend/src/app/pulse/page.tsx`*
- **T6.1 Market Breadth Tracker**:
  - Universe dropdown: `NIFTY50`, `NIFTY100`, `NIFTYMIDCAP50`.
  - Auto-refresh toggle switch (30-second interval).
- **T6.2 Volume Shockers & 52-Week Breakouts**:
  - Tab switcher: `Volume Shockers` vs `52-Week Breakouts`.
  - Volume expansion threshold buttons: `> 2x`, `> 3x`, `> 5x` 20-day average.
  - Inline row CTA: `Add to Screener` / `Analyze Stock`.

### Module 7: Buy & Sell Alpha Board & ML Ranker (`/recommendations`)
*Files: `frontend/src/app/recommendations/RecommendationsConsole.tsx`, `AIAlphaRadarTab.tsx`*
- **T7.1 Alpha Board Tabs & Universe Selector**:
  - Tab switcher: `Ranked Buys`, `Ranked Sells`, `My Portfolio Audit`, `AI Alpha Radar (ML)`.
  - Index Scope dropdown: `NIFTY50`, `NIFTY100`, `NIFTY200`, `NIFTY500`.
  - Scan Depth toggle: `Fast Scan (Prices Only)` vs `Full Scan (With Fundamentals)`.
  - `Refresh Recommendations` button.
- **T7.2 Purged Walk-Forward ML Decile Picker**:
  - Decile selector slider / buttons (`Decile 10: Top Alpha` down to `Decile 1`).
  - Feature Importance view toggle (`RSI`, `Momentum`, `ROCE`, `Debt/Equity`).
  - Inline row action: `Paper Trade Pick`.

### Module 8: NSE Universe Screener (`/screener`)
*Files: `frontend/src/app/screener/ScreenerConsole.tsx`*
- **T8.1 One-Click Preset Templates**:
  - Preset pill buttons: `Quick technical scan`, `Quality compounders`, `Trend momentum`, `Ranked buys only`.
- **T8.2 Filter Criteria Panel**:
  - Universe slider (50 to 500 stocks).
  - `With Fundamentals` toggle checkbox.
  - Fundamental inputs: `Min ROCE %`, `Max Debt/Equity`, `Min Promoter %`, `Max P/E`.
  - Technical toggles: `Above SMA 200`, `Golden Cross (50/200)`, `Min ADX`, `RSI Range (min/max)`.
  - Action checkboxes: `STRONG_BUY`, `BUY`, `HOLD`, `REDUCE`, `SELL`.
  - `Run Screener` primary button.
  - `Export to CSV` button.
- **T8.3 Screener Results Grid**:
  - Column sort headers (`Score`, `RSI`, `ROCE`, `P/E`).
  - Row expander accordion revealing technical indicators and balance sheet audit.

### Module 9: Equity Deep Dive & Forensic Scoring (`/analyse/[ticker]`)
*Files: `frontend/src/app/analyse/[ticker]/page.tsx`*
- **T9.1 Ticker Switcher & Chart Controls**:
  - Symbol input with search button.
  - Timeframe tabs: `1M`, `3M`, `6M`, `1Y`, `5Y`, `ALL`.
  - Overlay toggles: `SMA 20/50/200`, `Bollinger Bands`, `RSI`, `MACD`.
- **T9.2 Forensic Health Audit**:
  - Piotroski F-Score expander (9 individual sub-tests).
  - Altman Z-Score distress meter.
  - Financials view switcher: `Consolidated` vs `Standalone`.
  - `Add to Portfolio` modal trigger.

### Module 10: Quant Lab — HRP & Optimization (`/quant`)
*Files: `frontend/src/app/quant/QuantConsole.tsx`*
- **T10.1 Portfolio Optimization Controls**:
  - Tab switcher: `Allocation`, `Factor Exposures`, `Market Regime`, `Execution Orders`.
  - Method selector: `Hierarchical Risk Parity (HRP)`, `Min Variance`, `Max Sharpe`, `Equal Risk Contribution`.
  - Max Asset Weight slider (`15%` to `50%`).
  - Lookback period buttons: `1y`, `2y`, `3y`, `5y`.
  - `Include Efficient Frontier` checkbox.
  - `Calculate Optimal Weights` primary button.
- **T10.2 Factor Exposure Regression**:
  - Benchmark dropdown: `NIFTY 50` vs `NIFTY 500`.
  - `Run Factor Regression` button.
- **T10.3 Market Regime Classifier**:
  - `Detect Regime` button (`Bull Quiet`, `Bull Volatile`, `Bear Quiet`, `Bear Volatile`).
- **T10.4 Target Order Sheet**:
  - Cash inflow input (`₹`).
  - `Allow Selling` toggle checkbox.
  - `Generate Orders` CTA button.

### Module 11: Option Chain & Tail Hedging Sizer (`/options`)
*Files: `frontend/src/app/options/OptionsConsole.tsx`*
- **T11.1 Live Option Chain Controls**:
  - Underlying symbol dropdown (`NIFTY50`, `NIFTYBANK`, `RELIANCE`, etc.).
  - Strike count selector (`10`, `15`, `20`, `30` strikes).
  - Expiry date dropdown selector.
  - `Refresh Option Chain` button.
  - Chart toggle: `Total OI` vs `Change in OI`.
- **T11.2 Automated Tail Hedging Sizer**:
  - Structure selector: `Long Index Put` vs `Zero-Cost Collar`.
  - Drawdown Floor slider (`Capped at -5%`, `-10%`, `-15%`).
  - Portfolio Capital Coverage slider (`50%` to `100%`).
  - `Calculate Hedge Plan` CTA button.
  - `Add Hedge to Paper Ledger` button.

### Module 12: Strategy Lab v2 & Backtester (`/lab`)
*Files: `frontend/src/app/lab/StrategyLab.tsx`*
- **T12.1 Execution Model Settings**:
  - Symbol input / selector.
  - Strategy dropdown: `RSI 2-Period Mean Reversion`, `SMA Crossover`, `Donchian Breakout`, `Bollinger Bands`.
  - Start / End datepickers.
  - Initial Capital input (`₹`).
  - Position Sizer: `Fixed %`, `Volatility Sized`, `Fixed Risk`.
  - Slippage input (`0.05%` to `0.20%`).
  - `Run Permutation Test (1,000 runs)` checkbox.
  - `Run Backtest` primary CTA button.
- **T12.2 Walk-Forward Validation**:
  - Folds input (`2` to `8` folds).
  - Metric objective: `Sharpe`, `CAGR`, `Sortino`, `Calmar`.
  - `Run Walk-Forward Optimization` button.
  - `Export Trade Logs (CSV)` button.

### Module 13: Paper Trading & Virtual Execution Ledger (`/paper`)
*Files: `frontend/src/app/paper/PaperConsole.tsx`*
- **T13.1 Virtual Account Manager**:
  - `Create Virtual Account` button / modal.
  - Initial capital input (`₹1,00,000` to `₹1,00,00,000`).
  - Virtual account switcher dropdown.
- **T13.2 Order Ticket**:
  - Symbol input, Side toggle (`BUY` / `SELL`), Quantity input.
  - Order type toggle: `MARKET` vs `LIMIT` (with limit price input).
  - `Submit Virtual Order` button.
- **T13.3 Automated Strategy Runner**:
  - Strategy dropdown with `Run Strategy Signals` button.
  - `Liquidate All Positions` danger button.
  - `Export Audit Log` button.

### Module 14: India Macro Radar (`/macro`) & Mutual Funds (`/funds`)
*Files: `frontend/src/app/macro/page.tsx`, `frontend/src/app/funds/page.tsx`*
- **T14.1 Macro Radar**:
  - `Refresh Macro Data` button.
  - Crude Oil sensitivity slider (`$70` to `$110/bbl`).
  - Sector Rotation lookback buttons (`1W`, `1M`, `3M`).
- **T14.2 AMFI Funds Explorer**:
  - Live fund search input with category filter pills (`Equity`, `Debt`, `Hybrid`, `Index`, `ELSS`).
  - AMC filter dropdown.
  - Monthly SIP calculator input and duration slider with `Calculate SIP` button.

---

## 3. Ready-to-Execute Stitch Generation Prompts

You can directly copy and paste these modular prompts into **[stitch.withgoogle.com](https://stitch.withgoogle.com)** or invoke them via the Stitch MCP tool:

### Prompt A: Master Institutional Portfolio Console (`/portfolio`)

```markdown
Design an institutional desktop financial console for StockPortfolio.in, an Indian equity and portfolio intelligence platform (modeled on Ant Design Pro, FactSet, and Stripe Dashboard).

Strict Design Tokens:
- Canvas: Slate-50 (#F8FAFC)
- Cards: Pure White (#FFFFFF) with 1px slate-200 structural borders (#E2E8F0) and subtle elevation (0 1px 2px rgba(15, 23, 42, 0.04))
- Typography: Inter for headings and body; JetBrains Mono with tabular-nums for all monetary values (₹), percentages, tickers, and ratios
- Primary Brand/Action: Royal Sapphire (#2563EB)
- Signals: Pine Emerald (#059669 with #ECFDF5 fill) for gains, Crisp Crimson (#DC2626 with #FEF2F2 fill) for losses, Ochre Amber (#D97706 with #FFFBEB fill) for caution

Layout Structure:
1. Top Command & Market Bar (56px sticky top bar, #FFFFFF, 1px bottom border #E2E8F0):
   - Left: Platform Logo 'StockPortfolio.in' in Inter 700 with a subtle sapphire badge 'ENTERPRISE', followed by live Indian market benchmark pills:
     - NIFTY 50: 24,852.15 (+142.30 / +0.58%) [Pine Emerald]
     - SENSEX: 81,332.70 (+410.20 / +0.51%) [Pine Emerald]
     - INDIA VIX: 13.45 (-0.62 / -4.41%) [Emerald]
     - BRENT CRUDE: $74.80/bbl (+0.4%)
     - USD/INR: ₹83.94 (-0.03)
   - Center: Quick Search input box (Cmd+K) 'Search Indian tickers, F&O contracts, AMFI funds...' with hairline border #CBD5E1
   - Right: Broker Status pill ('Fyers Live WebSocket' with green status dot), Market Bell indicator, and User Account badge ('Abhishek Kumar - Institutional Pro')

2. Enterprise Navigation Rail (240px fixed left sidebar, #FFFFFF, 1px right border #E2E8F0):
   - Module 1: PORTFOLIO INTELLIGENCE
     - Active item: 'Portfolio Console' (#EFF6FF background, #2563EB text, 3px solid sapphire left border)
     - 'Wealth Cone & VaR'
     - 'Tax-Aware Rebalancing' (with 'Zero Tax' badge)
     - 'Holding Catalysts & News'
     - 'AI Monthly Memo'
   - Module 2: RESEARCH & DISCOVERY
     - 'NSE Universe Screener' (500 Equities)
     - 'Equity Deep Dive' (Piotroski & Altman Z)
     - 'Ranked Alpha Board'
     - 'Live Market Pulse'
   - Module 3: QUANT & DERIVATIVES
     - 'Options Chain & OI Walls'
     - 'Tail Risk Hedging & Sizer'
     - 'Hierarchical Risk Parity (HRP)'
   - Module 4: LAB & AGENT TOOLS
     - 'Event-Driven Backtester v2'
     - 'Paper Trading Ledger'

3. Main Dashboard Canvas (#F8FAFC):
   - Header Bar with actions:
     - Title: 'My Portfolio' with subtitle 'Real-time analytics, Danger vs Growth diagnostics, and tax-aware rebalancing.'
     - Buttons: 'Import from Fyers' (Primary Sapphire), 'Refresh Analytics' (Secondary Outline), and 'Add Lot' (Button)
   - Top KPI Summary Cards (4-column grid):
     - Card 1: 'TOTAL PORTFOLIO NAV' -> ₹48,25,400.00 with delta badge '+₹1,42,850.00 (+3.05%) Today'
     - Card 2: 'NET UNREALIZED GAIN' -> ₹11,84,200.00 (+32.52% overall return), XIRR: 24.8%
     - Card 3: 'REALIZED FY25 TAX DRAG' -> ₹3,18,500.00 (LTCG: ₹2,40,000 @ 12.5% | STCG: ₹78,500 @ 20%), 'LTCG Exemption: ₹1.25L applied'
     - Card 4: 'RISK & CAPITAL AT RISK' -> Daily Historical VaR (95%): 1.48% (₹71,415) | Sharpe: 1.84 | Beta: 0.88 vs NIFTY

   - Middle Section (2 columns):
     - Left (65% width): 'Wealth Cone & Monte Carlo Projection (10-Year 1,000 Paths)' card showing 5th percentile, median (50th), and 95th percentile trajectory bands with terminal NAV ₹1.84 Cr, plus SIP injection toggle (₹25k/mo).
     - Right (35% width): 'Indian Tax Rebalancer & Proximity Gate (Budget 2024-25)' card:
       - Mode switcher: 'Zero-Tax Inflow' vs 'Full Drift Trim'
       - LTCG Proximity Alert banner: 'HDFCBANK (45 shares) is at Day 342. Hold for 23 more days to save 7.5% tax (STCG 20% -> LTCG 12.5%)'
       - SIP Inflow Allocator: ₹50,000 capital route recommendations to underweight RELIANCE and TITAN (₹0 tax incurred).

   - Bottom Section: 'Portfolio Holdings & Forensic Health Matrix' (Ant Design Pro style table):
     - Columns: 'TICKER & ASSET', 'WEIGHT %', 'QTY', 'AVG BUY (₹)', 'LTP (₹)', 'TOTAL VALUE (₹)', 'P&L (₹ / %)', 'VAR CONTRIB', 'PIOTROSKI F', 'CATALYST SIGNAL', 'ACTIONS'
     - Sample Indian equities:
       - RELIANCE (Reliance Industries Ltd) | 16.4% | 310 | ₹2,740.00 | ₹2,985.40 | ₹9,25,474.00 | +₹76,074 (+8.96%) | 22% VaR | 8/9 (Strong) | EARNINGS BEAT (VADER +0.64) | [Rebalance]
       - TCS (Tata Consultancy Services) | 14.2% | 170 | ₹3,820.00 | ₹4,210.80 | ₹7,15,836.00 | +₹66,436 (+10.23%) | 18% VaR | 9/9 (Pristine) | DIVIDEND ₹28/sh | [Hold]
       - HDFCBANK (HDFC Bank Ltd) | 13.8% | 400 | ₹1,580.00 | ₹1,665.20 | ₹6,66,080.00 | +₹34,080 (+5.39%) | 15% VaR | 7/9 (Stable) | PROXIMITY GATE (Day 342) | [Hold for LTCG]
       - INFY (Infosys Ltd) | 10.5% | 260 | ₹1,720.00 | ₹1,945.50 | ₹5,05,830.00 | +₹58,630 (+13.11%) | 12% VaR | 8/9 (Strong) | AI CLOUD DEAL (VADER +0.72) | [Hold]
       - ICICIBANK (ICICI Bank Ltd) | 9.8% | 380 | ₹1,110.00 | ₹1,245.00 | ₹4,73,100.00 | +₹51,300 (+12.16%) | 11% VaR | 8/9 (Strong) | SEBI DISCLOSURE | [Rebalance]
     - Sticky table footer with aggregate portfolio sums and pagination.
```

---

### Prompt B: Indian Tax-Aware Rebalancing & Wealth Cone (`/portfolio?tab=rebalance`)

```markdown
Design an institutional tax optimization workspace for StockPortfolio.in focusing on Indian Capital Markets Tax Regime (Budget 2024-2025 rates).

Tokens & Styling:
- Daylight console theme: Soft slate-50 background (#F8FAFC), pure white cards (#FFFFFF), 1px slate borders (#E2E8F0), royal sapphire accents (#2563EB).
- Typography: Inter with JetBrains Mono for monetary values (₹) and percentages.

Components & Layout:
1. Header Bar:
   - Title: 'Tax-Aware Rebalancing & Capital Gains Minimizer'
   - Context Pill: 'Budget 2024–25: STCG @ 20% | LTCG @ 12.5% (>₹1.25L Exemption)'
   - Action Button: 'Export Execution Sheet (CSV)' (Primary Sapphire)

2. Top Configuration Strip:
   - Mode Selector: Segmented pill control ['Zero-Tax Cash Inflow Mode (Recommended)', 'Full Target Weight Rebalance']
   - Fresh Capital Input: Numeric input box with prefix '₹' and preset chips [+₹25,000, +₹50,000, +₹1,00,000]
   - Rebalance Objective: Dropdown ['Hierarchical Risk Parity Target', 'Equal Weight', 'Max Sharpe']
   - Primary Action: 'Optimize Capital Allocation' button

3. Proximity Gate & Harvesting Alert Box:
   - Warning card with amber border (#D97706) and soft amber fill (#FFFBEB):
     - Icon: Clock Alert
     - Headline: '3 Positions Near 365-Day LTCG Transition Window'
     - Details: 'Liquidating HDFCBANK, LT, or TITAN today triggers 20% STCG. Waiting 18 to 28 days transitions them to 12.5% LTCG, saving ₹42,800 in capital gains taxes.'
     - Action CTA: 'Lock Positions from Rebalance' button

4. Actionable Order Sheet (Ant Design Pro Table):
   - Table columns: 'ACTION', 'TICKER', 'CURRENT WT', 'TARGET WT', 'SHARES TO TRADE', 'EST. EXECUTION PRICE', 'TRADE NOTIONAL', 'EST. TAX DRAG', 'TAX OPTIMIZATION RATIONALE'
   - Rows:
     - BUY | RELIANCE | 12.4% -> 16.0% | +18 shares | ₹2,985.40 | ₹53,737.20 | ₹0.00 | 'Funded via fresh inflow. Zero tax drag.'
     - BUY | TITAN | 4.2% -> 7.5% | +12 shares | ₹3,410.00 | ₹40,920.00 | ₹0.00 | 'Underweight quality compounder. Zero tax drag.'
     - HOLD | HDFCBANK | 16.8% | 0 shares | ₹1,665.20 | ₹0.00 | ₹0.00 | 'Locked: Day 342 of 365 (LTCG Proximity Gate)'
   - Table Footer: Total Capital Deployed: ₹94,657.20 | Total Realized Gains Tax: ₹0.00 (Zero-Tax Execution Confirmed)
```

---

### Prompt C: Live Option Chain, OI Walls & Tail Risk Hedging (`/options`)

```markdown
Design an institutional derivatives cockpit for StockPortfolio.in displaying live NSE Option Chains and automated Portfolio Tail Hedging sizing.

Tokens & Styling:
- Daylight console theme: #F8FAFC canvas, #FFFFFF cards, 1px #E2E8F0 borders, #2563EB primary sapphire, #059669 emerald for Calls/OI drops, #DC2626 crimson for Puts/OI surges.
- Typography: Inter with JetBrains Mono tabular numbers for strikes, Greeks, and lot sizes.

Layout Structure:
1. Top Control Strip:
   - Underlying Selector: Dropdown ['NIFTY50 (LTP: 24,852.15)', 'NIFTYBANK (LTP: 51,340.50)', 'RELIANCE', 'HDFCBANK']
   - Expiry Dropdown: ['26-SEP-2024 (Monthly)', '03-OCT-2024 (Weekly)', '10-OCT-2024 (Weekly)']
   - Strike Count Range: Pill selector [10 strikes, 15 strikes, 20 strikes, 30 strikes]
   - Live Metrics Ribbon:
     - Put-Call Ratio (PCR): 1.14 (Mild Bullish)
     - Max Pain Strike: 24,800 CE/PE
     - Major Call Wall: 25,000 CE (1.42 Cr OI)
     - Major Put Wall: 24,500 PE (1.85 Cr OI)
     - IV Rank / Percentile: 24.2% (Low Volatility Environment)

2. Middle Section: Automated Portfolio Tail Hedging Sizer Card:
   - Sizing Parameters:
     - Target Portfolio Protection: ₹48,25,400.00
     - Drawdown Cap Slider: [-5% (Conservative), -10% (Balanced), -15% (Disaster Only)]
     - Strategy Selector: Segmented control ['Long Index Put', 'Zero-Cost Collar (+OTM Put / -OTM Call)']
   - Hedge Recommendation Box (Pure White card with 1px slate border):
     - Suggested Position: Buy 2 Lots NIFTY 26-SEP 24,200 PE @ ₹48.50 + Sell 2 Lots NIFTY 26-SEP 25,400 CE @ ₹46.20
     - Net Hedge Cost: ₹230 total debit (0.004% portfolio drag)
     - Max Protected Downside: Capped at -6.4% regardless of market drop
     - Action: 'One-Click Add to Paper Trading Ledger' (Royal Sapphire button)

3. Bottom Section: Dual-Sided NSE Option Chain Matrix (Ant Design Pro dense layout):
   - Left side: CALLS (OI, Change in OI %, Volume, IV %, Delta, Bid, Ask, LTP)
   - Center column: STRIKE PRICE (Highlighted ATM row at 24,850 in subtle sapphire #EFF6FF)
   - Right side: PUTS (LTP, Bid, Ask, Delta, IV %, Volume, Change in OI %, OI)
   - Monospace tabular figures with horizontal micro-bars showing relative OI density across strikes.
```

---

### Prompt D: Strategy Lab v2 & Walk-Forward Backtester (`/lab`)

```markdown
Design an institutional quantitative research console for StockPortfolio.in's Event-Driven Strategy Lab (v2 Next-Bar-Open Fills with Walk-Forward Validation).

Tokens & Styling:
- FactSet / Ant Design Pro daylight console: Slate-50 canvas (#F8FAFC), pure white surfaces (#FFFFFF), 1px slate hairline borders (#E2E8F0), royal sapphire accents (#2563EB).
- Typography: Inter with JetBrains Mono for all CAGR, Sharpe, Drawdown, and slippage figures.

Layout Structure:
1. Strategy Configuration Sidebar / Top Bar:
   - Universe & Asset: Symbol input ['RELIANCE'] with search button
   - Strategy Dropdown: ['RSI 2-Period Mean Reversion', 'SMA 50/200 Trend Crossover', 'Donchian Channel Breakout', 'Multi-Factor Momentum']
   - Date Range: [2019-01-01] to [2024-09-10] (5 Years)
   - Initial Capital: ₹1,00,000
   - Position Sizing Model: Dropdown ['Percent of Equity (100%)', 'Fixed Risk (1% per trade)', 'Volatility Sized (ATR)']
   - Institutional Cost Configuration:
     - Brokerage: ₹20 flat cap per order
     - Slippage: 0.05%
     - STT: 0.1% on delivery
   - Permutation Test: Checkbox ['Run 1,000 Bootstrap Permutations (Monte Carlo p-value)']
   - Primary CTA: 'Run Event-Driven Backtest' (Royal Sapphire button)

2. Walk-Forward Validation Strip:
   - Folds Selector: [4 Folds] (6-month out-of-sample rolling windows)
   - Objective Metric: Dropdown ['Sharpe Ratio', 'CAGR', 'Sortino', 'Calmar']
   - Button: 'Run Walk-Forward Optimization'

3. Performance Analytics Cockpit (Top 4 Metric Cards):
   - Metric 1: 'STRATEGY CAGR' -> 26.4% vs NIFTY 14.8% (Alpha: +11.6%)
   - Metric 2: 'MAX DRAWDOWN' -> -11.2% (Duration: 42 days) vs Benchmark -38.4%
   - Metric 3: 'SHARPE / SORTINO' -> 1.94 / 2.78 (p-value: 0.002 - Statistically Significant)
   - Metric 4: 'WIN RATE & PROFIT FACTOR' -> 68.4% Win Rate (142 Trades) | Profit Factor: 2.14

4. Interactive Visualizations:
   - Top Chart (65%): Dual-line Equity Curve (Strategy in Royal Sapphire #2563EB vs Buy & Hold Benchmark in Slate-400 #94A3B8).
   - Bottom Chart (35%): Underwater Drawdown Chart (Crimson #FEF2F2 filled area with #DC2626 line).

5. Audit & Trade Log Table (Ant Design Pro):
   - Columns: 'TRADE #', 'ENTRY DATE & TIME', 'SIGNAL', 'FILL PRICE (NEXT OPEN)', 'EXIT DATE & TIME', 'EXIT PRICE', 'SLIPPAGE & FEES', 'NET P&L (₹ / %)', 'HOLDING BARS'
   - Monospace tabular figures with status badges (Green pill for +P&L, Red pill for -P&L).
   - Actions: 'Export CSV Audit Trail' and 'Deploy to Paper Trading'.
```

---

### Prompt E: NSE Universe Screener & Alpha Board (`/screener` & `/recommendations`)

```markdown
Design an institutional equity screener and alpha discovery workstation for StockPortfolio.in covering the 500-stock NSE universe.

Tokens & Styling:
- FactSet / Ant Design Pro daylight console: Slate-50 canvas (#F8FAFC), pure white surfaces (#FFFFFF), 1px slate hairline borders (#E2E8F0), royal sapphire accents (#2563EB).
- Typography: Inter with JetBrains Mono for scores, ratios, and percentages.

Layout Structure:
1. Preset Filters Bar:
   - Preset Pills: ['Quick Technical Scan (150)', 'Quality Compounders (ROCE > 18%)', 'Trend Momentum (Golden Cross)', 'Ranked Buys Only', 'Custom Filter']

2. Multi-Factor Filter Panel:
   - Universe Slider: [NIFTY 500 (300 active)]
   - Toggles & Inputs:
     - Fundamental: 'With Fundamentals' checkbox | Min ROCE % [18%] | Max Debt/Equity [0.8] | Min Promoter % [50%]
     - Technical: 'Above SMA 200' toggle | 'Golden Cross' toggle | Min ADX [20] | RSI Range [40 - 68]
     - Quantitative Action: Checkbox group ['STRONG_BUY', 'BUY', 'HOLD']
   - Actions: 'Run Screener (300 Stocks)' (Primary Sapphire) | 'Reset Filters'

3. Results Table with Expandable Audit Rows (Ant Design Pro Style):
   - Table Columns: 'RANK', 'SYMBOL & NAME', 'SECTOR', 'LTP (₹)', '1D CHANGE %', 'RSI (14)', 'ROCE %', 'DEBT/EQUITY', 'PIOTROSKI F', 'ACTION RECOMMENDATION', 'QUICK ACTIONS'
   - Sample Rows:
     - #1 | BEL (Bharat Electronics) | Defense | ₹312.40 | +2.85% | 58.4 | 26.2% | 0.00 | 9/9 | [STRONG_BUY] | [Analyse] [Add]
     - #2 | TRENT (Trent Ltd) | Retail | ₹7,140.00 | +1.92% | 64.1 | 24.8% | 0.42 | 8/9 | [STRONG_BUY] | [Analyse] [Add]
     - #3 | DIXON (Dixon Tech) | Electronics | ₹12,850.00 | +3.40% | 62.0 | 21.5% | 0.28 | 8/9 | [BUY] | [Analyse] [Add]
   - Expanded Accordion on Click: Displays live Screener.in forensic audit metrics (Sales growth 3Y, Margin trends, P/E vs Historical median, VADER news sentiment score).
   - Table Footer: 42 stocks matched criteria. Pagination controls and 'Export to CSV' CTA.
```

---

## 4. How to Generate in Stitch

To generate screens with these prompts using the configured Stitch MCP server:
1. Ensure project `projects/11821548636130176926` is active.
2. Call `generate_screen_from_text` with:
   - `projectId`: `"11821548636130176926"`
   - `prompt`: Copy one of the prompts above (e.g. Prompt A, B, C, D, or E).
   - `designSystem`: `"assets/21025ff2f8224247b64d021182afbc71"`
   - `deviceType`: `"DESKTOP"`
   - `modelId`: `"GEMINI_3_8_FLASH"`
3. View the generated screen in Stitch at [stitch.withgoogle.com](https://stitch.withgoogle.com).
