import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Load .env before anything reads os.getenv below. Real environment variables
# always take precedence, so this is a no-op in production.
from app.dotenv_lite import load_env_file

load_env_file(Path(__file__).resolve().parent.parent / ".env")

import nltk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.stocks import router as stocks_router
from app.routes.backtest import router as backtest_router
from app.routes.mutual_funds import router as mutual_funds_router
from app.routes.fyers import router as fyers_router
from app.routes.portfolio import router as portfolio_router
from app.routes.recommendations import router as recommendations_router
from app.routes.screener import router as screener_router
from app.routes.engine import router as engine_router
from app.routes.options import router as options_router
from app.routes.quant import router as quant_router
from app.routes.ai import router as ai_router
from app.routes.accounts import router as accounts_router
from app.routes.paper import router as paper_router
from app.routes.admin import router as admin_router
from app.routes.macro import router as macro_router
from app.routes.market_pulse import router as market_pulse_router
from app.routes.ml import router as ml_router

# Configure logging to output UTF-8 to stdout/stderr
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

IS_PRODUCTION = os.getenv("ENV", "development").lower() == "production"

# The VADER lexicon is baked into the image at build time (see Dockerfile).
# In production a missing corpus is a broken deploy, so fail loudly at import
# rather than downloading on the request path. Locally, fall back to a download.
if NLTK_DATA := os.getenv("NLTK_DATA"):
    nltk.data.path.append(NLTK_DATA)

try:
    nltk.data.find("sentiment/vader_lexicon.zip")
except LookupError:
    if IS_PRODUCTION:
        raise RuntimeError(
            "vader_lexicon not found on NLTK_DATA path. It should have been "
            "installed at image build time; check the Dockerfile."
        )
    logger.info("vader_lexicon missing, downloading for local development...")
    nltk.download("vader_lexicon", quiet=True)

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Start the nightly scheduler on boot, stop it on shutdown.

    Both halves are no-ops unless ENABLE_SCHEDULER is set and a DATABASE_URL is
    configured, so the default deployment starts exactly as it did before this
    was added.
    """
    from app import scheduler

    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown()


app = FastAPI(
    title="stockportfolio.in - Portfolio Intelligence & Quant API",
    description=(
        "Portfolio valuation, danger and growth scoring, NSE screening, "
        "option-chain hedging, event-driven backtesting, portfolio optimisation, "
        "paper trading and AI narration for Indian markets. Read-only: there is "
        "no order-placement path anywhere in this service."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# Allowed browser origins. In production this is driven entirely by
# FRONTEND_ORIGIN (comma-separated) so that attaching a custom domain is a
# config change, not a code change.
origins = [
    o.strip() for o in os.getenv("FRONTEND_ORIGIN", "").split(",") if o.strip()
]

# Vercel gives every branch preview a fresh subdomain, so previews can only be
# matched by pattern rather than listed. Keeping the pattern in config lets it
# stay scoped to this project's own subdomains, instead of trusting every
# *.vercel.app deployment on the internet. Starlette fullmatches it.
origin_regex = os.getenv("PREVIEW_ORIGIN_REGEX") or None

if not IS_PRODUCTION:
    # Any localhost port, rather than a hardcoded 3000-3002 list: Next picks a
    # different port whenever the default is busy, and the symptom of a missing
    # one is a silent CORS failure that looks like a broken API. Only ever
    # applied outside production, where the loopback interface is the developer.
    dev_regex = r"http://(localhost|127\.0\.0\.1):\d+"
    origin_regex = (
        f"({origin_regex})|({dev_regex})" if origin_regex
        else f"({dev_regex})|(https://[a-z0-9-]+\\.vercel\\.app)"
    )

if IS_PRODUCTION and not origins:
    raise RuntimeError("FRONTEND_ORIGIN must be set when ENV=production.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=origin_regex,
    # No cookies or Authorization headers are used; keeping this False avoids
    # pairing credentialed requests with a wildcard-ish origin set.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(stocks_router, prefix="/api")
app.include_router(backtest_router, prefix="/api")
app.include_router(mutual_funds_router, prefix="/api")
app.include_router(fyers_router, prefix="/api")
app.include_router(portfolio_router, prefix="/api")
app.include_router(screener_router, prefix="/api")
app.include_router(engine_router, prefix="/api")
app.include_router(options_router, prefix="/api")
app.include_router(quant_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(accounts_router, prefix="/api")
app.include_router(paper_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(recommendations_router, prefix="/api")
app.include_router(macro_router, prefix="/api")
app.include_router(market_pulse_router, prefix="/api")
app.include_router(ml_router, prefix="/api")

@app.get("/health")
def health_check():
    """Lightweight liveness probe for the hosting platform's health check.

    Deliberately does not touch the database: a health check that fails when an
    optional subsystem is down takes the whole service out of rotation over a
    feature most requests never use. Subsystem state is reported at /status.
    """
    return {"status": "ok"}


@app.get("/status")
def status():
    """Which optional subsystems are configured. Never fails."""
    from app import redis_client, scheduler
    from app.ai import is_configured as ai_configured
    from app.db import is_enabled as db_enabled
    from app.secrets import admin_token, encryption_available

    return {
        "status": "ok",
        "version": "2.0.0",
        "subsystems": {
            "database": db_enabled(),
            "redis": redis_client.ping(),
            "scheduler": scheduler.status().get("running", False),
            "job_store": scheduler.store_kind(),
            "ai_narrative": ai_configured(),
            "token_encryption": encryption_available(),
            "admin_endpoints": admin_token() is not None,
        },
        "note": (
            "Every subsystem here is optional. With all of them off the service "
            "still values portfolios, scores holdings, screens the universe, "
            "backtests, optimises and sizes hedges - those paths are stateless "
            "and need no configuration."
        ),
    }


@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "NSE/BSE Stock Analysis and Backtesting API is running.",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    # Make sure execution is clean
    logger.info("Starting uvicorn server...")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, reload=True)
