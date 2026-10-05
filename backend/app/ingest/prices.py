"""Price-derived stats via yfinance: annualized volatility, beta vs SPY,
95th-percentile 1-year drawdown, and market cap. These feed the impact
model's shock sources (scoring/impact.py) for categories without a more
specific driver (FX, rates, etc.).
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import yfinance as yf

TRADING_DAYS_PER_YEAR = 252


@dataclass
class PriceStatResult:
    ann_vol: float | None
    beta: float | None
    dd95_1y: float | None
    mcap: float | None


def _daily_log_returns(close: pd.Series) -> pd.Series:
    return np.log(close / close.shift(1)).dropna()


def _max_rolling_drawdowns(close: pd.Series) -> pd.Series:
    """Drawdown at each point = price / running peak - 1 (<=0)."""
    running_peak = close.cummax()
    return close / running_peak - 1.0


def compute_price_stats(ticker: str, benchmark: str = "^GSPC") -> PriceStatResult:
    hist = yf.Ticker(ticker).history(period="2y", auto_adjust=True)
    if hist.empty or len(hist) < 30:
        return PriceStatResult(ann_vol=None, beta=None, dd95_1y=None, mcap=None)

    close = hist["Close"].tail(TRADING_DAYS_PER_YEAR + 1)
    returns = _daily_log_returns(close)
    ann_vol = float(returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)) if len(returns) > 2 else None

    beta = None
    try:
        bench_hist = yf.Ticker(benchmark).history(period="2y", auto_adjust=True)
        bench_close = bench_hist["Close"].tail(TRADING_DAYS_PER_YEAR + 1)
        bench_returns = _daily_log_returns(bench_close)
        aligned = pd.concat([returns, bench_returns], axis=1, join="inner").dropna()
        if len(aligned) > 10:
            stock_r, bench_r = aligned.iloc[:, 0], aligned.iloc[:, 1]
            variance = bench_r.var()
            if variance > 0:
                beta = float(stock_r.cov(bench_r) / variance)
    except Exception:
        beta = None

    drawdowns = _max_rolling_drawdowns(close)
    # 95th percentile of *severity*: the 5th percentile of (mostly
    # negative-or-zero) drawdown values is the deepest 5% of observed
    # drawdowns over the window.
    dd95_1y = float(abs(np.percentile(drawdowns, 5))) if len(drawdowns) > 10 else None

    mcap = None
    try:
        info = yf.Ticker(ticker).fast_info
        # FastInfo's dict-like .get() only recognizes its actual camelCase
        # keys (e.g. "marketCap") - a snake_case lookup silently returns
        # None instead of raising, which is easy to miss.
        raw_mcap = info.get("marketCap")
        mcap = float(raw_mcap) if raw_mcap else None
    except Exception:
        mcap = None

    return PriceStatResult(ann_vol=ann_vol, beta=beta, dd95_1y=dd95_1y, mcap=mcap)
