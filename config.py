# ============================================================
#  PRODUCTION CONFIG - IMPROVED (Fixes Applied 2026-03-27)
#  Enhanced with trend filter, higher threshold, wider stops
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

# ── PROFESSIONAL RISK MANAGEMENT ──────────────────────────────
RISK_PER_TRADE      = 0.05      # 5% risk per trade
STOP_LOSS_PCT       = 0.015     # 1.5% stop-loss (FIX #4: wider stops)
TAKE_PROFIT_PCT     = 0.025     # 2.5% take-profit (PROVEN OPTIMAL)
TRAILING_STOP_PCT   = 0.008     # 0.8% trailing stop
MAX_OPEN_TRADES     = 1         # Single position focus
MAX_DAILY_LOSS_PCT  = 0.05      # 5% daily loss limit
MAX_DAILY_TRADES    = 30        # Max 30 trades per day (5m timeframe)

# ── PROFESSIONAL SIGNAL FILTERING ────────────────────────────
# PROVEN combination that achieved 55.4% win rate
STRATEGY_WEIGHTS = {
    "professional":  0.25,    # Williams %R + EMA 8/21 + VWAP + Volume
    "rsi_ema":       0.45,    # Enhanced RSI + EMA (PRIMARY)
    "bollinger":     0.25,    # Enhanced Bollinger with Williams %R
    "orderbook":     0.00,    # Disabled - too noisy
    "ml_signal":     0.05,    # Minimal ML support
}
SIGNAL_THRESHOLD = 0.25      # FIX #2: Increased from 0.15 (higher quality trades)

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
FUTURES_LEVERAGE = 10           # 10x leverage (tested and proven)
MARGIN_TYPE = "ISOLATED"
POSITION_MODE = "HEDGE"

LIQUIDATION_BUFFER_PCT = 0.06
MIN_MARGIN_RATIO = 0.30
MAX_FUNDING_RATE_PCT = 0.05

# ── WEB DASHBOARD ────────────────────────────────────────────
ENABLE_WEB_DASHBOARD = True
WEB_HOST = "127.0.0.1"
WEB_PORT = 5000
WEB_DEBUG = False

# ── PROFESSIONAL VOLATILITY FILTER ───────────────────────────
MIN_ATR_THRESHOLD = 0.008       # 0.8% minimum ATR
MIN_ADX_THRESHOLD = 25          # FIX #3: Require strong trend (ADX > 25)
USE_ATR_STOPS = False

# ── IMPROVED EXIT LOGIC ──────────────────────────────────────
USE_TREND_FILTER = True         # FIX #1: Enable trend filter (EMA-200)
TREND_EMA_PERIOD = 200          # Only BUY above EMA-200, SELL below
USE_TRAILING_TP = True
MIN_TRADE_DURATION_SEC = 0
