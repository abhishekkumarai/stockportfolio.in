import logging
from fastapi import APIRouter, HTTPException, Query
from app.scraper import GoogleNewsScraper
from app.analysis import get_stock_analysis
from typing import List, Dict, Any

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stocks", tags=["Stocks"])

# Pre-seeded popular Indian tickers for autocomplete search
POPULAR_TICKERS = [
    {"symbol": "RELIANCE.NS", "name": "Reliance Industries Limited", "exchange": "NSE"},
    {"symbol": "TCS.NS", "name": "Tata Consultancy Services Limited", "exchange": "NSE"},
    {"symbol": "INFY.NS", "name": "Infosys Limited", "exchange": "NSE"},
    {"symbol": "HDFCBANK.NS", "name": "HDFC Bank Limited", "exchange": "NSE"},
    {"symbol": "ICICIBANK.NS", "name": "ICICI Bank Limited", "exchange": "NSE"},
    {"symbol": "BHARTIARTL.NS", "name": "Bharti Airtel Limited", "exchange": "NSE"},
    {"symbol": "SBIN.NS", "name": "State Bank of India", "exchange": "NSE"},
    {"symbol": "ITC.NS", "name": "ITC Limited", "exchange": "NSE"},
    {"symbol": "LICI.NS", "name": "Life Insurance Corporation of India", "exchange": "NSE"},
    {"symbol": "HINDUNILVR.NS", "name": "Hindustan Unilever Limited", "exchange": "NSE"},
    {"symbol": "LT.NS", "name": "Larsen & Toubro Limited", "exchange": "NSE"},
    {"symbol": "TATAMOTORS.NS", "name": "Tata Motors Limited", "exchange": "NSE"},
    {"symbol": "AXISBANK.NS", "name": "Axis Bank Limited", "exchange": "NSE"},
    {"symbol": "ONGC.NS", "name": "Oil and Natural Gas Corporation Limited", "exchange": "NSE"},
    {"symbol": "ADANIENT.NS", "name": "Adani Enterprises Limited", "exchange": "NSE"},
    {"symbol": "SUNPHARMA.NS", "name": "Sun Pharmaceutical Industries Limited", "exchange": "NSE"},
    {"symbol": "M&M.NS", "name": "Mahindra & Mahindra Limited", "exchange": "NSE"},
    {"symbol": "NTPC.NS", "name": "NTPC Limited", "exchange": "NSE"},
    {"symbol": "POWERGRID.NS", "name": "Power Grid Corporation of India Limited", "exchange": "NSE"},
    {"symbol": "BAJFINANCE.NS", "name": "Bajaj Finance Limited", "exchange": "NSE"},
    {"symbol": "COALINDIA.NS", "name": "Coal India Limited", "exchange": "NSE"},
    {"symbol": "TATASTEEL.NS", "name": "Tata Steel Limited", "exchange": "NSE"},
    {"symbol": "MARUTI.NS", "name": "Maruti Suzuki India Limited", "exchange": "NSE"},
    {"symbol": "HCLTECH.NS", "name": "HCL Technologies Limited", "exchange": "NSE"},
    {"symbol": "ADANIPORTS.NS", "name": "Adani Ports and Special Economic Zone Limited", "exchange": "NSE"},
    
    # Popular BSE tickers
    {"symbol": "500325.BO", "name": "Reliance Industries Limited", "exchange": "BSE"},
    {"symbol": "532540.BO", "name": "Tata Consultancy Services Limited", "exchange": "BSE"},
    {"symbol": "500209.BO", "name": "Infosys Limited", "exchange": "BSE"},
    {"symbol": "500180.BO", "name": "HDFC Bank Limited", "exchange": "BSE"},
    {"symbol": "532174.BO", "name": "ICICI Bank Limited", "exchange": "BSE"}
]

scraper = GoogleNewsScraper()

@router.get("/search")
def search_stocks(q: str = Query(..., min_length=1, description="Search query for ticker symbol or company name")):
    """
    Search list of popular stock tickers by ticker symbol or name.
    If no matches in popular list, allows creation of dynamic ticker query.
    """
    q_lower = q.lower().strip()
    
    # Filter pre-seeded tickers
    results = [
        t for t in POPULAR_TICKERS 
        if q_lower in t["symbol"].lower() or q_lower in t["name"].lower()
    ]
    
    # If no results and it looks like a custom ticker symbol, suggest it
    if not results:
        upper_q = q.upper().strip()
        # Handle BSE/NSE conversions automatically if not suffixed
        if upper_q.isdigit():
            results.append({"symbol": f"{upper_q}.BO", "name": f"BSE Stock {upper_q}", "exchange": "BSE"})
        elif not upper_q.endswith(".NS") and not upper_q.endswith(".BO"):
            results.append({"symbol": f"{upper_q}.NS", "name": f"NSE Stock {upper_q}", "exchange": "NSE"})
            results.append({"symbol": f"{upper_q}.BO", "name": f"BSE Stock {upper_q}", "exchange": "BSE"})
        else:
            exch = "BSE" if upper_q.endswith(".BO") else "NSE"
            results.append({"symbol": upper_q, "name": f"Custom Stock {upper_q}", "exchange": exch})
            
    return results[:10]

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
    
    # Find readable name in list for better news scraping query
    matched = next((t for t in POPULAR_TICKERS if t["symbol"] == ticker), None)
    news_search_query = f"{matched['name'] if matched else clean_query} share price news"
    
    try:
        # 1. Scrape News
        headlines_data = scraper.fetch_news(news_search_query)
        headlines_list = [h["title"] for h in headlines_data]
        
        # 2. Get Stock Analysis (Technicals + Sentiment + Decision)
        analysis_result = get_stock_analysis(ticker, headlines_list, timeframe=timeframe)
        
        # Add the detailed scraped news list in response
        analysis_result["news"] = headlines_data
        
        return analysis_result

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
