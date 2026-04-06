# ============================================================
#  bot.py — Main Scalping Bot Engine
# ============================================================
import time
import logging
import signal
import sys
from datetime import datetime

from binance_client import BinanceClient
from indicators    import enrich_dataframe
from strategies_pro import SignalAggregatorPro as SignalAggregator
from risk_manager  import RiskManager
from trade_logger  import TradeLogger
from dashboard     import render_dashboard
from web_server    import start_web_server
from adaptive_learner import AdaptiveLearner  # Self-learning AI
from config        import (SYMBOL, INTERVAL, SIGNAL_THRESHOLD,
                            STRATEGY_WEIGHTS, USE_TESTNET,
                            ML_RETRAIN_INTERVAL, ML_MODEL_PATH,
                            ML_SCALER_PATH, DASHBOARD_REFRESH,
                            TRADE_QUANTITY, LOG_LEVEL)


# ── Logging setup ─────────────────────────────────────────────
logging.basicConfig(
    level     = getattr(logging, LOG_LEVEL),
    format    = "%(asctime)s  %(name)-16s  %(levelname)-8s  %(message)s",
    datefmt   = "%H:%M:%S",
    handlers  = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/bot.log"),
    ]
)
log = logging.getLogger("ScalpingBot")


class ScalpingBot:
    def __init__(self):
        self.client     = BinanceClient()
        self.aggregator = SignalAggregator()
        self.trade_log  = TradeLogger()
        self.running    = False
        self._trades_since_retrain = 0
        self._last_signal: dict = {}
        self._latest_df = None  # Store latest candle data for web API

        # Import futures config
        from config import USE_FUTURES, FUTURES_LEVERAGE
        self.is_futures = USE_FUTURES
        self.leverage = FUTURES_LEVERAGE if USE_FUTURES else 1

        # Fetch starting capital
        asset           = "USDT"
        starting_capital = self.client.get_account_balance(asset)
        if starting_capital == 0:
            starting_capital = 1_000.0   # fallback for testnet
            log.warning(f"Could not fetch balance — using default ${starting_capital}")
        self.risk_mgr   = RiskManager(starting_capital)

        # Initialize self-learning AI system
        self.learner = AdaptiveLearner()
        log.info("🧠 Self-learning AI system activated")

        mode_str = "FUTURES" if USE_FUTURES else "SPOT"
        lev_str = f" {self.leverage}x" if USE_FUTURES else ""
        log.info(f"Bot initialised | Mode={mode_str}{lev_str} | Symbol={SYMBOL} | "
                 f"Capital={starting_capital:.2f} USDT | "
                 f"{'TESTNET' if USE_TESTNET else 'LIVE'}")

        # Start web dashboard server
        from config import ENABLE_WEB_DASHBOARD
        if ENABLE_WEB_DASHBOARD:
            try:
                self._web_thread = start_web_server(
                    risk_manager_inst=self.risk_mgr,
                    trade_logger_inst=self.trade_log,
                    signal_aggregator_inst=self.aggregator,
                    binance_client_inst=self.client,
                    bot_inst=self
                )
            except Exception as e:
                log.warning(f"Web dashboard failed to start: {e}")

        # Graceful shutdown
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    # ── Main loop ─────────────────────────────────────────────
    def run(self):
        self.running = True
        log.info("🚀 Bot started — entering main loop")
        self._initial_train()

        last_dashboard = 0.0

        while self.running:
            try:
                loop_start = time.time()

                # 1. Fetch market data
                df = self.client.get_klines(SYMBOL, INTERVAL, limit=200)
                if df.empty:
                    log.warning("Empty klines — retrying in 5s")
                    time.sleep(5)
                    continue

                df = enrich_dataframe(df)
                if df.empty:
                    time.sleep(5)
                    continue

                # Store latest dataframe for web dashboard
                self._latest_df = df

                current_price = float(df["close"].iloc[-1])
                order_book    = self.client.get_order_book(SYMBOL)

                # 2. Compute signals
                signal_data = self.aggregator.compute(
                    df, order_book, STRATEGY_WEIGHTS)
                self._last_signal = signal_data
                combined = signal_data["combined"]

                # 3. Manage existing positions
                self._manage_positions(current_price, signal_data, df)

                # 4. Entry logic with 60%+ strategy filters
                if combined >= SIGNAL_THRESHOLD:
                    # Advanced validation for 60%+ accuracy
                    valid, reason = self._validate_60plus_filters("BUY", df, signal_data)
                    if not valid:
                        log.debug(f"BUY filtered (60%+): {reason}")
                    else:
                        can_trade, reason = self.risk_mgr.can_trade(new_side="BUY")
                        if can_trade:
                            self._open_trade("BUY", current_price,
                                             signal_data, df)
                        else:
                            log.debug(f"BUY blocked: {reason}")
                elif combined <= -SIGNAL_THRESHOLD:
                    # Advanced validation for 60%+ accuracy
                    valid, reason = self._validate_60plus_filters("SELL", df, signal_data)
                    if not valid:
                        log.debug(f"SELL filtered (60%+): {reason}")
                    else:
                        can_trade, reason = self.risk_mgr.can_trade(new_side="SELL")
                        if can_trade:
                            self._open_trade("SELL", current_price,
                                             signal_data, df)
                        else:
                            log.debug(f"SELL blocked: {reason}")

                # 5. Dashboard
                if time.time() - last_dashboard >= DASHBOARD_REFRESH:
                    render_dashboard(
                        self.risk_mgr, signal_data, df,
                        current_price, self.trade_log, SYMBOL)
                    last_dashboard = time.time()

                # 6. Periodic ML retrain
                self._maybe_retrain(df)

                # Sleep to align with next candle close
                elapsed = time.time() - loop_start
                sleep_time = max(1.0, 3.0 - elapsed)   # poll every ~3s (optimized for scalping)
                time.sleep(sleep_time)

            except Exception as e:
                log.error(f"Main loop error: {e}", exc_info=True)
                time.sleep(10)

    # ── Entry ─────────────────────────────────────────────────
    def _open_trade(self, side: str, price: float,
                    signal_data: dict, df):
        """Open position (spot or futures)."""
        sym_info = self.client.get_symbol_info(SYMBOL)

        # Extract ATR for ATR-based exits
        atr = float(df.iloc[-1].get('atr', 0)) if not df.empty else 0.0

        if self.is_futures:
            # Futures with leverage
            raw_qty, margin_req = self.risk_mgr.calculate_futures_quantity(
                price, signal_data["combined"], self.leverage, sym_info["minQty"])
            quantity = self.client.round_qty(raw_qty, sym_info["stepSize"])

            # Calculate liquidation BEFORE placing order
            liquidation_price = self.client.calculate_liquidation_price(
                side, price, self.leverage)

            # Safety check: verify not starting too close to liquidation
            from config import LIQUIDATION_BUFFER_PCT
            if side == "BUY":
                distance = (price - liquidation_price) / price
            else:
                distance = (liquidation_price - price) / price

            if distance < LIQUIDATION_BUFFER_PCT:
                log.warning(f"Skipping: liquidation {liquidation_price:.2f} too close "
                           f"({distance*100:.1f}% < {LIQUIDATION_BUFFER_PCT*100:.1f}%)")
                return

            # Place futures order
            order = self.client.place_futures_market_order(SYMBOL, side, quantity)
            if not order:
                return

            # Get fill price from order response or use current market price
            fill_price = float(order.get("avgPrice", 0))
            if fill_price == 0:
                fill_price = price  # Use current market price as fallback

            # Create position with futures params
            pos = self.risk_mgr.create_position(
                SYMBOL, side, fill_price, quantity, str(order["orderId"]),
                is_futures=True, leverage=self.leverage,
                liquidation_price=liquidation_price,
                entry_signal=signal_data, atr=atr)

            # Place stop-loss on exchange
            close_side = "SELL" if side == "BUY" else "BUY"
            self.client.place_futures_stop_loss(SYMBOL, close_side, quantity, pos.stop_loss)

            log.info(f"📈 {side} {self.leverage}x | ${fill_price:.2f} | "
                     f"Qty={quantity} | SL={pos.stop_loss:.2f} | Liq={liquidation_price:.2f}")
        else:
            # Existing spot logic
            raw_qty  = self.risk_mgr.calculate_quantity(
                price, signal_data["combined"], sym_info["minQty"])
            quantity = self.client.round_qty(raw_qty, sym_info["stepSize"])

            if quantity * price < sym_info["minNotional"]:
                log.debug("Trade below min notional — skipped")
                return

            order = self.client.place_market_order(SYMBOL, side, quantity)
            if not order:
                return

            fill_price = float(order.get("fills", [{}])[0].get("price", price)) \
                         if order.get("fills") else price

            pos = self.risk_mgr.create_position(
                SYMBOL, side, fill_price, quantity, str(order["orderId"]),
                entry_signal=signal_data, atr=atr)

            log.info(f"📈 OPEN {side} | Price={fill_price:.4f} | "
                     f"Qty={quantity} | Signal={signal_data['combined']:+.4f} | "
                     f"SL={pos.stop_loss:.4f} TP={pos.take_profit:.4f}")

    # ── Position management ────────────────────────────────────
    def _manage_positions(self, price: float, signal_data: dict, df):
        """Monitor positions and close on exit conditions."""
        for order_id, pos in list(self.risk_mgr.open_positions.items()):
            pos.update_trailing(price)

            # FUTURES: Check liquidation risk FIRST
            if pos.is_futures:
                is_risky, reason = self.risk_mgr.check_liquidation_risk(pos, price)
                if is_risky:
                    log.error(f"⚠️ LIQUIDATION RISK: {reason} — force closing")
                    self._close_position(order_id, pos, price, "liquidation_risk")
                    continue

                # Check funding rate
                funding = self.client.get_funding_rate(SYMBOL)
                from config import MAX_FUNDING_RATE_PCT
                if abs(funding) > MAX_FUNDING_RATE_PCT:
                    if (pos.side == "BUY" and funding > MAX_FUNDING_RATE_PCT) or \
                       (pos.side == "SELL" and funding < -MAX_FUNDING_RATE_PCT):
                        log.warning(f"High funding rate {funding*100:.4f}% — closing position")
                        self._close_position(order_id, pos, price, "high_funding")
                        continue

            # Regular exit checks
            exit_reason = None
            if pos.should_stop_loss(price):
                exit_reason = "stop_loss"
            elif pos.should_take_profit(price):
                exit_reason = "take_profit"
            elif self._signal_reversal(pos.side, signal_data):
                exit_reason = "signal_reversal"

            if exit_reason:
                self._close_position(order_id, pos, price, exit_reason)

    def _close_position(self, order_id: str, pos, price: float, reason: str):
        """Close position (spot or futures)."""
        close_side = "SELL" if pos.side == "BUY" else "BUY"

        if pos.is_futures:
            self.client.place_futures_market_order(
                SYMBOL, close_side, pos.quantity, reduce_only=True)
        else:
            self.client.place_market_order(SYMBOL, close_side, pos.quantity)

        closed = self.risk_mgr.close_position(order_id, price, reason)
        if closed:
            self.trade_log.log_trade(closed, price, reason, self._last_signal)
            self._trades_since_retrain += 1

            # Record trade in self-learning system
            if self._latest_df is not None and not self._latest_df.empty:
                indicators_row = self._latest_df.iloc[-1]
                trade_data = {
                    'timestamp': datetime.now().isoformat(),
                    'side': closed.side,
                    'entry_price': closed.entry_price,
                    'exit_price': price,
                    'pnl': closed.pnl,
                    'pnl_pct': (closed.pnl / (closed.entry_price * closed.quantity)) * 100,
                    'duration_sec': int(time.time() - closed.timestamp),
                    'reason': reason,
                    'signal_strength': abs(closed.entry_signal.get('combined', 0)),
                    'indicators': {
                        'rsi': float(indicators_row.get('rsi', 0)),
                        'adx': float(indicators_row.get('adx', 0)),
                        'atr_pct': float(indicators_row.get('atr_pct', 0)),
                        'candle_body': float(indicators_row.get('candle_body', 0)) / 100,
                        'macd_hist': float(indicators_row.get('macd_hist', 0)),
                        'stoch_k': float(indicators_row.get('stoch_k', 0)),
                    },
                    'market_conditions': {
                        'bb_squeeze': bool(indicators_row.get('bb_squeeze', False)),
                        'vol_ratio': float(indicators_row.get('vol_ratio', 1.0)),
                    }
                }
                self.learner.record_trade(trade_data)

    def _signal_reversal(self, current_side: str, signal_data: dict) -> bool:
        """Exit if signal strongly reverses against our position."""
        c = signal_data["combined"]
        if current_side == "BUY"  and c < -SIGNAL_THRESHOLD * 0.8:
            return True
        if current_side == "SELL" and c >  SIGNAL_THRESHOLD * 0.8:
            return True
        return False

    def _validate_60plus_filters(self, side: str, df, signal_data: dict):
        """
        Balanced Scalping Strategy v2.0 - Simplified filters
        Focus on core quality indicators, allow moderate signals
        Returns: (is_valid, reason)
        """
        from config import (USE_SUPERTREND, MAX_ATR_THRESHOLD,
                            REQUIRE_STRONG_CANDLE, MIN_CANDLE_BODY_PCT,
                            USE_DYNAMIC_CANDLE_FILTER, CANDLE_BODY_ATR_RATIO,
                            MIN_ADX_THRESHOLD)

        row = df.iloc[-1]

        # FILTER #0: Multi-Timeframe Trend Alignment (CRITICAL - Professional Edge)
        from indicators import check_mtf_alignment
        mtf_allowed, mtf_reason = check_mtf_alignment(self.client, SYMBOL, side)
        if not mtf_allowed:
            return False, mtf_reason

        # FILTER #1: SuperTrend Confirmation (Keep - proven effective)
        if USE_SUPERTREND:
            supertrend_dir = row.get("supertrend_direction", 0)
            if side == "BUY" and supertrend_dir != 1:
                return False, "SuperTrend not bullish"
            elif side == "SELL" and supertrend_dir != -1:
                return False, "SuperTrend not bearish"

        # FILTER #2: ADX Trend Strength (Keep - essential)
        adx = row.get("adx", 0)
        if adx < MIN_ADX_THRESHOLD:
            return False, f"Trend too weak (ADX {adx:.1f} < {MIN_ADX_THRESHOLD})"

        # FILTER #3: Volatility Range Check (Keep - risk management)
        atr_pct = row.get("atr_pct", 0)
        if atr_pct > MAX_ATR_THRESHOLD:
            return False, f"Volatility too high ({atr_pct:.2%})"

        # FILTER #4: Price Action Confirmation (FIXED: Dynamic based on volatility)
        if REQUIRE_STRONG_CANDLE:
            candle_body = row.get("candle_body", 0) / 100  # Convert to decimal

            # Dynamic candle filter: adjust requirement based on ATR
            if USE_DYNAMIC_CANDLE_FILTER:
                atr = row.get("atr", 0)
                price = row.get("close", 1)
                atr_pct = (atr / price) if price > 0 else 0

                # In high volatility, require smaller candles (15% of ATR)
                # In low volatility, use fixed minimum
                min_candle_required = max(MIN_CANDLE_BODY_PCT, atr_pct * CANDLE_BODY_ATR_RATIO)
            else:
                min_candle_required = MIN_CANDLE_BODY_PCT

            if candle_body < min_candle_required:
                return False, f"Weak candle body ({candle_body:.2%} < {min_candle_required:.2%})"

            # Check candle direction matches signal
            is_bullish = row.get("is_bullish", 0)
            if side == "BUY" and not is_bullish:
                return False, "Bearish candle on BUY signal"
            elif side == "SELL" and is_bullish:
                return False, "Bullish candle on SELL signal"

        return True, "Strategy v2.0 filters passed"

    # ── ML Training ───────────────────────────────────────────
    def _initial_train(self):
        log.info("📊 Loading initial data for ML training...")
        df = self.client.get_klines(SYMBOL, INTERVAL, limit=500)
        if not df.empty:
            df = enrich_dataframe(df)
            loaded = self.aggregator.ml.load(ML_MODEL_PATH, ML_SCALER_PATH)
            if not loaded:
                trained = self.aggregator.ml.train(df)
                if trained:
                    self.aggregator.ml.save(ML_MODEL_PATH, ML_SCALER_PATH)
                    log.info("✅ ML model trained & saved")
                else:
                    log.warning("⚠ ML training failed — using other strategies")
            else:
                log.info("✅ ML model loaded from disk")

    def _maybe_retrain(self, df):
        if self._trades_since_retrain >= ML_RETRAIN_INTERVAL:
            log.info("🔄 Retraining ML model...")
            trained = self.aggregator.ml.train(df)
            if trained:
                self.aggregator.ml.save(ML_MODEL_PATH, ML_SCALER_PATH)
                log.info("✅ ML model retrained")
            self._trades_since_retrain = 0

    # ── Shutdown ──────────────────────────────────────────────
    def _shutdown(self, *_):
        log.info("🛑 Shutdown signal received — closing positions...")
        self.running = False

        # Close all open positions at market
        for order_id, pos in list(self.risk_mgr.open_positions.items()):
            ticker = self.client.get_ticker(SYMBOL)
            price  = float(ticker.get("price", pos.entry_price))
            self._close_position(order_id, pos, price, "shutdown")

        perf = self.trade_log.performance_summary()
        log.info(f"📊 Final stats: {perf}")
        log.info("Bot stopped cleanly.")
        sys.exit(0)


# ── Entry point ───────────────────────────────────────────────
if __name__ == "__main__":
    bot = ScalpingBot()
    bot.run()
