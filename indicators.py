# ============================================================
#  indicators.py — Technical Indicators Engine
# ============================================================
import numpy as np
import pandas as pd
from config import (RSI_PERIOD, EMA_FAST, EMA_SLOW, EMA_TREND,
                    BB_PERIOD, BB_STD_DEV, BB_SQUEEZE_THRESHOLD)


def compute_rsi(series: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def compute_macd(series: pd.Series,
                 fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast   = compute_ema(series, fast)
    ema_slow   = compute_ema(series, slow)
    macd_line  = ema_fast - ema_slow
    signal_line = compute_ema(macd_line, signal)
    histogram   = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_bollinger_bands(series: pd.Series,
                             period: int = BB_PERIOD,
                             std_dev: float = BB_STD_DEV):
    sma   = series.rolling(window=period).mean()
    std   = series.rolling(window=period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    bandwidth = (upper - lower) / sma
    pct_b     = (series - lower) / (upper - lower + 1e-10)
    return upper, sma, lower, bandwidth, pct_b


def compute_atr(high: pd.Series, low: pd.Series,
                close: pd.Series, period: int = 14) -> pd.Series:
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean()


def compute_vwap(df: pd.DataFrame) -> pd.Series:
    """Volume-Weighted Average Price (resets each session)."""
    typical = (df["high"] + df["low"] + df["close"]) / 3
    cum_vol  = df["volume"].cumsum()
    cum_tvol = (typical * df["volume"]).cumsum()
    return cum_tvol / cum_vol.replace(0, np.nan)


def compute_stochastic(high: pd.Series, low: pd.Series,
                        close: pd.Series, k: int = 14, d: int = 3):
    lowest  = low.rolling(k).min()
    highest = high.rolling(k).max()
    stoch_k = 100 * (close - lowest) / (highest - lowest + 1e-10)
    stoch_d = stoch_k.rolling(d).mean()
    return stoch_k, stoch_d


def compute_volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """Current volume vs rolling average — spike detection."""
    return volume / volume.rolling(period).mean().replace(0, np.nan)


def compute_williams_r(high: pd.Series, low: pd.Series,
                       close: pd.Series, period: int = 10) -> pd.Series:
    """
    Williams %R - Momentum oscillator (professional scalping indicator)
    Returns values from 0 to -100
    -20 to 0 = Overbought (sell signal)
    -80 to -100 = Oversold (buy signal)
    Period 10 is optimal for scalping (more sensitive than default 14)
    """
    highest = high.rolling(period).max()
    lowest = low.rolling(period).min()
    williams = -100 * (highest - close) / (highest - lowest + 1e-10)
    return williams.fillna(-50)


def compute_adx(high: pd.Series, low: pd.Series,
                close: pd.Series, period: int = 14) -> tuple:
    """
    Average Directional Index (ADX) - measures trend strength.
    Returns: (adx, plus_di, minus_di)
    ADX > 25 = strong trend, ADX < 20 = weak/choppy market
    """
    # Calculate True Range
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)

    # Directional movement
    plus_dm = high.diff()
    minus_dm = -low.diff()

    # Set to 0 if not directional
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    plus_dm[(plus_dm < minus_dm)] = 0
    minus_dm[(minus_dm < plus_dm)] = 0

    # Smooth with Wilder's method
    atr_smooth = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_dm_smooth = plus_dm.ewm(alpha=1/period, adjust=False).mean()
    minus_dm_smooth = minus_dm.ewm(alpha=1/period, adjust=False).mean()

    # Calculate DI
    plus_di = 100 * plus_dm_smooth / atr_smooth.replace(0, np.nan)
    minus_di = 100 * minus_dm_smooth / atr_smooth.replace(0, np.nan)

    # Calculate ADX
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()

    return adx.fillna(0), plus_di.fillna(0), minus_di.fillna(0)


def enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Add all indicators to OHLCV dataframe."""
    df = df.copy()
    c = df["close"]
    h = df["high"]
    lo = df["low"]
    v = df["volume"]

    # RSI
    df["rsi"] = compute_rsi(c)

    # EMAs (original + professional scalping 8/21)
    df["ema_fast"]  = compute_ema(c, EMA_FAST)
    df["ema_slow"]  = compute_ema(c, EMA_SLOW)
    df["ema_trend"] = compute_ema(c, EMA_TREND)
    df["ema_8"]  = compute_ema(c, 8)   # Professional scalping
    df["ema_21"] = compute_ema(c, 21)  # Professional scalping

    # MACD
    df["macd"], df["macd_signal"], df["macd_hist"] = compute_macd(c)

    # Bollinger Bands
    df["bb_upper"], df["bb_mid"], df["bb_lower"], \
        df["bb_bandwidth"], df["bb_pct"] = compute_bollinger_bands(c)

    # ATR (volatility measure)
    df["atr"] = compute_atr(h, lo, c)
    df["atr_pct"] = df["atr"] / c * 100

    # VWAP
    df["vwap"] = compute_vwap(df)

    # Stochastic
    df["stoch_k"], df["stoch_d"] = compute_stochastic(h, lo, c)

    # Williams %R (professional scalping momentum)
    df["williams_r"] = compute_williams_r(h, lo, c, period=10)

    # Volume
    df["vol_ratio"] = compute_volume_ratio(v)

    # ADX (trend strength)
    df["adx"], df["plus_di"], df["minus_di"] = compute_adx(h, lo, c)

    # Candle features
    df["candle_body"]  = (c - df["open"]).abs() / c * 100
    df["candle_upper"] = (h - df[["open","close"]].max(axis=1)) / c * 100
    df["candle_lower"] = (df[["open","close"]].min(axis=1) - lo) / c * 100
    df["is_bullish"]   = (c > df["open"]).astype(int)

    # Squeeze (BB contraction)
    df["bb_squeeze"] = df["bb_bandwidth"] < BB_SQUEEZE_THRESHOLD

    return df.dropna()
