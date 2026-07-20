import logging
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

# Pre-download VADER Lexicon on startup
nltk.data.path.append('/tmp')
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    logger.info("Initializing NLTK vader_lexicon download...")
    nltk.download('vader_lexicon', download_dir='/tmp', quiet=True)

app = FastAPI(
    title="NSE/BSE Stock Analyst & Backtesting API",
    description="Backend API for stock analysis, news sentiment parsing, and strategy backtesting",
    version="1.0.0"
)

# Enable CORS for Next.js development and production origins
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
    "chrome-extension://eppiocemhmnlbhjplcgkofciiegomcon",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?|https://.*\.vercel\.app|chrome-extension://[a-z]+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(stocks_router, prefix="/api")
app.include_router(backtest_router, prefix="/api")

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
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)
