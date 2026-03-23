# ============================================================
#  web_server.py — Flask Web Dashboard API Server
# ============================================================
import os
import logging
import threading
from datetime import datetime
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

log = logging.getLogger("WebServer")

# Global references (set by start_web_server)
risk_manager = None
trade_logger = None
signal_aggregator = None
binance_client = None
bot_instance = None

app = Flask(__name__)
CORS(app)  # Enable CORS for development


# ── Routes ─────────────────────────────────────────────────

@app.route('/')
def index():
    """Serve main dashboard page."""
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    """
    GET /api/status
    Returns: Account summary, current price, bot state
    """
    try:
        from config import SYMBOL, USE_TESTNET, USE_FUTURES, FUTURES_LEVERAGE

        # Get current price
        ticker = binance_client.get_ticker(SYMBOL)
        current_price = float(ticker.get('price', 0))

        # Get account summary
        summary = risk_manager.summary()

        # Bot status
        bot_running = bot_instance.running if bot_instance else False

        return jsonify({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "symbol": SYMBOL,
            "price": current_price,
            "environment": "TESTNET" if USE_TESTNET else "LIVE",
            "mode": "FUTURES" if USE_FUTURES else "SPOT",
            "leverage": FUTURES_LEVERAGE if USE_FUTURES else 1,
            "bot_running": bot_running,
            "account": {
                "capital": summary["capital"],
                "total_pnl": summary["total_pnl"],
                "daily_pnl": summary["daily_pnl"],
                "daily_trades": summary["daily_trades"],
                "open_positions": summary.get("open", 0),
                "win_rate": summary["win_rate"],
                "wins": summary["wins"],
                "losses": summary["losses"],
                "paused": summary["paused"],
                "pause_reason": risk_manager.pause_reason if summary["paused"] else ""
            }
        })
    except Exception as e:
        log.error(f"Error in /api/status: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/signals')
def api_signals():
    """
    GET /api/signals
    Returns: Latest combined signal + individual strategy scores
    """
    try:
        from config import SIGNAL_THRESHOLD, STRATEGY_WEIGHTS

        # Get last signal from bot
        if not bot_instance or not bot_instance._last_signal:
            return jsonify({"error": "No signal data available"}), 503

        signal_data = bot_instance._last_signal
        combined = signal_data.get("combined", 0)

        # Determine direction
        if combined >= SIGNAL_THRESHOLD:
            direction = "BUY"
            confidence = "STRONG"
        elif combined <= -SIGNAL_THRESHOLD:
            direction = "SELL"
            confidence = "STRONG"
        else:
            direction = "HOLD"
            confidence = "WEAK"

        # Count consensus
        bull_count = sum(1 for v in signal_data.values() if isinstance(v, (int, float)) and v > 0)
        bear_count = sum(1 for v in signal_data.values() if isinstance(v, (int, float)) and v < 0)

        return jsonify({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "combined": combined,
            "direction": direction,
            "confidence": confidence,
            "strategies": {
                "rsi_ema": signal_data.get("rsi_ema", 0),
                "bollinger": signal_data.get("bollinger", 0),
                "orderbook": signal_data.get("orderbook", 0),
                "ml_signal": signal_data.get("ml_signal", 0)
            },
            "weights": STRATEGY_WEIGHTS,
            "consensus_bull": bull_count,
            "consensus_bear": bear_count,
            "threshold": SIGNAL_THRESHOLD
        })
    except Exception as e:
        log.error(f"Error in /api/signals: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/positions')
def api_positions():
    """
    GET /api/positions
    Returns: Active positions with live unrealized P&L
    """
    try:
        from config import SYMBOL

        # Get current price for P&L calculation
        ticker = binance_client.get_ticker(SYMBOL)
        current_price = float(ticker.get('price', 0))

        positions = []
        for order_id, pos in risk_manager.open_positions.items():
            positions.append({
                "order_id": order_id,
                "symbol": pos.symbol,
                "side": pos.side,
                "entry_price": pos.entry_price,
                "quantity": pos.quantity,
                "stop_loss": pos.stop_loss,
                "take_profit": pos.take_profit,
                "trailing_stop": pos.trailing_stop,
                "unrealised_pnl": pos.unrealised_pnl(current_price),
                "unrealised_pct": pos.unrealised_pct(current_price),
                "duration_sec": int(time.time() - pos.timestamp),
                "is_futures": pos.is_futures,
                "leverage": pos.leverage,
                "liquidation_price": pos.liquidation_price if pos.is_futures else None
            })

        return jsonify({
            "count": len(positions),
            "positions": positions
        })
    except Exception as e:
        log.error(f"Error in /api/positions: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/indicators')
def api_indicators():
    """
    GET /api/indicators
    Returns: Latest candle technical indicators
    """
    try:
        # Get latest dataframe from bot
        if not bot_instance or not hasattr(bot_instance, '_latest_df') or bot_instance._latest_df is None:
            return jsonify({"error": "No indicator data available"}), 503

        df = bot_instance._latest_df
        if df.empty:
            return jsonify({"error": "Empty dataframe"}), 503

        latest = df.iloc[-1]

        return jsonify({
            "timestamp": latest.name.isoformat() if hasattr(latest.name, 'isoformat') else str(latest.name),
            "price": float(latest["close"]),
            "indicators": {
                "rsi": float(latest.get("rsi", 0)),
                "ema_fast": float(latest.get("ema_fast", 0)),
                "ema_slow": float(latest.get("ema_slow", 0)),
                "ema_trend": float(latest.get("ema_trend", 0)),
                "macd": float(latest.get("macd", 0)),
                "macd_signal": float(latest.get("macd_signal", 0)),
                "macd_hist": float(latest.get("macd_hist", 0)),
                "bb_upper": float(latest.get("bb_upper", 0)),
                "bb_mid": float(latest.get("bb_mid", 0)),
                "bb_lower": float(latest.get("bb_lower", 0)),
                "bb_pct": float(latest.get("bb_pct", 0)),
                "bb_bandwidth": float(latest.get("bb_bandwidth", 0)),
                "bb_squeeze": bool(latest.get("bb_squeeze", False)),
                "atr": float(latest.get("atr", 0)),
                "atr_pct": float(latest.get("atr_pct", 0)),
                "adx": float(latest.get("adx", 0)),
                "plus_di": float(latest.get("plus_di", 0)),
                "minus_di": float(latest.get("minus_di", 0)),
                "vwap": float(latest.get("vwap", 0)),
                "stoch_k": float(latest.get("stoch_k", 0)),
                "stoch_d": float(latest.get("stoch_d", 0)),
                "vol_ratio": float(latest.get("vol_ratio", 0)),
                "candle_body": float(latest.get("candle_body", 0)),
                "is_bullish": bool(latest.get("is_bullish", False))
            }
        })
    except Exception as e:
        log.error(f"Error in /api/indicators: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/trades')
def api_trades():
    """
    GET /api/trades?limit=50&offset=0
    Returns: Historical trade log with pagination
    """
    try:
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))

        # Load trade history from CSV (returns list of dicts)
        history = trade_logger.load_history()

        if not history:
            return jsonify({
                "total": 0,
                "limit": limit,
                "offset": offset,
                "trades": []
            })

        # Sort by timestamp descending (newest first)
        history = sorted(history, key=lambda x: x.get('timestamp', ''), reverse=True)

        total = len(history)
        paginated = history[offset:offset+limit]

        trades = []
        for row in paginated:
            trades.append({
                "timestamp": row.get('timestamp', ''),
                "symbol": row.get('symbol', ''),
                "side": row.get('side', ''),
                "entry_price": float(row.get('entry_price', 0)),
                "exit_price": float(row.get('exit_price', 0)),
                "quantity": float(row.get('quantity', 0)),
                "pnl": float(row.get('pnl', 0)),
                "pnl_pct": float(row.get('pnl_pct', 0)),
                "reason": row.get('reason', ''),
                "duration_sec": int(float(row.get('duration_sec', 0))),
                "scores": {
                    "rsi_ema": float(row.get('rsi_ema_score', 0)),
                    "bollinger": float(row.get('bollinger_score', 0)),
                    "orderbook": float(row.get('orderbook_score', 0)),
                    "ml_signal": float(row.get('ml_score', 0)),
                    "combined": float(row.get('combined_score', 0))
                }
            })

        return jsonify({
            "total": total,
            "limit": limit,
            "offset": offset,
            "trades": trades
        })
    except Exception as e:
        log.error(f"Error in /api/trades: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/performance')
def api_performance():
    """
    GET /api/performance
    Returns: Aggregated performance metrics + chart data
    """
    try:
        # Get performance summary
        perf = trade_logger.performance_summary()

        # Load trade history for charts (returns list of dicts)
        history = trade_logger.load_history()

        # Equity curve data
        equity_curve = []
        if history:
            # Sort by timestamp
            sorted_history = sorted(history, key=lambda x: x.get('timestamp', ''))
            running_capital = risk_manager.capital - risk_manager.total_pnl

            for row in sorted_history:
                running_capital += float(row.get('pnl', 0))
                equity_curve.append({
                    "timestamp": row.get('timestamp', ''),
                    "capital": running_capital
                })

        # P&L distribution (simple histogram)
        pnl_distribution = {"bins": [], "counts": []}
        if history:
            import numpy as np
            pnls = [float(row.get('pnl', 0)) for row in history if row.get('pnl')]
            if len(pnls) > 0:
                bins = [-20, -15, -10, -5, 0, 5, 10, 15, 20, 25]
                counts, _ = np.histogram(pnls, bins=bins)
                pnl_distribution = {
                    "bins": bins,
                    "counts": counts.tolist()
                }

        # Win rate by hour (if we have timestamp data)
        win_rate_by_hour = []
        if history:
            from datetime import datetime
            hour_stats = {}
            for row in history:
                try:
                    timestamp = row.get('timestamp', '')
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    hour = dt.hour
                    pnl = float(row.get('pnl', 0))

                    if hour not in hour_stats:
                        hour_stats[hour] = {"wins": 0, "total": 0}

                    hour_stats[hour]["total"] += 1
                    if pnl > 0:
                        hour_stats[hour]["wins"] += 1
                except:
                    pass

            for hour in range(24):
                if hour in hour_stats:
                    stats = hour_stats[hour]
                    win_rate = (stats["wins"] / stats["total"]) * 100 if stats["total"] > 0 else 0
                else:
                    win_rate = 0
                win_rate_by_hour.append({
                    "hour": hour,
                    "win_rate": win_rate
                })

        return jsonify({
            "summary": perf,
            "chart_data": {
                "equity_curve": equity_curve,
                "pnl_distribution": pnl_distribution,
                "win_rate_by_hour": win_rate_by_hour
            }
        })
    except Exception as e:
        log.error(f"Error in /api/performance: {e}")
        return jsonify({"error": str(e)}), 500


# ── Server startup ─────────────────────────────────────────

def start_web_server(risk_manager_inst, trade_logger_inst, signal_aggregator_inst,
                     binance_client_inst, bot_inst):
    """
    Start Flask web server in a background thread.

    Args:
        risk_manager_inst: RiskManager instance from bot
        trade_logger_inst: TradeLogger instance from bot
        signal_aggregator_inst: SignalAggregator instance from bot
        binance_client_inst: BinanceClient instance from bot
        bot_inst: ScalpingBot instance for accessing _last_signal and _latest_df

    Returns:
        threading.Thread: The Flask server thread
    """
    global risk_manager, trade_logger, signal_aggregator, binance_client, bot_instance

    risk_manager = risk_manager_inst
    trade_logger = trade_logger_inst
    signal_aggregator = signal_aggregator_inst
    binance_client = binance_client_inst
    bot_instance = bot_inst

    # Load config
    from config import WEB_HOST, WEB_PORT, WEB_DEBUG

    def run_flask():
        log.info(f"🌐 Web dashboard starting at http://{WEB_HOST}:{WEB_PORT}")
        app.run(host=WEB_HOST, port=WEB_PORT, debug=WEB_DEBUG, use_reloader=False)

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    return flask_thread


# Needed for time import in positions endpoint
import time
