# PRD: Production Deployment — Split Hosting (Vercel + Render)

**Status:** Proposed
**Author:** abhishekkumarai
**Date:** 2026-07-21
**Repo:** `stockportfolio_in` (Next.js 16 frontend + FastAPI backend)

---

## 1. Problem Statement

The project does not deploy. Two separate problems are being conflated:

1. **The Vercel deployment fails at build time** because of how the repository is
   structured, not because of application code.
2. **The FastAPI backend is architecturally incompatible with Vercel's serverless
   runtime.** Even if the build succeeded, the API would fail or time out at runtime.

This document specifies a target architecture — frontend on Vercel, backend on a
container host (Render or Railway) — and the concrete work required to get there.
It is written assuming the reader has never deployed to Render or Railway before.

---

## 2. Root Cause Analysis

### 2.1 Why the Vercel build fails

The repository root contains no `package.json` and no `vercel.json`:

```
stockportfolio_in/
├── backend/          # FastAPI + vercel.json (legacy config)
├── frontend/         # Next.js 16.2.9 app — the actual deployable
└── download_historical.py
```

Vercel clones the repo and runs its build in the root directory by default. It finds
no Node manifest, cannot detect a framework, and fails with a "no Next.js version
detected" / "no build output" style error.

**Fix:** set the Vercel project's **Root Directory** to `frontend`. This is a
dashboard setting, not a code change. Everything below it (`pnpm-lock.yaml`,
`next.config.ts`, `src/`) is then treated as the project root.

### 2.2 Why the backend cannot run on Vercel

`backend/vercel.json` uses the legacy `builds` array with `@vercel/python`. Five
independent blockers:

| # | Blocker | Evidence |
|---|---------|----------|
| 1 | **Bundle size.** Vercel Python functions cap at 250 MB unzipped. | `pandas` 67 MB, `numpy` 33 MB + `numpy.libs` 21 MB, `nltk` 13 MB, plus `yfinance`, `curl_cffi`, `pydantic`. Already ~140 MB before transitive deps. |
| 2 | **Cold-start downloads.** `main.py:20-27` fetches the NLTK `vader_lexicon` into `/tmp` at import time. Serverless filesystems are ephemeral — this re-downloads on every cold start, adding latency and a network dependency to the critical path. |
| 3 | **Execution timeout.** Backtests download multi-year OHLC history via `yfinance`, then simulate. Vercel Hobby functions are limited to ~10s (60s on Pro). A 5-year `Hybrid` backtest will exceed this. |
| 4 | **Scraper IP reputation.** `scraper.py:25` scrapes Google News with `curl_cffi` TLS impersonation. Google aggressively blocks shared datacenter egress IPs; the function will silently fall through to `_get_fallback_news()`. |
| 5 | **Module-level state.** `stocks.py` instantiates `scraper = GoogleNewsScraper()` at import. Any future in-process caching is worthless when every request may hit a cold container. |

**Conclusion:** the backend needs a long-lived container with a persistent
filesystem and no hard request timeout. That is Render or Railway, not Vercel.

### 2.3 Runtime bugs that will surface after the build is fixed

These do not break the build, but will break the deployed app:

- **`NEXT_PUBLIC_API_URL` is unset on Vercel.** All three call sites
  (`src/app/page.tsx:43`, `src/app/backtest/page.tsx:101`,
  `src/app/analyse/[ticker]/page.tsx:97`) fall back to `http://127.0.0.1:8001`.
  In production the browser would call the user's own machine. Every request fails.
- **CORS will reject a custom domain.** `main.py:41` allows
  `https://.*\.vercel\.app` via regex. The moment a real domain is attached, or
  Vercel serves a preview under a non-matching host, requests are blocked.
- **`allow_credentials=True` combined with a permissive origin regex** is a
  standing security smell. No cookies are used today; it should be `False`.

---

## 3. Goals & Non-Goals

### Goals

- **G1** — Frontend builds and serves from Vercel on every push to `main`.
- **G2** — Backend runs as a container on Render (or Railway) with a public HTTPS URL.
- **G3** — Frontend talks to the backend via a single configured environment variable.
- **G4** — CORS is explicit and correct for production, preview, and local origins.
- **G5** — A first-time Render/Railway user can follow §6 end to end without prior knowledge.

### Non-Goals

- Custom domain purchase and DNS (can follow later).
- Database introduction — the app is stateless today; keep it that way.
- Authentication, user accounts, saved portfolios.
- CI test gates (there is no test suite yet).
- Migrating away from Google News scraping to a paid market-data API.

---

## 4. Target Architecture

```
Browser
   │
   ├──────────────► Vercel (Next.js 16, static + SSR)
   │                Root Directory: frontend/
   │                Env: NEXT_PUBLIC_API_URL
   │
   └── fetch() ───► Render Web Service (Docker or native Python)
                    uvicorn app.main:app --host 0.0.0.0 --port $PORT
                    Env: FRONTEND_ORIGIN, NLTK_DATA
                            │
                            ├──► yfinance (OHLC history)
                            └──► Google News (curl_cffi scrape)
```

**Why split hosting rather than all-Vercel or all-Render?**
Vercel's edge CDN and Next.js build pipeline are genuinely best-in-class for the
frontend and free for this workload. The backend's requirements — heavy scientific
Python, multi-second compute, persistent NLTK corpora — are exactly what a
long-running container is for. Splitting plays to both platforms' strengths.

**Render vs Railway — recommendation: start with Render.**

| | Render | Railway |
|---|---|---|
| Free tier | Yes, but the service **sleeps after ~15 min idle** (first request after sleep takes ~30-50s) | Trial credit, then paid; no indefinite free tier |
| Beginner UX | Slightly simpler; explicit Build/Start command fields | More flexible, more concepts (services, plugins, variables) |
| Verdict | **Recommended to start.** Free, and cold starts are acceptable for a personal project. | Upgrade path if the sleep latency becomes annoying. |

Pricing and free-tier terms on both platforms change frequently — verify current
terms on their pricing pages before committing.

---

## 5. Requirements

### 5.1 Repository changes

| ID | Requirement | File |
|----|-------------|------|
| R1 | Add `backend/Dockerfile` pinning Python 3.12, installing `requirements.txt`, pre-downloading the NLTK lexicon **at build time** (not at import), and starting uvicorn bound to `0.0.0.0:$PORT`. | new |
| R2 | Delete `backend/vercel.json`. It is dead config that invites re-deploying the backend to the wrong platform. | `backend/vercel.json` |
| R3 | Replace the startup NLTK download with a read from `NLTK_DATA` (baked into the image). Fail loudly if missing rather than downloading. | `backend/app/main.py:20-27` |
| R4 | Drive CORS from a `FRONTEND_ORIGIN` env var (comma-separated). Keep localhost origins only when a `DEBUG`/`ENV=development` flag is set. Set `allow_credentials=False`. | `backend/app/main.py:33-50` |
| R5 | Add `GET /health` returning `{"status":"ok"}` for the platform health check. `/` currently serves this role but returns a heavier payload. | `backend/app/main.py` |
| R6 | Pin `requirements.txt` to exact versions (`==`) instead of `>=`. Floating minimums mean a rebuild months later can pull a breaking pandas/numpy major and fail in production only. | `backend/requirements.txt` |
| R7 | Extract the duplicated `API_BASE` fallback into `src/lib/api.ts`; throw at module load in production if `NEXT_PUBLIC_API_URL` is unset, so misconfiguration fails at build, not silently at runtime. | 3 frontend files |
| R8 | Add `.env.example` files for both apps documenting every variable. | new |
| R9 | Add `backend/.dockerignore` excluding `.venv/`, `__pycache__/`, `*.pyc`. Without it, the 200 MB local venv is uploaded to the build and may shadow site-packages. | new |

### 5.2 Platform configuration

| ID | Requirement |
|----|-------------|
| R10 | Vercel project: Root Directory = `frontend`, framework preset Next.js, install command `pnpm install` (a `pnpm-lock.yaml` is committed). |
| R11 | Vercel env var `NEXT_PUBLIC_API_URL` = the Render service URL, set for Production **and** Preview. |
| R12 | Render service: env vars `FRONTEND_ORIGIN`, `NLTK_DATA=/usr/local/share/nltk_data`, `ENV=production`. Health check path `/health`. |
| R13 | Both platforms auto-deploy from `main`. |

### 5.3 Acceptance criteria

- [ ] Vercel build succeeds from a clean clone with no manual intervention.
- [ ] `curl https://<render-url>/health` returns 200.
- [ ] Ticker search on the deployed frontend returns results (proves CORS + wiring).
- [ ] A 1-year RSI backtest completes without a gateway timeout.
- [ ] The analyse page renders real scraped headlines, not `_get_fallback_news()` output.
- [ ] Browser devtools show zero requests to `127.0.0.1` in production.
- [ ] A Vercel preview deployment on a branch also reaches the backend successfully.

---

## 6. Implementation Plan

### Phase 1 — Backend containerization (local)
1. Write `backend/Dockerfile` and `backend/.dockerignore` (R1, R9).
2. Refactor NLTK loading and CORS to be env-driven (R3, R4). Add `/health` (R5).
3. Pin dependencies (R6).
4. Verify locally: `docker build -t sp-backend ./backend && docker run -p 8001:8001 -e PORT=8001 sp-backend`, then hit `/health` and `/api/stocks/search?q=REL`.

**Gate:** the container must work locally before touching any hosting platform.
Debugging a Dockerfile through a remote build log is significantly slower.

### Phase 2 — Deploy the backend to Render (first-timer walkthrough)
1. Sign up at render.com with GitHub; authorize access to this repository.
2. **New → Web Service**, select the repo.
3. Set **Root Directory** to `backend`. This is the single most common first-time
   mistake — without it Render builds from the repo root and finds no Dockerfile.
4. Runtime **Docker** (Render auto-detects the Dockerfile). Instance type **Free**.
5. Add the env vars from R12. Leave `PORT` unset — Render injects it, and the
   Dockerfile must read `$PORT` rather than hardcoding a port.
6. Set the health check path to `/health`.
7. Deploy, watch the build log, then verify the public URL responds.

**Concepts worth internalizing before starting:** Render gives you a *service*
(your running container), a *build* (turning the repo into an image), and *env
vars* (injected at runtime, never committed). Free instances sleep after ~15
minutes of inactivity — the first request afterward will be slow. This is normal,
not a bug in your code.

### Phase 3 — Deploy the frontend to Vercel
1. Import the repo into Vercel.
2. Set **Root Directory** to `frontend` (R10) — this alone fixes the current failure.
3. Add `NEXT_PUBLIC_API_URL` = the Render URL for Production and Preview (R11).
4. Deploy.

`NEXT_PUBLIC_*` variables are inlined into the client bundle at **build** time.
Changing the value requires a redeploy; editing it in the dashboard alone does nothing.

### Phase 4 — Wire up and verify
1. Set `FRONTEND_ORIGIN` on Render to the deployed Vercel domain; redeploy the backend.
2. Walk the acceptance criteria in §5.3.
3. Refactor the frontend `API_BASE` duplication (R7) and commit `.env.example` files (R8).

---

## 7. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Google News blocks Render's egress IPs | Analyse page silently degrades to fallback headlines | `_get_fallback_news()` already prevents a hard failure. Surface a "live news unavailable" flag in the API response so the UI can be honest rather than showing stale data as real. |
| Free-tier cold starts (~30-50s) | Poor first impression | Accept for a personal project; upgrade to Render's paid tier or Railway if it becomes a real problem. Do **not** work around it with a cron pinger — that violates free-tier terms on most platforms. |
| `yfinance` is an unofficial, scraped API | Backtests break with no warning when Yahoo changes its endpoints | Pin the version (R6). Treat a data-source migration as a known future work item. |
| Preview deployments get rotating URLs that CORS rejects | Previews appear broken | Support a regex origin for `*.vercel.app` **only** when `ENV != production`, or list preview domains explicitly. |
| Vercel `NEXT_PUBLIC_API_URL` forgotten on Preview | Previews call localhost | R7's build-time assertion turns this into a loud build failure. |

---

## 8. Open Questions

1. Custom domain now or later? It affects CORS configuration and is cheap to defer.
2. Is the ~40s cold start acceptable, or is Railway's always-on paid tier worth it from day one?
3. Should backtest results be cached (Redis / on-disk) to blunt repeated identical runs? Deferred — no evidence of the need yet.

---

## 9. Appendix: Files Referenced

- `backend/vercel.json` — to be deleted (R2)
- `backend/app/main.py:20-27` — NLTK cold-start download (R3)
- `backend/app/main.py:33-50` — CORS origins and credentials (R4)
- `backend/requirements.txt` — unpinned dependencies (R6)
- `frontend/src/app/page.tsx:43` — `API_BASE` fallback (R7)
- `frontend/src/app/backtest/page.tsx:101` — `API_BASE` fallback (R7)
- `frontend/src/app/analyse/[ticker]/page.tsx:97` — `API_BASE` fallback (R7)
