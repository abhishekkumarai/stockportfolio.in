# UI Gap Analysis — stockportfolio.in

*Written 2026-09-13. Sources: full exploration of `frontend/src` (Next.js App
Router) and `backend/app` (FastAPI, ~85 endpoints / 17 routers).*

## Executive summary

- The backend is far more capable than the UI exposes: alert rules, paper
  trading detail, portfolio snapshot history, AI-generated explanations, tax-
  aware exit costs, and most of the mutual-fund analysis suite are fully
  built server-side with **no frontend caller**.
- The flagship homepage ("Master Console") mixes real portfolio data with a
  large amount of **fabricated data rendered as if live** — fake tickers,
  fake option chains, fake backtest logs, a static footer P&L figure — with
  no visual distinction from genuinely live numbers. For a financial
  product this is a credibility (and potentially compliance) problem, and
  it's the single highest-priority item in this document.
- Three parallel design systems coexist in the frontend (legacy CSS-variable
  system, ad-hoc raw Tailwind, and shadcn/ui), with shadcn — the one
  configured project-wide — used on only one page.
- Several pages exist with no navigation entry (`/backtest`, `/funds`,
  `/macro`), and the broker-statement-upload feature is fully backed but has
  **zero UI** — every "Import Statement" button in the app just links to the
  signin page, which has no upload form.
- No toast/notification system exists; loading skeletons and accessibility
  attributes are sparse outside `/recommendations`.

## 1. Critical: fabricated data rendered as live

| Location | What's fake | Fix |
|---|---|---|
| `src/app/page.tsx` | `alphaPicks` (L254-333, 6 invented stocks), `optionChain` (L336-437, fake NIFTY chain), `backtestLogs` (L440-489), static footer `₹32,05,920.00` P&L (L1785-1796), fake "Showing 1-6 of 50" pagination (L1863-1906), Piotroski modal always "PASS" (L2041-2140), `handleExecuteBasket` is a `setTimeout` stub with no backend call (L534-544), two bare `alert()` calls (L1333, L1495) | Remove or replace with real API-backed data; wire `handleExecuteBasket` to a real order endpoint or clearly disable/label it as a demo |
| `src/components/TopBar.tsx` | Hardcoded NIFTY/SENSEX/VIX index values (L124-145) styled with pulsing "Live" dots, fake "WebSocket Live · 3ms" badge (L191-196), notification bell with no handler (L199-206) | Fetch real index quotes (`/api/stocks/history` or `/api/macro`) or remove the "Live" styling; remove the fake WS badge; wire or remove the bell |
| `src/components/Sidebar.tsx` | Static "Live"/"0% Tax"/"500 EQ"/"Fyers" badges (L191, 226, 267, 341) not tied to any real state | Derive from real connection/portfolio state or remove |
| `PortfolioDashboard.tsx` | `FALLBACK_DANGER`/`FALLBACK_GROWTH` (L31-121) silently substituted on error/first load | Show a visible "sample data" badge when fallback is active, per the `OptionsConsole` pattern below |
| `HealthRadar.tsx` | `SAMPLE_CATALYSTS_NEWS`/`SAMPLE_REBALANCE_PLAN` (L31-129) silently substituted on error | Same — visible sample-data indicator |
| `QuantConsole.tsx` | `FALLBACK_METHODS`/`FALLBACK_OPTIMISE_RESULT` (L44-100) silently substituted on error | Same |
| `src/app/analyse/page.tsx` | `FEATURED_STOCKS` (L20-121) shown as a live "featured" grid | Replace with a real screener/recommendations-backed list, or remove the section |

**Reference pattern already in the codebase:** `OptionsConsole.tsx`'s
`generateSimulatedChain()` is used only when the live Fyers fetch fails, and
the UI visibly flags this with an amber "Simulated" badge vs. a green "Live"
badge. This is the correct pattern and should be applied everywhere else
data can silently fall back to a fabricated value.

## 2. Backend features with zero frontend surface

- **Alert rules** (`/api/accounts/me/alerts/*`) — create/list/delete rules,
  fired-event history — entirely absent from the UI.
- **Portfolio snapshot history** (`/api/accounts/me/snapshots`) — no equity
  curve chart anywhere, despite nightly jobs already recording it.
- **Paper trading detail** (`/api/paper/{id}/orders`, `/signals`, `/run`) —
  only list/create is wired; the audit-trail value (executed vs. skipped
  signals) is unreachable in the UI.
- **AI `/explain`** (plain-English "why is this a BUY/SELL") and
  **`/sentiment`** — unused, despite `Recommendation` objects already
  carrying `reasons[]`/`conviction`/`warnings[]` that a bare score badge
  wastes.
- **Tax-aware exit context** (`exit_context()` in `recommendations.py`
  L172-238: estimated exit tax, net proceeds, days-to-LTCG note) — valuable,
  unclear whether it's rendered anywhere.
- Fyers `/positions`, `/funds`, `/quote`, `/history`; options live
  `/chain`/`/analysis`/`/greeks`; ML `/metrics`; mutual fund `/compare`,
  `/sip`, `/lumpsum`, `/rolling`.
- **Broker statement upload** — `uploadStatementFile()` /
  `importOfflineStatement()` / `getOfflineFiles()` exist in `portfolioApi.ts`
  with **zero call sites**. Every "Import Statement (.xlsx)" button in the
  app (`page.tsx`, `PortfolioDashboard.tsx`, `QuantConsole.tsx`) links to
  `/auth`, which has no upload form. This is a fully-backed feature with no
  UI at all.
- Two parallel auth systems (email/password in `auth.py` vs. anonymous
  account-key in `accounts.py`) aren't integrated — the frontend doesn't
  appear to pass the auth token into the accounts/holdings/alerts calls.

## 3. Navigation/discoverability gaps

Pages that exist with no sidebar entry: `/backtest`, `/funds`,
`/funds/[schemeCode]`, `/macro`. The "Broker Active" link and the sidebar
profile link both point to `/auth`, which has no account/broker-management
UI — a functional dead end.

## 4. Design system fragmentation

Three coexisting systems:
1. Legacy `.glass-panel`/CSS-variable + inline styles — `portfolio/*`,
   `quant`, `paper`, `lab`, `backtest`, `funds`.
2. Ad-hoc raw Tailwind utility strings duplicated across files — homepage,
   `macro`, `pulse`, `screener`, `analyse` index, `TopBar`, `Sidebar`.
3. shadcn/ui (`src/components/ui/*`) — configured project-wide via
   `components.json` but used only on `/recommendations`.

Recommendation: standardize on shadcn/ui and retire the other two.

## 5. Missing UX infrastructure

- No toast/notification library anywhere — all feedback is inline banners.
- Only `/recommendations` uses real loading skeletons; everything else uses
  a generic spinner or nothing.
- Homepage has no error state for `refreshPortfolio` — failures are
  swallowed to `console.error` only.
- Sparse accessibility: a handful of `aria-label`s, no focus traps on
  modals, no `role="dialog"`/`aria-modal` on the rebalance/forensic modals.

## 6. Responsive-design inconsistency

Homepage and `AppShell`/`Sidebar`/`TopBar` handle mobile well (dual
desktop-table/mobile-card renders, real drawer with Escape-to-close).
Older pages (`backtest`, `portfolio`, `lab`, `paper`, `quant`) use fixed
inline `gridTemplateColumns` with no breakpoint handling and won't reflow
on narrow screens.

## 7. Prioritized recommendations

1. Remove or clearly label all fabricated/fallback data (§1) — cheapest fix,
   highest trust impact.
2. Build the broker-statement-upload UI (backend already complete).
3. Add nav entries for orphaned pages; fix dead "Broker Active"/profile
   links.
4. Consolidate on shadcn/ui; retire the two legacy styling systems.
5. Surface the highest-value unused backend features: alert rules,
   snapshot/equity-curve history, AI `/explain`, paper-trading detail.

---

## Implementation log

**Done (2026-09-13):**

- **Homepage (`src/app/page.tsx`)**: removed the fabricated static footer P&L,
  fake pagination, and the always-"PASS" Piotroski modal; per-holding
  Piotroski/VaR figures that were deterministically faked from array index
  now show "—"/a link to real fundamentals instead. The Alpha Picks, Option
  Chain, and Backtest Logs tabs are now clearly labeled "Sample data" with a
  link to the real page. The "Execute Rebalance Basket" modal no longer
  simulates order placement (`setTimeout` + "Basket Successfully
  Dispatched!") — it now links out to the real rebalance/hedge pages and
  states plainly that order execution isn't supported. Two `alert()` calls
  removed. Added a visible error state for portfolio load failures. KPI
  cards for tax status, F&O hedge sizing, and ML alpha/VaR no longer show
  invented numbers — they either show real computed values or link to the
  page that computes them.
- **`TopBar.tsx`**: NIFTY/SENSEX/VIX tickers are now fetched from
  `/api/macro` (extended to include `nifty50`/`sensex` current price + 1-day
  change, and `vix` 1-day change) instead of hardcoded literals; the chip
  hides itself rather than fabricating a value when the feed is unavailable.
  Removed the fake "WebSocket Live · 3ms" badge and the non-functional
  notification bell's fake unread dot.
- **`Sidebar.tsx`**: removed static "Live"/"0% Tax" badges; the Fyers badge
  on Options now reflects real connection status. Added nav entries for the
  previously-orphaned `/backtest`, `/funds`, and `/macro` pages.
- **Broker statement upload**: built the missing UI. `PortfolioDashboard.tsx`
  now has a real file input wired to the existing `uploadStatementFile()`
  API client — previously every "Import Statement" button in the app linked
  to `/auth`, which had no upload form at all.
- **`savePortfolio()`** now dispatches the `portfolio-updated` event it was
  always supposed to — Sidebar and the homepage listen for this event, but
  nothing fired it, so cross-page portfolio sync depended on a full reload.
- **Silent fake-data fallbacks now labeled**: `PortfolioDashboard.tsx`
  (danger/growth), `HealthRadar.tsx` (news headlines — previously fabricated
  and attributed to real outlets like Economic Times/BSE — and the rebalance
  plan), and `QuantConsole.tsx` (optimiser/factors/regime/rebalance panels)
  all now show a visible "Sample data" notice when falling back, instead of
  silently substituting a fabricated result that looks identical to a real
  one.

**Deferred (larger scope, not attempted this pass):**

- Full backend wiring of the homepage's Wealth Cone SVG, Strategy Lab tab,
  and OI Payoff tab to real Monte Carlo / walk-forward / options data
  (currently labeled "Illustrative" rather than removed).
- Alert rules UI, portfolio snapshot/equity-curve history UI, paper-trading
  order/signal detail UI, AI `/explain` surfacing — all backend-complete,
  still no frontend (§2).
- Design-system consolidation onto shadcn/ui (§4).
- Toast/notification system; accessibility pass (focus traps, ARIA on
  modals) (§5).
- Responsive-layout fixes for `backtest`/`portfolio`/`lab`/`paper`/`quant`
  (§6).
- Also noticed but out of this analysis's scope: `backend/app/routes/auth.py`
  signup does not actually reject a duplicate email (pre-existing bug, caught
  by the backend test suite — `test_signup_and_signin_flow` fails on main).

**Done (2026-09-13, follow-up): Portfolio page tab antipattern fixed.** The
"Wealth Cone & VaR" / "Tax Rebalance" / "Catalysts & News" area was 5 tabs
(`overview`/`stress`/`rebalance`/`news`/`memo`) implemented as pure client
`useState` in `HealthRadar.tsx`, switched by pill buttons that never updated
the URL — so back/forward/reload/sharing a specific tab were all broken for
in-page clicks. Meanwhile the sidebar separately linked to 3 of the 5 tabs via
`?tab=` query params, and the other 2 (Crash Simulator, AI Memo) had no
sidebar entry at all. Rebuilt as 5 real Next.js routes (`/portfolio`,
`/portfolio/stress`, `/portfolio/rebalance`, `/portfolio/news`,
`/portfolio/memo`) sharing one `layout.tsx` that owns all portfolio/valuation
state via a new `PortfolioContext` and renders the KPI cards, sub-nav, and
holdings table once; `HealthRadar.tsx` and `PortfolioDashboard.tsx` were
deleted, fully redistributed into per-route `*View.tsx` files. Sidebar now has
all 5 entries pointing at real paths; a small redirect in the layout sends old
`/portfolio?tab=...` links to the matching new route. Verified in Chrome:
URLs update on tab click, browser Back/Forward now works, and rebalance/news
now fetch real data immediately on navigating to the route (previously only
fetched lazily on click).

**Done (2026-09-13, second follow-up): Holdings split out; shared radar
wrapper fully disintegrated.** Per user request, went further than the route
split above: the holdings table, Add Holding form, and Allocation Bars chart
moved out into a new dedicated `/portfolio/holdings` page (first entry in the
sidebar's Portfolio Intelligence group), taking the KPI strip and Connect
Fyers/Import Statement/Refresh Analytics buttons with them. `layout.tsx` shrank
to an invisible state provider (just `PortfolioContext` + hydration gating +
the legacy `?tab=` redirect) — no more shared header, KPI grid, or in-page
pill sub-nav (`PortfolioSubNav.tsx` deleted). Each of the 5 analysis pages
(Wealth & VaR, Crash Simulator, Tax Rebalance, Catalysts & News, AI Memo) now
stands alone with its own heading, reachable purely via the sidebar. To avoid
stranding a user with an empty portfolio on one of those 5 pages (no more
Connect/Import buttons in view there), added a small shared
`EmptyPortfolioNotice` link-out to the Holdings page, shown on all 5 when
`isEmpty`. All other internal links that pointed at bare `/portfolio` for
holdings-management purposes (homepage's "Import/Sync Broker Holdings" and
rebalance-preview cards, Quant Lab's "Import Statement" buttons,
Recommendations' "Add your portfolio" link) were repointed to
`/portfolio/holdings`. Verified in Chrome: Holdings page has all the chrome,
the 5 analysis pages have none of it, sidebar highlights correctly on all 6.

**Done (2026-09-13, third follow-up): Tail Risk Sizer split into its own
route; sidebar/topbar scroll bug fixed.** The "Tail-risk hedge sizer" was
unconditionally rendered inline at the bottom of `/options`, even though the
sidebar already linked to it separately via `/options?tab=sizer` — that query
param was never actually read by `OptionsConsole.tsx`, so the two "views"
were really the same page. Extracted it into a real `/options/tail-risk`
route (own `page.tsx` + `TailRiskSizerView.tsx`, self-contained: loads its own
portfolio and fetches its own default index spot instead of depending on
whatever chain the user happened to have loaded on `/options`). `/options`
itself no longer renders the sizer. Also fixed a real layout bug hit while
verifying this: the sidebar and top bar were not actually sticky — nested
`overflow-x-hidden` ancestors were implicitly turning their `overflow-y` into
`auto` (a CSS spec rule: an axis set to non-`visible` forces the other axis
off `visible` too), which broke `position: sticky` against the true viewport,
so the sidebar scrolled away with the page on any tall page. Fixed in
`AppShell.tsx` by switching to a fixed-height shell (`h-screen overflow-hidden`)
with the sidebar simply filling that fixed height and only the content column
scrolling (`overflow-y-auto`) — the conventional, more robust pattern, rather
than fighting sticky positioning across multiple nested overflow contexts.
Verified live: sidebar and top bar now stay pinned to the browser window on
every page while content scrolls underneath.

**Done (2026-09-13, fourth follow-up): `/funds` renamed to `/mutualfunds`;
undefined-CSS-class sweep; "Your Mutual Funds" feature added.**

- Renamed the route directory (`frontend/src/app/funds` → `.../mutualfunds`)
  and every internal link (`Sidebar.tsx`, `FundSearch.tsx`,
  `[schemeCode]/page.tsx`). Verified live and via a clean production build.
- While reviewing `/mutualfunds`, found `FundSearch.tsx`'s search box used
  `className="search-input-wrapper"`/`"search-input"` — **classes never
  defined anywhere in the codebase** — so the input rendered with no border,
  background, or width (default browser ~20-char intrinsic width), truncating
  the placeholder mid-word. Fixed by replacing with inline styles matching
  the file's own existing pattern.
- Asked to sweep for the same bug pattern app-wide. Found **7 more instances**,
  all in `frontend/src/app/analyse/[ticker]/page.tsx`: the page's headline
  BUY/SELL/HOLD `badge-recommendation` class (highest impact — rendered as
  plain unstyled text), and six classes in the news-feed section
  (`news-feed`, `news-card`, `news-header`, `news-source`, `news-time`,
  `news-title`, `news-sentiment-badge`) — the sentiment badges and headline
  links rendered unstyled, and an inline `--sentiment-color` custom property
  was set but never consumed by anything. All fixed with inline styles reusing
  the app's existing `--color-buy/-sell/-hold(-bg)` design tokens. Also fixed
  a drive-by bug spotted next to these: `data.name` used hardcoded
  `color: "#fff"` on this light-themed app, rendering the company name
  effectively invisible. Noted but left alone (lower priority, not broken):
  ~260 lines of a fully unused earlier sidebar design in `globals.css` and
  the default unused `page.module.css` boilerplate.
- Built the requested feature: a "Your Mutual Funds" panel at the top of
  `/mutualfunds` (`MyMutualFunds.tsx`), shown only when the portfolio holds
  funds. Per user's design choice, shows both personal performance (invested/
  current value/P&L from the real portfolio valuation, matching the Holdings
  page exactly) and each fund's own 1Y/3Y CAGR (fetched live per fund via the
  existing fund-analysis endpoint, `Promise.allSettled` so one fund's fetch
  failing doesn't blank out the others). Each row links through to that
  fund's detail page; a "Manage holdings →" link points back to
  `/portfolio/holdings`. Verified live against the demo account's 5 real
  mutual fund holdings.
