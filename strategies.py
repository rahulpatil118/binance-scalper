# ============================================================
#  strategies.py — Four Scalping Strategies
#  Each returns a score in [-1.0 … +1.0]
#  -1.0 = strong SELL  |  0 = neutral  |  +1.0 = strong BUY
# ============================================================
import numpy as np
import pandas as pd
from config import (RSI_OVERSOLD, RSI_OVERBOUGHT,
                    BB_SQUEEZE_THRESHOLD,
                    ORDERBOOK_IMBALANCE_MIN, ORDERBOOK_IMBALANCE_MAX,
                    ML_CONFIDENCE_MIN)


# ── 1. RSI + EMA CROSSOVER STRATEGY ─────────────────────────
class RSIEMAStrategy:
    """
    Rules:
    • BUY  when RSI < oversold + EMA fast crosses above EMA slow
              + price > EMA trend (uptrend filter)
    • SELL when RSI > overbought + EMA fast crosses below EMA slow
              + price < EMA trend (downtrend filter)
    Adds MACD confirmation and stochastic for higher quality signals.
    """

    name = "RSI_EMA"

    def score(self, df: pd.DataFrame) -> float:
        if len(df) < 3:
            return 0.0

        row  = df.iloc[-1]
        prev = df.iloc[-2]

        score = 0.0

        # ── RSI component (±0.35) ────────────────────────────
        rsi = row["rsi"]
        if rsi < RSI_OVERSOLD:
            score += 0.35 * (1 - rsi / RSI_OVERSOLD)   # deeper = stronger
        elif rsi > RSI_OVERBOUGHT:
            score -= 0.35 * ((rsi - RSI_OVERBOUGHT) / (100 - RSI_OVERBOUGHT))

        # ── EMA crossover (±0.25) ────────────────────────────
        ema_cross_now  = row["ema_fast"]  - row["ema_slow"]
        ema_cross_prev = prev["ema_fast"] - prev["ema_slow"]
        if ema_cross_now > 0 and ema_cross_prev <= 0:   # golden cross
            score += 0.25
        elif ema_cross_now < 0 and ema_cross_prev >= 0: # death cross
            score -= 0.25
        else:
            # Trend bias without fresh cross
            score += 0.10 if ema_cross_now > 0 else -0.10

        # ── Trend filter: price vs EMA trend (±0.15) ─────────
        if row["close"] > row["ema_trend"]:
            score += 0.15
        else:
            score -= 0.15

        # ── MACD confirmation (±0.15) ─────────────────────────
        if row["macd_hist"] > 0 and prev["macd_hist"] <= 0:
            score += 0.15
        elif row["macd_hist"] < 0 and prev["macd_hist"] >= 0:
            score -= 0.15
        elif row["macd_hist"] > 0:
            score += 0.07
        else:
            score -= 0.07

        # ── Stochastic (±0.10) ────────────────────────────────
        sk = row["stoch_k"]
        if sk < 20:
            score += 0.10
        elif sk > 80:
            score -= 0.10

        return float(np.clip(score, -1.0, 1.0))


# ── 2. BOLLINGER BANDS BREAKOUT STRATEGY ────────────────────
class BollingerStrategy:
    """
    Rules:
    • Mean reversion: price touches lower band → BUY (bounce expected)
    • Breakout: price closes above upper band on squeeze release → BUY
    • Reverse logic for SELL
    • BB width filter avoids low-volatility false signals
    """

    name = "Bollinger"

    def score(self, df: pd.DataFrame) -> float:
        if len(df) < 3:
            return 0.0

        row  = df.iloc[-1]
        prev = df.iloc[-2]

        score = 0.0
        pct_b = row["bb_pct"]   # 0 = at lower band, 1 = at upper band

        # ── Mean-reversion component (±0.40) ─────────────────
        if pct_b < 0.05:          # touching / outside lower band
            score += 0.40 * (1 - pct_b)
        elif pct_b > 0.95:        # touching / outside upper band
            score -= 0.40 * pct_b

        # ── Squeeze breakout (±0.25) ──────────────────────────
        was_squeeze = prev["bb_squeeze"]
        now_squeeze = row["bb_squeeze"]
        if was_squeeze and not now_squeeze:   # squeeze just released
            direction = 1 if row["close"] > row["bb_mid"] else -1
            score += direction * 0.25

        # ── Band position trend (±0.20) ───────────────────────
        if 0.45 < pct_b < 0.55:  # price riding middle band
            # direction determined by candle colour
            score += 0.10 if row["is_bullish"] else -0.10
        elif pct_b < 0.35:
            score += 0.20   # below midpoint — upward bias
        elif pct_b > 0.65:
            score -= 0.20   # above midpoint — downward bias

        # ── Volume confirmation (±0.15) ───────────────────────
        if row["vol_ratio"] > 1.5:   # volume spike on the move
            score += 0.15 if score > 0 else -0.15

        return float(np.clip(score, -1.0, 1.0))


# ── 3. ORDER BOOK IMBALANCE STRATEGY ────────────────────────
class OrderBookStrategy:
    """
    Analyses live order-book depth:
    • Bid/Ask ratio > threshold → buy pressure → BUY
    • Bid/Ask ratio < inverse  → sell pressure → SELL
    • Large wall detection adjusts score
    """

    name = "OrderBook"

    def score(self, order_book: dict) -> float:
        """
        order_book = {"bids": [[price, qty], ...],
                      "asks": [[price, qty], ...]}
        """
        if not order_book or "bids" not in order_book:
            return 0.0

        bids = np.array(order_book["bids"], dtype=float)
        asks = np.array(order_book["asks"], dtype=float)

        if len(bids) == 0 or len(asks) == 0:
            return 0.0

        total_bid = bids[:, 1].sum()
        total_ask = asks[:, 1].sum()

        if total_ask == 0:
            return 0.5

        ratio = total_bid / total_ask   # >1 = more bids = bullish

        # ── Base imbalance score ──────────────────────────────
        if ratio >= ORDERBOOK_IMBALANCE_MIN:
            base = min((ratio - 1) / (ORDERBOOK_IMBALANCE_MIN - 1), 1.0) * 0.6
        elif ratio <= ORDERBOOK_IMBALANCE_MAX:
            base = -min((1 - ratio) / (1 - ORDERBOOK_IMBALANCE_MAX), 1.0) * 0.6
        else:
            base = (ratio - 1) * 0.3   # mild linear interpolation

        # ── Spread component (±0.20) ──────────────────────────
        best_bid = bids[0, 0]
        best_ask = asks[0, 0]
        spread_pct = (best_ask - best_bid) / best_ask

        # Tight spread = healthy liquidity, slight positive bias
        spread_score = -min(spread_pct * 100, 1.0) * 0.10

        # ── Large wall detection (±0.20) ──────────────────────
        max_bid_wall = bids[:5, 1].max()
        max_ask_wall = asks[:5, 1].max()
        wall_score   = 0.0
        if max_bid_wall > 2 * bids[:, 1].mean():
            wall_score += 0.20   # strong bid wall below = support
        if max_ask_wall > 2 * asks[:, 1].mean():
            wall_score -= 0.20   # strong ask wall above = resistance

        final = base + spread_score + wall_score
        return float(np.clip(final, -1.0, 1.0))


# ── 4. ML SIGNAL STRATEGY ────────────────────────────────────
class MLStrategy:
    """
    Trains a RandomForest on OHLCV + indicator features.
    • Labels: 1 = price went up >0.3% in next 3 candles, 0 = otherwise
    • Re-trains periodically on recent live data
    • Outputs probability → converted to [-1, +1] score
    """

    name = "ML"

    FEATURE_COLS = [
        "rsi", "ema_fast", "ema_slow", "macd", "macd_hist",
        "bb_pct", "bb_bandwidth", "atr_pct",
        "stoch_k", "stoch_d", "vol_ratio",
        "candle_body", "candle_upper", "candle_lower", "is_bullish",
        "vwap", "adx", "plus_di", "minus_di",  # Added ADX for trend strength
    ]

    def __init__(self):
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import StandardScaler
        self.model   = RandomForestClassifier(
            n_estimators=200, max_depth=6,
            min_samples_leaf=5, random_state=42, n_jobs=-1
        )
        self.scaler  = StandardScaler()
        self.trained = False

    def train(self, df: pd.DataFrame, forward_candles: int = 3,
              target_pct: float = 0.003):
        """Train model on historical data from enriched dataframe."""
        if len(df) < 60:
            return False

        df = df.copy()
        df["future_return"] = df["close"].shift(-forward_candles) / df["close"] - 1
        df["label"] = (df["future_return"] > target_pct).astype(int)
        df = df.dropna(subset=self.FEATURE_COLS + ["label"])

        if len(df) < 40:
            return False

        X = df[self.FEATURE_COLS].values
        y = df["label"].values

        # Ensure both classes present
        if len(np.unique(y)) < 2:
            return False

        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        self.trained = True
        return True

    def score(self, df: pd.DataFrame) -> float:
        if not self.trained or len(df) < 2:
            return 0.0

        row = df[self.FEATURE_COLS].iloc[[-1]]
        try:
            X_scaled = self.scaler.transform(row.values)
            proba    = self.model.predict_proba(X_scaled)[0]   # [p_down, p_up]
            confidence = max(proba)

            if confidence < ML_CONFIDENCE_MIN:
                return 0.0  # not confident enough

            # Convert [0..1] probability to [-1..+1] score
            return float(np.clip((proba[1] - proba[0]) * confidence * 2, -1.0, 1.0))
        except Exception:
            return 0.0

    def save(self, model_path: str, scaler_path: str):
        import joblib
        joblib.dump(self.model,  model_path)
        joblib.dump(self.scaler, scaler_path)

    def load(self, model_path: str, scaler_path: str):
        import joblib
        import os
        if os.path.exists(model_path) and os.path.exists(scaler_path):
            self.model   = joblib.load(model_path)
            self.scaler  = joblib.load(scaler_path)
            self.trained = True
            return True
        return False


# ── SIGNAL AGGREGATOR ────────────────────────────────────────
class SignalAggregator:
    """
    Combines all strategy scores using weighted average.
    Returns final score and per-strategy breakdown.
    """

    def __init__(self):
        self.rsi_ema    = RSIEMAStrategy()
        self.bollinger  = BollingerStrategy()
        self.orderbook  = OrderBookStrategy()
        self.ml         = MLStrategy()

    def compute(self, df: pd.DataFrame, order_book: dict,
                weights: dict) -> dict:
        scores = {
            "rsi_ema":   self.rsi_ema.score(df),
            "bollinger": self.bollinger.score(df),
            "orderbook": self.orderbook.score(order_book),
            "ml_signal": self.ml.score(df),
        }

        total_weight = sum(weights.values())
        combined = sum(scores[k] * weights.get(k, 0)
                       for k in scores) / total_weight

        # Consensus boost: if 3+ strategies agree, amplify signal
        bullish_count = sum(1 for v in scores.values() if v > 0.1)
        bearish_count = sum(1 for v in scores.values() if v < -0.1)

        if bullish_count >= 3:
            combined = min(combined * 1.15, 1.0)
        elif bearish_count >= 3:
            combined = max(combined * 1.15, -1.0)

        # ── VOLATILITY FILTER (research-backed) ──────────────────
        # Avoid trading in low volatility / choppy conditions
        if len(df) > 0:
            latest = df.iloc[-1]

            # Filter 1: ATR volatility check
            # If ATR % is too low, market is choppy/consolidating
            atr_pct = latest.get("atr_pct", 0)
            if atr_pct < 0.05:  # Less than 0.05% volatility
                combined *= 0.3  # Heavily dampen signal
            elif atr_pct < 0.10:  # Low volatility
                combined *= 0.6  # Moderately dampen signal

            # Filter 2: ADX trend strength check (research-backed)
            # ADX < 20 = weak/choppy trend, avoid trading
            # ADX > 25 = strong trend, good for scalping
            adx = latest.get("adx", 0)
            if adx < 20:  # Weak/choppy trend
                combined *= 0.2  # Heavily dampen signal
            elif adx < 25:  # Moderate trend
                combined *= 0.7  # Moderately dampen signal
            # If ADX >= 25, no dampening (strong trend)

            # Filter 3: Bollinger Bands squeeze (already computed)
            # During squeeze, avoid trading until breakout
            bb_bandwidth = latest.get("bb_bandwidth", 1)
            if bb_bandwidth < 0.01:  # Very tight squeeze
                combined *= 0.4  # Dampen signal

        return {
            "combined": round(combined, 4),
            "scores":   {k: round(v, 4) for k, v in scores.items()},
            "consensus_bull": bullish_count,
            "consensus_bear": bearish_count,
            "filters": {
                "atr_pct": round(df.iloc[-1].get("atr_pct", 0), 4) if len(df) > 0 else 0,
                "adx": round(df.iloc[-1].get("adx", 0), 2) if len(df) > 0 else 0,
                "bb_bandwidth": round(df.iloc[-1].get("bb_bandwidth", 0), 4) if len(df) > 0 else 0,
            }
        }
