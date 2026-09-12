import logging
import nltk
import pandas as pd
import numpy as np
import yfinance as yf
from typing import Dict, Any, List
from datetime import datetime, timedelta

from nltk.sentiment.vader import SentimentIntensityAnalyzer
from app.technicals import calculate_rsi

logger = logging.getLogger(__name__)


class PriceDataUnavailable(Exception):
    """Raised when no real price history could be fetched for a symbol."""


# Initialize VADER Sentiment Analyzer
try:
    sia = SentimentIntensityAnalyzer()
except Exception as e:
    logger.error(f"Error initializing NLTK Sentiment Intensity Analyzer: {e}")
    sia = None

def analyze_sentiment(headlines: List[str]) -> Dict[str, Any]:
    """
    Analyzes sentiment of news headlines using NLTK VADER.
    Returns average compound, positive, negative, and neutral scores.
    """
    if not headlines or not sia:
        return {"compound": 0.0, "pos": 0.0, "neg": 0.0, "neu": 1.0, "count": 0}

    scores = []
    for headline in headlines:
        try:
            score = sia.polarity_scores(headline)
            scores.append(score)
        except Exception as e:
            logger.debug(f"Error sentiment-analyzing headline: {e}")
            continue

    if not scores:
        return {"compound": 0.0, "pos": 0.0, "neg": 0.0, "neu": 1.0, "count": 0}

    avg_compound = float(np.mean([s["compound"] for s in scores]))
    avg_pos = float(np.mean([s["pos"] for s in scores]))
    avg_neg = float(np.mean([s["neg"] for s in scores]))
    avg_neu = float(np.mean([s["neu"] for s in scores]))

    return {
        "compound": round(avg_compound, 4),
        "pos": round(avg_pos, 4),
        "neg": round(avg_neg, 4),
        "neu": round(avg_neu, 4),
        "count": len(scores)
    }

def get_stock_analysis(ticker_symbol: str, news_headlines: List[str], timeframe: str = "month") -> Dict[str, Any]:
    """
    Fetches stock metadata and historical data for technical analysis based on timeframe.
    Combines it with news sentiment to suggest Buy/Sell/Hold rating.
    """
    logger.info(f"Analyzing stock ticker: {ticker_symbol} | Timeframe: {timeframe}")
    
    # Map timeframe to yfinance query parameters
    # We fetch a larger window to calculate indicators cleanly, then slice later.
    period = "1y"
    interval = "1d"
    date_format = "%b %d"
    slice_len = 22
    
    if timeframe == "day":
        period = "5d"
        interval = "5m"
        date_format = "%H:%M"
        slice_len = 75
    elif timeframe == "week":
        period = "1mo"
        interval = "30m"
        date_format = "%b %d, %H:%M"
        slice_len = 65
    elif timeframe == "month":
        period = "1y"
        interval = "1d"
        date_format = "%b %d"
        slice_len = 22
    elif timeframe == "year":
        period = "2y"
        interval = "1d"
        date_format = "%Y-%m-%d"
        slice_len = 252

    # Try fetching yfinance data
    try:
        ticker = yf.Ticker(ticker_symbol)
        
        # Fetch historical data
        hist = ticker.history(period=period, interval=interval)
            
        if hist.empty:
            raise ValueError(f"No historical price data returned for ticker {ticker_symbol}")

        # Strip timezone from index to avoid errors
        if hist.index.tz is not None:
            hist.index = hist.index.tz_localize(None)

        # Fetch basic stock info / meta
        info = ticker.info
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        
        # Fallback for current price from history
        if current_price is None and not hist.empty:
            current_price = float(hist["Close"].iloc[-1])
            
        previous_close = info.get("regularMarketPreviousClose") or (float(hist["Close"].iloc[-2]) if len(hist) > 1 else current_price)
        price_change = current_price - previous_close if current_price and previous_close else 0.0
        price_change_pct = (price_change / previous_close) * 100.0 if previous_close else 0.0
        
        name = info.get("longName") or info.get("shortName") or ticker_symbol
        day_high = info.get("dayHigh") or float(hist["High"].iloc[-1])
        day_low = info.get("dayLow") or float(hist["Low"].iloc[-1])
        volume = info.get("volume") or int(hist["Volume"].iloc[-1])
        fifty_two_week_high = info.get("fiftyTwoWeekHigh") or float(hist["High"].max())
        fifty_two_week_low = info.get("fiftyTwoWeekLow") or float(hist["Low"].min())
        currency = info.get("currency") or "INR"

    except Exception as e:
        # No mock fallback. This function's output is a buy/sell/hold call, and
        # inventing a 1500.00 price plus a random-walk history to keep the
        # endpoint "resilient" produces a confident recommendation about a
        # security nobody priced. Failing visibly is the only safe answer.
        logger.warning("No price data for %s: %s", ticker_symbol, e)
        raise PriceDataUnavailable(
            f"No price history available for {ticker_symbol}: {e}"
        ) from e

    # --- Technical Indicators Calculation ---
    close_prices = hist["Close"]
    
    # RSI (14 period)
    rsi_series = calculate_rsi(close_prices, 14)
    current_rsi = float(rsi_series.iloc[-1])
    
    # SMAs (20, 50, 200)
    sma20 = float(close_prices.rolling(window=20).mean().iloc[-1]) if len(close_prices) >= 20 else current_price
    sma50 = float(close_prices.rolling(window=50).mean().iloc[-1]) if len(close_prices) >= 50 else current_price
    sma200 = float(close_prices.rolling(window=200).mean().iloc[-1]) if len(close_prices) >= 200 else current_price

    # EMAs (20, 50)
    ema20 = float(close_prices.ewm(span=20, adjust=False).mean().iloc[-1]) if len(close_prices) >= 20 else current_price
    ema50 = float(close_prices.ewm(span=50, adjust=False).mean().iloc[-1]) if len(close_prices) >= 50 else current_price

    # Sentiment Analysis
    sentiment = analyze_sentiment(news_headlines)
    sentiment_score = sentiment["compound"]

    # --- Combined Decision Logic ---
    # 1. RSI Indicator Mapping
    # Oversold (RSI < 30) is underbought, so Bullish indicator
    # Overbought (RSI > 70) is overbought, so Bearish indicator
    if current_rsi < 30:
        rsi_signal_score = 95  # Strong Underbought (Bullish)
        rsi_desc = "Oversold (Underbought)"
    elif current_rsi < 40:
        rsi_signal_score = 75  # Moderate Underbought
        rsi_desc = "Accumulation Zone"
    elif current_rsi > 70:
        rsi_signal_score = 10  # Strong Overbought (Bearish)
        rsi_desc = "Overbought (Sell Alert)"
    elif current_rsi > 60:
        rsi_signal_score = 30  # Moderate Overbought
        rsi_desc = "Distribution Zone"
    else:
        rsi_signal_score = 50  # Neutral
        rsi_desc = "Neutral RSI"

    # 2. News Sentiment mapping
    if sentiment_score > 0.3:
        sent_signal_score = 90  # Very positive
        sent_desc = "Strong Positive News Sentiment"
    elif sentiment_score > 0.1:
        sent_signal_score = 70  # Positive
        sent_desc = "Positive News Sentiment"
    elif sentiment_score < -0.3:
        sent_signal_score = 10  # Very negative
        sent_desc = "Strong Negative News Sentiment"
    elif sentiment_score < -0.1:
        sent_signal_score = 30  # Negative
        sent_desc = "Negative News Sentiment"
    else:
        sent_signal_score = 50  # Neutral
        sent_desc = "Neutral News Sentiment"

    # 3. Combine scores (RSI 60%, Sentiment 40%)
    combined_score = 0.6 * rsi_signal_score + 0.4 * sent_signal_score
    
    # Classify decision
    if combined_score >= 80:
        decision = "STRONG BUY"
        interpretation = f"The stock is significantly underbought (RSI: {current_rsi:.1f}) accompanied by highly positive online sentiment. Favorable conditions for long positions."
    elif combined_score >= 60:
        decision = "BUY"
        interpretation = f"Stock is in the oversold/accumulation region (RSI: {current_rsi:.1f}) and news sentiment is generally constructive."
    elif combined_score >= 40:
        decision = "HOLD"
        interpretation = f"Both technical momentum (RSI: {current_rsi:.1f}) and external news sentiment are balanced in a neutral range."
    elif combined_score >= 25:
        decision = "SELL"
        interpretation = f"Stock shows signs of being overbought (RSI: {current_rsi:.1f}) with weakening news sentiment. Consider trimming positions."
    else:
        decision = "STRONG SELL"
        interpretation = f"Stock is heavily overbought (RSI: {current_rsi:.1f}) and faces highly negative news catalysts. Risk of correction is elevated."

    # Format chart data sliced dynamically based on timeframe
    chart_history = []
    recent_hist = hist.tail(slice_len)
    for index, row in recent_hist.iterrows():
        chart_history.append({
            "date": index.strftime(date_format),
            "close": round(float(row["Close"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "volume": int(row["Volume"])
        })

    return {
        "symbol": ticker_symbol,
        "name": name,
        "price": round(current_price, 2) if current_price else None,
        "change": round(price_change, 2),
        "change_pct": round(price_change_pct, 2),
        "details": {
            "day_high": round(day_high, 2),
            "day_low": round(day_low, 2),
            "volume": volume,
            "fifty_two_week_high": round(fifty_two_week_high, 2),
            "fifty_two_week_low": round(fifty_two_week_low, 2),
            "currency": currency
        },
        "technicals": {
            "rsi": round(current_rsi, 2),
            "rsi_desc": rsi_desc,
            "sma20": round(sma20, 2),
            "sma50": round(sma50, 2),
            "sma200": round(sma200, 2),
            "ema20": round(ema20, 2),
            "ema50": round(ema50, 2),
            "trend": "Bullish" if current_price > sma50 else "Bearish"
        },
        "sentiment": {
            "compound": sentiment["compound"],
            "pos": sentiment["pos"],
            "neg": sentiment["neg"],
            "neu": sentiment["neu"],
            "count": sentiment["count"],
            "desc": sent_desc
        },
        "recommendation": {
            "score": round(combined_score, 1),
            "decision": decision,
            "interpretation": interpretation
        },
        "chart_data": chart_history
    }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    mock_headlines = [
        "Reliance Industries sets new profit record in Q4",
        "Analysts bullish on Mukesh Ambani's digital strategy",
        "Markets hit record highs as Reliance surges 2%",
        "Concerns rise over capital expenditure levels"
    ]
    res = get_stock_analysis("RELIANCE.NS", mock_headlines)
    print("Stock name:", res["name"])
    print("Price:", res["price"])
    print("RSI:", res["technicals"]["rsi"])
    print("Sentiment score:", res["sentiment"]["compound"])
    print("Recommendation Score:", res["recommendation"]["score"])
    print("Decision:", res["recommendation"]["decision"])
    print("Interpretation:", res["recommendation"]["interpretation"])
