# ============================================================
#  config.py — Binance Scalping Bot Configuration
# ============================================================
import os
from dotenv import load_dotenv

load_dotenv()

# ── API CREDENTIALS ─────────────────────────────────────────
# Testnet keys (get from https://testnet.binance.vision)
TESTNET_API_KEY    = os.getenv("TESTNET_API_KEY", "YOUR_TESTNET_API_KEY")
TESTNET_API_SECRET = os.getenv("TESTNET_API_SECRET", "YOUR_TESTNET_API_SECRET")

# Live keys (get from https://www.binance.com/en/my/settings/api-management)
LIVE_API_KEY    = os.getenv("LIVE_API_KEY", "YOUR_LIVE_API_KEY")
LIVE_API_SECRET = os.getenv("LIVE_API_SECRET", "YOUR_LIVE_API_SECRET")

# ── ENVIRONMENT ──────────────────────────────────────────────
# Set to False to switch to LIVE trading (DO NOT until fully tested)
USE_TESTNET = True

# ── TRADING PARAMETERS ───────────────────────────────────────
SYMBOL          = "BTCUSDT"       # Trading pair
INTERVAL        = "5m"            # Candle interval (5m optimal for scalping per research)
TRADE_QUANTITY  = 0.001           # BTC per trade (adjust to your budget)

# ── RISK MANAGEMENT ──────────────────────────────────────────
RISK_PER_TRADE      = 0.05    # Max 5% of capital per trade
STOP_LOSS_PCT       = 0.004   # 0.4% stop-loss (optimized for 10x leverage)
TAKE_PROFIT_PCT     = 0.008   # 0.8% take-profit (2:1 RR ratio)
TRAILING_STOP_PCT   = 0.003   # 0.3% trailing stop
MAX_OPEN_TRADES     = 3       # Maximum concurrent positions
MAX_DAILY_LOSS_PCT  = 0.05    # Stop trading if daily loss > 5%
MAX_DAILY_TRADES    = 25      # Circuit breaker: reduced for 5m timeframe

# ── STRATEGY WEIGHTS (must sum to 1.0) ───────────────────────
STRATEGY_WEIGHTS = {
    "rsi_ema":      0.35,    # Increased - more reliable on 5m
    "bollinger":    0.30,    # Increased - mean reversion works better
    "orderbook":    0.15,    # Reduced - less relevant on 5m
    "ml_signal":    0.20,
}
SIGNAL_THRESHOLD = 0.05   # Very low threshold for catching trades quickly

# ── RSI + EMA STRATEGY ───────────────────────────────────────
RSI_PERIOD       = 7     # Faster RSI for 5m timeframe (research-backed)
RSI_OVERSOLD     = 30    # Standard oversold level
RSI_OVERBOUGHT   = 70    # Standard overbought level
EMA_FAST         = 9
EMA_SLOW         = 21
EMA_TREND        = 50   # Trend filter

# ── BOLLINGER BANDS STRATEGY ─────────────────────────────────
BB_PERIOD     = 9      # Shorter period for 5m scalping (research-backed)
BB_STD_DEV    = 2.0
BB_SQUEEZE_THRESHOLD = 0.015   # Tighter squeeze threshold for 5m

# ── ORDER BOOK STRATEGY ──────────────────────────────────────
ORDERBOOK_DEPTH         = 20   # Levels to fetch
ORDERBOOK_IMBALANCE_MIN = 1.5  # Buy/sell ratio to consider bullish
ORDERBOOK_IMBALANCE_MAX = 0.67 # Below this = bearish

# ── ML MODEL ─────────────────────────────────────────────────
ML_LOOKBACK_CANDLES  = 100   # Candles used to train
ML_RETRAIN_INTERVAL  = 50    # Retrain every N trades
ML_MODEL_PATH        = "models/scalper_model.joblib"
ML_SCALER_PATH       = "models/scalper_scaler.joblib"
ML_CONFIDENCE_MIN    = 0.55  # Min model confidence to use signal

# ── LOGGING ──────────────────────────────────────────────────
LOG_FILE          = "logs/trades.csv"
LOG_LEVEL         = "INFO"    # DEBUG | INFO | WARNING | ERROR
PRINT_CANDLES     = False     # Print every candle update
DASHBOARD_REFRESH = 1         # Dashboard refresh rate (seconds)

# ── FUTURES TRADING ──────────────────────────────────────────
USE_FUTURES = True                    # Toggle between spot/futures
FUTURES_LEVERAGE = 10                 # 1-125x leverage
MARGIN_TYPE = "ISOLATED"              # ISOLATED or CROSS
POSITION_MODE = "HEDGE"               # Allows simultaneous LONG+SHORT

# Safety parameters for liquidation
LIQUIDATION_BUFFER_PCT = 0.06         # Stay 6% away from liquidation (safe for 10x)
MIN_MARGIN_RATIO = 0.30               # Close if margin ratio < 30%
MAX_FUNDING_RATE_PCT = 0.05           # Close if funding too expensive (0.05% per 8h)

# ── WEB DASHBOARD ────────────────────────────────────────────
ENABLE_WEB_DASHBOARD = True           # Toggle web interface
WEB_HOST = "127.0.0.1"                # Only localhost by default (security)
WEB_PORT = 5000                       # Dashboard port
WEB_DEBUG = False                     # Flask debug mode (dev only)
