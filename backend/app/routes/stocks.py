import logging
from fastapi import APIRouter, HTTPException, Query
from app import symbols as symbol_master
from app.scraper import GoogleNewsScraper
from app.analysis import PriceDataUnavailable, get_stock_analysis
from typing import List, Dict, Any

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stocks", tags=["Stocks"])

scraper = GoogleNewsScraper()

@router.get("/search")
def search_stocks(q: str = Query(..., min_length=1, description="Search query for ticker symbol or company name")):
    """
    Search list of stock tickers by ticker symbol or company name against the NSE symbol master.
    """
    q_clean = q.strip()
    if not q_clean:
        return []

    results = symbol_master.search(q_clean, limit=10)
    if results:
        return [
            {
                "symbol": f"{record.symbol}.NS",
                "name": record.name,
                "exchange": "NSE",
            }
            for record in results
        ]

    # Fallback if someone entered an explicit BSE scrip code or symbol
    upper_q = q_clean.upper()
    if upper_q.isdigit():
        return [{"symbol": f"{upper_q}.BO", "name": f"BSE Scrip {upper_q}", "exchange": "BSE"}]

    clean_sym = upper_q.replace(".NS", "").replace(".BO", "")
    return [
        {"symbol": f"{clean_sym}.NS", "name": clean_sym, "exchange": "NSE"},
    ]

@router.get("/lookup")
def lookup_stocks(
    q: str = Query(..., min_length=2, description="Symbol or company name"),
    limit: int = Query(10, ge=1, le=50),
):
    """Search the real NSE symbol master.

    Distinct from /search above, which matches against a hardcoded list of ~30
    tickers and, failing that, fabricates an entry like "NSE Stock FOO" for
    whatever was typed. That is fine for a demo and wrong for a portfolio: a
    user can add a holding in a symbol that does not exist. This endpoint only
    ever returns instruments Fyers can actually quote, and returns nothing when
    there is no match.
    """
    results = symbol_master.search(q, limit=limit)
    return {
        "query": q,
        "count": len(results),
        "results": [
            {
                "symbol": record.symbol,
                "name": record.name,
                "sector": record.sector,
                "cap": record.cap,
                "fyers": record.fyers,
            }
            for record in results
        ],
    }


@router.get("/analyse")
def analyse_stock(
    ticker: str = Query(..., description="Stock ticker symbol (e.g. RELIANCE.NS)"),
    timeframe: str = Query("month", description="Timeframe filter: 'day', 'week', 'month', 'year'")
):
    """
    Scrapes online news related to ticker, runs sentiment analysis,
    calculates technical indicators, and provides overbought/underbought suggestion.
    """
    ticker = ticker.upper().strip()
    if not ticker.endswith(".NS") and not ticker.endswith(".BO"):
        if ticker.isdigit():
            ticker = f"{ticker}.BO"
        else:
            ticker = f"{ticker}.NS"
            
    # Clean symbol for news query (e.g. RELIANCE.NS -> Reliance Industries or RELIANCE share price)
    clean_query = ticker.replace(".NS", "").replace(".BO", "")
    
    # Find readable name in symbol master for better news scraping query
    matched = symbol_master.lookup(clean_query)
    company_name = matched.name if matched else clean_query
    news_search_query = f"{company_name} share price news"
    
    try:
        # 1. Scrape News
        headlines_data = scraper.fetch_news(news_search_query)
        headlines_list = [h["title"] for h in headlines_data]
        
        # 2. Get Stock Analysis (Technicals + Sentiment + Decision)
        analysis_result = get_stock_analysis(ticker, headlines_list, timeframe=timeframe)
        
        # Add the detailed scraped news list in response
        analysis_result["news"] = headlines_data
        
        return analysis_result

    except PriceDataUnavailable as e:
        # Upstream had no prices. A 502 with the reason is honest; the previous
        # behaviour was a fabricated analysis returned with HTTP 200.
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception(f"Error in analyse endpoint for {ticker}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing stock data: {str(e)}")

@router.get("/history")
def get_stock_history(
    ticker: str = Query(..., description="Stock ticker symbol (e.g. RELIANCE.NS)"),
    period: str = Query("1y", description="Timeframe period: '5d', '1mo', '6mo', '1y', '5y', 'max'"),
    interval: str = Query("1d", description="Bar interval: '5m', '30m', '1d', '1wk', '1mo'"),
    export_format: str = Query("json", description="Output format: 'json' or 'csv'")
):
    """
    Exposes raw historical stock price data (OHLCV) directly under an API.
    Can return data in JSON format or stream it as a CSV file download.
    """
    from fastapi.responses import StreamingResponse
    import io
    import yfinance as yf

    ticker = ticker.upper().strip()
    if not ticker.endswith(".NS") and not ticker.endswith(".BO"):
        if ticker.isdigit():
            ticker = f"{ticker}.BO"
        else:
            ticker = f"{ticker}.NS"

    try:
        ticker_obj = yf.Ticker(ticker)
        hist = ticker_obj.history(period=period, interval=interval)

        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No historical price data returned for ticker {ticker}")

        # Strip timezone from index to keep formatting clean
        if hist.index.tz is not None:
            hist.index = hist.index.tz_localize(None)

        if export_format == "csv":
            # Generate CSV in memory and stream
            stream = io.StringIO()
            hist.to_csv(stream)
            response = StreamingResponse(
                iter([stream.getvalue()]),
                media_type="text/csv"
            )
            response.headers["Content-Disposition"] = f"attachment; filename={ticker}_history_{period}_{interval}.csv"
            return response

        # Default JSON format
        records = []
        for index, row in hist.iterrows():
            records.append({
                "date": index.isoformat(),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"])
            })

        return {
            "symbol": ticker,
            "period": period,
            "interval": interval,
            "records_count": len(records),
            "data": records
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching historical data for {ticker}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching historical data: {str(e)}")


@router.get("/{symbol}/technicals")
def get_stock_technicals(symbol: str):
    """Calculates indicators (RSI, Moving Averages, MACD, ADX, Bollinger) and returns a ScoreCard."""
    import yfinance as yf
    from app.technicals import extract_technicals, score_technicals

    canonical = symbol_master.canonical(symbol) or symbol.upper()
    yf_sym = symbol_master.to_yfinance(canonical) or f"{canonical}.NS"

    try:
        ticker = yf.Ticker(yf_sym)
        hist = ticker.history(period="1y", interval="1d")
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No price history found for {symbol}")

        if hist.index.tz is not None:
            hist.index = hist.index.tz_localize(None)

        extracted = extract_technicals(hist)
        scorecard = score_technicals(extracted)

        return {
            "symbol": canonical,
            "indicators": extracted,
            "scorecard": scorecard.as_dict(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error evaluating technicals for %s", symbol)
        raise HTTPException(status_code=500, detail=f"Technicals calculation failed: {exc}")


@router.get("/{symbol}/fundamentals")
def get_stock_fundamentals(
    symbol: str,
    sector_relative: bool = Query(
        False,
        description=(
            "Grade valuation and quality against sector peers as well as "
            "absolute bands. Costs up to a dozen extra upstream fetches on a "
            "cold cache, so it is opt-in."
        ),
    ),
):
    """Fetches Screener.in/yfinance fundamentals, Piotroski F-score, Altman Z, and returns a ScoreCard."""
    from app.fundamentals import (
        get_fundamentals,
        score_fundamentals,
        score_fundamentals_relative,
    )

    canonical = symbol_master.canonical(symbol) or symbol.upper()
    try:
        if sector_relative:
            scorecard, data = score_fundamentals_relative(canonical)
        else:
            data = get_fundamentals(canonical)
            scorecard = score_fundamentals(data)

        return {
            "symbol": canonical,
            "sector_relative": sector_relative,
            "fundamentals": data,
            "scorecard": scorecard.as_dict(),
        }
    except Exception as exc:
        logger.exception("Error evaluating fundamentals for %s", symbol)
        raise HTTPException(status_code=500, detail=f"Fundamentals calculation failed: {exc}")

