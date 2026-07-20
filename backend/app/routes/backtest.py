import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.backtester import run_backtest
from typing import Dict, Any

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/backtest", tags=["Backtesting"])

class BacktestRequest(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol (e.g. RELIANCE.NS)")
    strategy: str = Field("RSI", description="Strategy name: 'RSI', 'SMA_Crossover', or 'Hybrid'")
    startDate: str = Field("2025-01-01", description="Start date (YYYY-MM-DD)")
    endDate: str = Field("2025-12-31", description="End date (YYYY-MM-DD)")
    initialCapital: float = Field(100000.0, ge=100.0, description="Initial capital in INR")
    fee: float = Field(0.001, ge=0.0, le=0.05, description="Transaction fee percentage (e.g. 0.001 for 0.1%)")
    rsiOversold: float = Field(30.0, ge=5.0, le=95.0, description="RSI buy threshold (Oversold)")
    rsiOverbought: float = Field(70.0, ge=5.0, le=95.0, description="RSI sell threshold (Overbought)")
    smaFast: int = Field(20, ge=2, le=100, description="SMA Fast period")
    smaSlow: int = Field(50, ge=5, le=300, description="SMA Slow period")

@router.post("")
def execute_backtest(req: BacktestRequest):
    """
    Executes a historical strategy simulation based on user parameters.
    """
    try:
        ticker = req.ticker.upper().strip()
        if not ticker.endswith(".NS") and not ticker.endswith(".BO"):
            if ticker.isdigit():
                ticker = f"{ticker}.BO"
            else:
                ticker = f"{ticker}.NS"

        results = run_backtest(
            ticker_symbol=ticker,
            start_date_str=req.startDate,
            end_date_str=req.endDate,
            strategy_name=req.strategy,
            initial_capital=req.initialCapital,
            transaction_fee_pct=req.fee,
            rsi_oversold=req.rsiOversold,
            rsi_overbought=req.rsiOverbought,
            sma_fast_period=req.smaFast,
            sma_slow_period=req.smaSlow
        )
        return results
    except Exception as e:
        logger.exception(f"Error executing backtest for {req.ticker}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error running backtest: {str(e)}")
