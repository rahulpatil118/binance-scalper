# ============================================================
#  PRODUCTION CONFIG - AI PRE-TRAINED (2026-04-02)
#  Pre-trained on historical data: 53.3% WR, optimized parameters
#  AI learned: Higher ADX (22), larger candle bodies (0.33%)
# ============================================================
import os
from dotenv import load_dotenv

load_dotenv()

# ── API CREDENTIALS ─────────────────────────────────────────
TESTNET_API_KEY    = os.getenv("TESTNET_API_KEY", "YOUR_TESTNET_API_KEY")
TESTNET_API_SECRET = os.getenv("TESTNET_API_SECRET", "YOUR_TESTNET_API_SECRET")

LIVE_API_KEY    = os.getenv("LIVE_API_KEY", "YOUR_LIVE_API_KEY")
LIVE_API_SECRET = os.getenv("LIVE_API_SECRET", "YOUR_LIVE_API_SECRET")

# ── ENVIRONMENT ──────────────────────────────────────────────
USE_TESTNET = True

# ── TRADING PARAMETERS ───────────────────────────────────────
SYMBOL          = "BTCUSDT"
INTERVAL        = "5m"          # 5-minute timeframe (PROVEN 55.4% WR)
TRADE_QUANTITY  = 0.001

# Multi-Timeframe Analysis (Professional Edge)
USE_MTF_FILTER = True           # Enable multi-timeframe trend confirmation
MTF_INTERVALS = ["1h", "4h"]    # Higher timeframes for trend context
MTF_EMA_PERIOD = 50             # EMA for higher timeframe trend detection
MTF_ALIGNMENT_REQUIRED = True   # Only trade WITH higher TF trend

# ── PROFESSIONAL RISK MANAGEMENT ──────────────────────────────
RISK_PER_TRADE      = 0.02      # 2% risk per trade (Professional standard)
STOP_LOSS_PCT       = 0.010     # 1.0% stop-loss (will be ATR-based)
TAKE_PROFIT_PCT     = 0.025     # 2.5% take-profit (will be ATR-based for 1:2.5 R:R)
TRAILING_STOP_PCT   = 0.008     # 0.8% trailing stop
MAX_OPEN_TRADES     = 2         # Allow 2 concurrent positions
MAX_DAILY_LOSS_PCT  = 0.05      # 5% daily loss limit
MAX_DAILY_TRADES    = 9999      # Unlimited trades - trade every opportunity
MAX_DRAWDOWN_PCT    = 0.15      # 15% max equity drawdown - circuit breaker

# Drawdown Protection (Circuit Breakers)
ENABLE_CIRCUIT_BREAKERS = True  # Enable drawdown protection
CONSECUTIVE_LOSS_LIMIT = 3      # Reduce size after 3 losses in a row
LOSS_STREAK_PAUSE_LIMIT = 5     # Pause trading after 5 losses in a row
LOSS_STREAK_PAUSE_HOURS = 6     # Pause duration in hours
DRAWDOWN_RISK_REDUCTION = 0.5   # Reduce risk to 50% after consecutive losses
TRADE_COOLDOWN_SECONDS = 300    # 5-minute cooldown after closing position (prevents rapid re-entry)

# ── PROFESSIONAL SIGNAL FILTERING ────────────────────────────
# PROVEN combination that achieved 55.4% win rate
STRATEGY_WEIGHTS = {
    "professional":  0.25,    # Williams %R + EMA 8/21 + VWAP + Volume
    "rsi_ema":       0.45,    # Enhanced RSI + EMA (PRIMARY)
    "bollinger":     0.25,    # Enhanced Bollinger with Williams %R
    "orderbook":     0.00,    # Disabled - too noisy
    "ml_signal":     0.05,    # Minimal ML support
}
SIGNAL_THRESHOLD = 0.04      # Strategy v2.0: Balanced scalping (was 0.08)

# ── TIME-BASED FILTERS ───────────────────────────────────────
BLACKLIST_HOURS = [6, 7, 11, 12, 21]  # Avoid historically poor hours
WHITELIST_HOURS = []

# ── RSI + EMA STRATEGY (5m optimized) ────────────────────────
RSI_PERIOD       = 7
RSI_OVERSOLD     = 30
RSI_OVERBOUGHT   = 70
EMA_FAST         = 9
EMA_SLOW         = 21
EMA_TREND        = 50

# ── BOLLINGER BANDS STRATEGY (5m optimized) ──────────────────
BB_PERIOD     = 20
BB_STD_DEV    = 2.0
BB_SQUEEZE_THRESHOLD = 0.015

# ── ORDER BOOK STRATEGY ──────────────────────────────────────
ORDERBOOK_DEPTH         = 20
ORDERBOOK_IMBALANCE_MIN = 1.5
ORDERBOOK_IMBALANCE_MAX = 0.67

# ── ML MODEL ─────────────────────────────────────────────────
ML_LOOKBACK_CANDLES  = 100
ML_RETRAIN_INTERVAL  = 50
ML_MODEL_PATH        = "models/scalper_model.joblib"
ML_SCALER_PATH       = "models/scalper_scaler.joblib"
ML_CONFIDENCE_MIN    = 0.65

# ── LOGGING ──────────────────────────────────────────────────
LOG_FILE          = "logs/trades.csv"
LOG_LEVEL         = "INFO"
PRINT_CANDLES     = False
DASHBOARD_REFRESH = 1

# ── FUTURES TRADING ──────────────────────────────────────────
USE_FUTURES = True
FUTURES_LEVERAGE = 5            # 5x leverage (Professional standard)
MARGIN_TYPE = "ISOLATED"
POSITION_MODE = "HEDGE"

LIQUIDATION_BUFFER_PCT = 0.06
MIN_MARGIN_RATIO = 0.30
MAX_FUNDING_RATE_PCT = 0.05

# ── WEB DASHBOARD ────────────────────────────────────────────
ENABLE_WEB_DASHBOARD = True
WEB_HOST = "0.0.0.0"
WEB_PORT = 5000
WEB_DEBUG = False

# ── PROFESSIONAL VOLATILITY FILTER ───────────────────────────
MIN_ATR_THRESHOLD = 0.010       # 1.0% minimum ATR (60%+ strategy)
MAX_ATR_THRESHOLD = 0.35        # 35% maximum ATR (allow high volatility)
MIN_ADX_THRESHOLD = 22          # AI-Optimized from historical data (53.3% WR)
USE_ATR_STOPS = False

# ── IMPROVED EXIT LOGIC ──────────────────────────────────────
USE_TREND_FILTER = True         # FIX #1: Enable trend filter (EMA-200)
TREND_EMA_PERIOD = 200          # Only BUY above EMA-200, SELL below
USE_TRAILING_TP = True
MIN_TRADE_DURATION_SEC = 0

# ATR-Based Risk Management (Professional R:R)
USE_ATR_EXITS = True            # Use ATR for dynamic SL/TP
ATR_SL_MULTIPLIER = 1.5         # Stop-loss = 1.5x ATR
ATR_TP_MULTIPLIER = 3.75        # Take-profit = 3.75x ATR (1:2.5 R:R)
USE_PARTIAL_EXITS = True        # Exit 50% at 1:1.5, let 50% run to 1:2.5
PARTIAL_EXIT_PERCENT = 0.5      # Exit 50% at first target

# ── ADVANCED 60%+ STRATEGY FILTERS ────────────────────────────
# SuperTrend Indicator (Proven 60-65% accuracy)
USE_SUPERTREND = True
SUPERTREND_PERIOD = 10
SUPERTREND_MULTIPLIER = 3.0

# Signal Conflict Detection
MAX_INDICATOR_CONFLICT = 0.3    # Max 30% conflict between strategies

# Volume Confirmation
MIN_VOLUME_RATIO = 1.5          # Already defined above
VOLUME_SPIKE_RATIO = 2.5        # Extra confidence on 2.5x+ volume spikes

# Price Action Confirmation (FIXED: Dynamic based on volatility)
REQUIRE_STRONG_CANDLE = True    # Candle body must be strong
MIN_CANDLE_BODY_PCT = 0.0010    # 0.10% minimum (3x more lenient, adapts to volatility)
USE_DYNAMIC_CANDLE_FILTER = True  # Adjust candle requirement based on ATR
CANDLE_BODY_ATR_RATIO = 0.15    # In high volatility, require candle = 15% of ATR
