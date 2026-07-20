import os
import sys

# Try importing yfinance
try:
    import yfinance as yf
except ImportError:
    print("yfinance is not installed in the active environment.")
    print("Please run: pip install yfinance")
    sys.exit(1)

def main():
    print("=== stockportfolio.in Historical Data Downloader ===")
    
    # Prompt for ticker symbol
    ticker_input = input("Enter Stock Ticker (e.g. RELIANCE, TCS, INFY): ").strip().upper()
    if not ticker_input:
        print("Invalid ticker symbol.")
        return

    # Automatically format exchange suffix if missing
    ticker_symbol = ticker_input
    if not ticker_symbol.endswith(".NS") and not ticker_symbol.endswith(".BO"):
        if ticker_symbol.isdigit():
            ticker_symbol = f"{ticker_symbol}.BO"
        else:
            ticker_symbol = f"{ticker_symbol}.NS"
            
    print(f"Resolving ticker to: {ticker_symbol}")

    # Prompt for timeframe period
    print("\nSelect period:")
    print("1. 5 Days (5d)")
    print("2. 1 Month (1mo)")
    print("3. 6 Months (6mo)")
    print("4. 1 Year (1y)")
    print("5. 5 Years (5y)")
    print("6. Max History (max)")
    
    period_choice = input("Select option (1-6) [default: 4]: ").strip()
    period_map = {
        "1": "5d",
        "2": "1mo",
        "3": "6mo",
        "4": "1y",
        "5": "5y",
        "6": "max"
    }
    period = period_map.get(period_choice, "1y")

    # Prompt for interval
    print("\nSelect bar interval:")
    print("1. 5 Minutes (5m) - (only supported for periods <= 60d)")
    print("2. 30 Minutes (30m) - (only supported for periods <= 60d)")
    print("3. 1 Day (1d)")
    print("4. 1 Week (1wk)")
    print("5. 1 Month (1mo)")
    
    interval_choice = input("Select option (1-5) [default: 3]: ").strip()
    interval_map = {
        "1": "5m",
        "2": "30m",
        "3": "1d",
        "4": "1wk",
        "5": "1mo"
    }
    interval = interval_map.get(interval_choice, "1d")

    print(f"\nDownloading {ticker_symbol} price history (period={period}, interval={interval})...")
    
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period=period, interval=interval)
        
        if hist.empty:
            print(f"Error: No historical data returned for symbol {ticker_symbol}")
            return
            
        # Strip timezone from index for cleaner CSV output
        if hist.index.tz is not None:
            hist.index = hist.index.tz_localize(None)

        filename = f"{ticker_input}_history_{period}_{interval}.csv"
        hist.to_csv(filename)
        
        print(f"\nSUCCESS: Saved {len(hist)} records to '{filename}'!")
        print(f"File path: {os.path.abspath(filename)}")
        
        # Print a small preview
        print("\nData Preview (Last 5 rows):")
        print(hist.tail()[["Open", "High", "Low", "Close", "Volume"]])
        
    except Exception as e:
        print(f"Error fetching data: {str(e)}")

if __name__ == "__main__":
    main()
