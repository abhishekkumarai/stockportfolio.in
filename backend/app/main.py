import logging
import os
import sys
import nltk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.stocks import router as stocks_router
from app.routes.backtest import router as backtest_router

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

app = FastAPI(
    title="NSE/BSE Stock Analyst & Backtesting API",
    description="Backend API for stock analysis, news sentiment parsing, and strategy backtesting",
    version="1.0.0"
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
    origins += [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
    ]
    origin_regex = origin_regex or r"https://[a-z0-9-]+\.vercel\.app"

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

@app.get("/health")
def health_check():
    """Lightweight liveness probe for the hosting platform's health check."""
    return {"status": "ok"}


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
