---
version: 2.0
name: stockportfolio-enterprise-light
description: |
  A high-density, institutional-grade console for Indian equity and portfolio intelligence,
  modeled on Ant Design Pro, Material UI 3, FactSet, and Stripe Dashboard. Replaces dark
  crypto/AI-slop aesthetics with an executive light theme: a soft slate-50 canvas (#F8FAFC),
  crisp pure white surfaces (#FFFFFF) defined by 1px slate structural borders (#E2E8F0),
  and a restrained financial semantic palette (Pine Emerald for profit/buys, Crimson for
  loss/breaches, Ochre Amber for caution, and Corporate Royal Sapphire #2563EB for primary
  actions). Typography enforces tabular monospace numerals (JetBrains Mono / Inter Tabular)
  for zero-jitter financial scannability.
---

## Philosophy

This is an institutional decision-support and quantitative terminal, not a decorative marketing site or crypto dashboard. Every number on screen informs risk, asset allocation, or order execution. The interface prioritizes scannability, rapid visual parsing, and low cognitive fatigue during volatile trading days.

Three core laws govern every visual and structural choice:
1. **Architectural Structure, Not Decorative Glow.** Depth is achieved through clean 1px structural borders (`#E2E8F0`) and subtle, whisper-soft elevation (`0 1px 2px 0 rgba(15, 23, 42, 0.05)`). Decorative purple/cyan neon halos, blurry backdrop filters, and dark zinc-950 surfaces are strictly forbidden.
2. **Color is Financial Data.** Interface chrome is neutral slate. Color is spent strictly on semantic financial state:
   - Emerald (`#059669` / `#10B981`) for gains, positive momentum, healthy balance sheets, and buy signals.
   - Crimson (`#DC2626` / `#EF4444`) for losses, downside volatility, drawdown breaches, and sell signals.
   - Amber (`#D97706` / `#F59E0B`) for caution, warnings, and hold signals.
   - Royal Sapphire (`#2563EB`) exclusively for primary CTAs, active segmented tabs, and focus outlines.
3. **Tabular Monospace Number Discipline.** All monetary figures (₹), percentages (%), price targets, ratios, and strike prices enforce `font-variant-numeric: tabular-nums` or `JetBrains Mono` to prevent column shifting during live streaming ticks.

---

## Palette Tokens

```
/* Foundations */
canvas              #F8FAFC   slate-50. Daylight-readable workspace backdrop.
surface-card        #FFFFFF   pure white elevated cards & containers.
surface-subtle      #F1F5F9   slate-100 table header row and nested panel background.
surface-hover       #F8FAFC   subtle row hover state.
border-subtle       #E2E8F0   slate-200 structural hairline for cards & table rows.
border-strong       #CBD5E1   slate-300 input border and focus outline.

/* Typography & Ink */
ink                 #0F172A   slate-900. High-contrast primary headings and financial values.
ink-secondary       #475569   slate-600. Secondary copy, field labels, metadata.
ink-muted           #94A3B8   slate-400. Column heads, timestamps, ticker units.

/* Primary Execution & Action */
primary             #2563EB   royal sapphire. Execution buttons, active nav, primary tabs.
primary-hover       #1D4ED8   deepened sapphire hover.
primary-subtle      #EFF6FF   selected tab background, active nav item background.

/* Financial Semantic Signals */
buy                 #059669   pine emerald. Positive delta, buy recommendations, healthy score.
buy-surface         #ECFDF5   soft emerald chip fill.
sell                #DC2626   crisp crimson. Negative delta, sell recommendations, drawdown.
sell-surface        #FEF2F2   soft crimson chip fill.
hold                #D97706   warm ochre amber. Hold recommendations, warnings, alert states.
hold-surface        #FFFBEB   soft amber chip fill.
```

---

## Typography Hierarchy

```
display    Inter 700, 24px-28px, tracking -0.02em, line-height 1.2   page headers
heading    Inter 600, 16px-18px, tracking -0.01em                    section headers, card titles
body       Inter 400, 13px-14px, line-height 1.45                    descriptive prose
small      Inter 400, 12px, ink-secondary                            supporting metadata
label      Inter / JetBrains Mono 500, 11px, UPPERCASE               column headers, tags, status pills
figure     JetBrains Mono 500/600, tabular-nums                      prices, P&L, percentages, ratios
```

---

## Component Standards

- **Top Command & Market Bar**: 56px sticky top bar, `#FFFFFF` with `1px solid #E2E8F0`. Houses live benchmark indicators (NIFTY 50, SENSEX, INDIA VIX, BRENT CRUDE, USD/INR), universal search (`Cmd+K`), broker connection status, and user profile.
- **Enterprise Navigation Rail**: 240px fixed left rail on `#FFFFFF` with `1px solid #E2E8F0`. Grouped into 4 modules: Portfolio Intelligence, Research & Alpha, Quant & Derivatives, and Execution & Lab. Active nav items display `#EFF6FF` background with `#2563EB` text and a 3px left border.
- **KPI Summary Cards**: White card, `border: 1px solid #E2E8F0`, `border-radius: 6px-8px`, subtle shadow (`0 1px 2px 0 rgba(15, 23, 42, 0.04)`). Uppercase 11px slate label, prominent tabular primary value, and contextual delta badge.
- **Data Tables (Ant Design Pro Style)**: Sticky header with `#F8FAFC` background and uppercase 11px mono labels. Rows separated by 1px `#E2E8F0` hairline. Numeric and financial columns are right-aligned in monospace.
- **Buttons**:
  - Primary: `#2563EB` solid fill, white text, 4px-6px radius, hover `#1D4ED8`.
  - Secondary: `#FFFFFF` fill with `1px solid #CBD5E1`, `#0F172A` text, hover `#F1F5F9`.
- **Status Pills & Chips**: Pill-shaped (`rounded-full`), 24px height, with light semantic background fill (e.g., `#ECFDF5` for buy, `#FEF2F2` for sell), 1px tinted border, and dark semantic text.
