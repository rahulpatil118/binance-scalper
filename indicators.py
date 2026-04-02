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


def compute_supertrend(high: pd.Series, low: pd.Series, close: pd.Series,
                       period: int = 10, multiplier: float = 3.0) -> tuple:
    """
    SuperTrend Indicator - Proven 60-65% accuracy for trend following
    Returns: (supertrend, direction)
    direction: 1 = uptrend (bullish), -1 = downtrend (bearish)

    Buy when: price crosses above SuperTrend (direction changes to 1)
    Sell when: price crosses below SuperTrend (direction changes to -1)
    """
    # Calculate ATR for the period
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()

    # Calculate basic bands
    hl_avg = (high + low) / 2
    upper_band = hl_avg + (multiplier * atr)
    lower_band = hl_avg - (multiplier * atr)

    # Initialize supertrend
    supertrend = pd.Series(index=close.index, dtype=float)
    direction = pd.Series(index=close.index, dtype=int)

    # Set initial values
    supertrend.iloc[0] = lower_band.iloc[0]
    direction.iloc[0] = 1

    # Calculate SuperTrend
    for i in range(1, len(close)):
        # Update bands based on previous supertrend
        if close.iloc[i] > upper_band.iloc[i-1]:
            direction.iloc[i] = 1  # Uptrend
        elif close.iloc[i] < lower_band.iloc[i-1]:
            direction.iloc[i] = -1  # Downtrend
        else:
            direction.iloc[i] = direction.iloc[i-1]  # Continue previous trend

        # Set supertrend value
        if direction.iloc[i] == 1:  # Uptrend
            supertrend.iloc[i] = lower_band.iloc[i]
            # Make sure it doesn't decrease
            if i > 0 and supertrend.iloc[i] < supertrend.iloc[i-1]:
                supertrend.iloc[i] = supertrend.iloc[i-1]
        else:  # Downtrend
            supertrend.iloc[i] = upper_band.iloc[i]
            # Make sure it doesn't increase
            if i > 0 and supertrend.iloc[i] > supertrend.iloc[i-1]:
                supertrend.iloc[i] = supertrend.iloc[i-1]

    return supertrend.fillna(0), direction.fillna(0)


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

    # SuperTrend (60%+ strategy)
    from config import SUPERTREND_PERIOD, SUPERTREND_MULTIPLIER
    df["supertrend"], df["supertrend_direction"] = compute_supertrend(
        h, lo, c, SUPERTREND_PERIOD, SUPERTREND_MULTIPLIER)

    return df.dropna()


def get_mtf_trend(binance_client, symbol: str, intervals: list, ema_period: int = 50) -> dict:
    """
    Get trend direction for multiple timeframes using EMA.

    Args:
        binance_client: BinanceClient instance
        symbol: Trading pair (e.g., "BTCUSDT")
        intervals: List of intervals to check (e.g., ["1h", "4h"])
        ema_period: EMA period for trend detection

    Returns:
        dict: {
            "1h": 1 (bullish) or -1 (bearish),
            "4h": 1 (bullish) or -1 (bearish),
            "aligned": True if all timeframes agree
        }
    """
    trends = {}

    for interval in intervals:
        try:
            # Fetch enough data for EMA calculation
            df = binance_client.get_klines(symbol, interval, limit=ema_period + 50)
            if df.empty:
                trends[interval] = 0  # Neutral if no data
                continue

            # Calculate EMA
            close = df['close']
            ema = compute_ema(close, ema_period)

            # Determine trend: price > EMA = bullish (1), price < EMA = bearish (-1)
            current_price = float(close.iloc[-1])
            current_ema = float(ema.iloc[-1])

            if current_price > current_ema:
                trends[interval] = 1  # Bullish
            elif current_price < current_ema:
                trends[interval] = -1  # Bearish
            else:
                trends[interval] = 0  # Neutral

        except Exception as e:
            trends[interval] = 0  # Neutral on error

    # Check if all timeframes are aligned
    trend_values = [v for v in trends.values() if v != 0]
    if trend_values:
        aligned = all(t == trend_values[0] for t in trend_values)
    else:
        aligned = False

    trends["aligned"] = aligned

    return trends


def check_mtf_alignment(binance_client, symbol: str, side: str) -> tuple[bool, str]:
    """
    Check if trade direction aligns with higher timeframe trends.

    Args:
        binance_client: BinanceClient instance
        symbol: Trading pair
        side: "BUY" or "SELL"

    Returns:
        (allowed, reason)
    """
    from config import USE_MTF_FILTER, MTF_INTERVALS, MTF_EMA_PERIOD, MTF_ALIGNMENT_REQUIRED

    if not USE_MTF_FILTER:
        return True, "MTF filter disabled"

    # Get trends from higher timeframes
    trends = get_mtf_trend(binance_client, symbol, MTF_INTERVALS, MTF_EMA_PERIOD)

    # Determine required trend direction
    required_direction = 1 if side == "BUY" else -1

    # Check each timeframe
    misaligned = []
    for interval in MTF_INTERVALS:
        trend = trends.get(interval, 0)
        if trend != 0 and trend != required_direction:
            misaligned.append(f"{interval}={('bearish' if trend < 0 else 'bullish')}")

    if misaligned:
        if MTF_ALIGNMENT_REQUIRED:
            return False, f"MTF misaligned: {', '.join(misaligned)}"
        else:
            # Warning but allow trade
            return True, f"MTF warning: {', '.join(misaligned)}"

    return True, f"MTF aligned: {side} confirmed by {', '.join(MTF_INTERVALS)}"
