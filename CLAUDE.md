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
