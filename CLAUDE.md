# CLAUDE.md

## Backend Python environment (uv)

`backend/`'s virtualenv and dependencies are managed by
[uv](https://docs.astral.sh/uv/) — `backend/pyproject.toml` (dependencies +
the `dev` group) and `backend/uv.lock` (resolved versions/hashes). There is
no `requirements.txt` and `app/` is never `pip install`-ed as a package
(`[tool.uv] package = false` — it runs in place via `python -m app.main` /
`uvicorn app.main:app`, and `pytest.ini` puts `backend/` on `sys.path`
directly).

**Setup / sync deps:**
```bash
cd backend
uv sync
```

**Run without activating** (prefix commands with `uv run`):
```bash
uv run python -m app.main                       # FastAPI on :8001
uv run uvicorn app.main:app --port 8001 --reload
uv run pytest -v
```

**Manual activation** (when a shell needs the venv on `PATH` directly):
```bash
# PowerShell
.venv\Scripts\Activate.ps1
# cmd
.venv\Scripts\activate.bat
# Git Bash
source .venv/Scripts/activate
```

**Adding a dependency:**
```bash
uv add <package>              # runtime dependency
uv add --group dev <package>  # dev-only (e.g. test tooling)
```
Commit the updated `pyproject.toml` and `uv.lock` together.

The production Docker image (`backend/Dockerfile`) builds with
`uv sync --frozen --no-dev`, so the `dev` group (pytest, httpx2) never ships.

## Flutter Web frontend (`flutter_app/`)

Rewrite of `frontend/` (Next.js) in Flutter Web, same FastAPI backend. Tracked in Jira
project REC, Epics 8-13 (REC-83 to REC-88). `frontend/` stays until parity is confirmed.

```bash
cd flutter_app
flutter pub get
flutter analyze && flutter test
flutter run -d chrome --dart-define=API_URL=http://127.0.0.1:8001   # dev
flutter build web --release --dart-define=API_URL=https://<api>     # release
```

- `API_URL` is a `--dart-define`; release builds throw if it is unset (`lib/core/config.dart`).
- Layout: `lib/core` (config, theme tokens, http client, auth, nav config), `lib/widgets`
  (shell, common widgets, charts), `lib/features/<area>` (pages), `lib/router.dart`
  (go_router; auth guard replaces `middleware.ts`; page builders registered in `pageBuilders`).
- Nav is driven by `lib/core/nav_config.dart` only; add a route there and in `pageBuilders`.
- Pages read backend JSON as loose maps (`asMap`/`asList`/`asNum`), mirroring `frontend/src/lib/*Api.ts`.
- Zero mock data: feeds without a source return `{items: [], source: "not_connected"}` from
  `backend/app/routes/market_data.py` and the UI shows an empty state saying so.
- Deep links need an SPA fallback: `flutter_app/vercel.json` (Vercel) and `nginx.conf` (Docker).
  A plain `python -m http.server` 404s on `/screener`.
- Compose runs it as `flutter-web` on :3004 beside the Next.js `frontend` service.
- The installed `file_picker` 13 API is `FilePicker.pickFile()` + `readAsBytes()`.

### Deploying the Flutter site

Production (www.stockportfolio.in) is the Vercel project `stockportfolio-in`, fed only by
`.github/workflows/deploy-flutter.yml` (build, analyze, test, then `vercel deploy --prebuilt --prod`).
The Vercel project does **not** build from git (Ignored Build Step `exit 0`, no root directory),
so pushing to `main` cannot put Next.js live. Needs GitHub secret `VERCEL_TOKEN` and variables
`VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `API_URL`; without them the workflow builds and tests but skips
the deploy. Routing/no-cache config for the output lives in `flutter_app/vercel-output/config.json`.
Roll back by promoting the previous deployment in the Vercel dashboard. Details: `docs/DEPLOYMENT_PRD.md` section 10.
