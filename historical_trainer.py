#!/usr/bin/env python3
# ============================================================
#  historical_trainer.py — Pre-Train AI on Historical Data
#  Train the self-learning AI on past trades for instant optimization
# ============================================================
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from binance_client import BinanceClient
from indicators import enrich_dataframe
from strategies_pro import SignalAggregatorPro
from adaptive_learner import AdaptiveLearner
from config import (SYMBOL, INTERVAL, SIGNAL_THRESHOLD, STRATEGY_WEIGHTS,
                    MIN_ADX_THRESHOLD, MIN_CANDLE_BODY_PCT, STOP_LOSS_PCT,
                    TAKE_PROFIT_PCT, MAX_ATR_THRESHOLD, USE_SUPERTREND)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-16s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("HistoricalTrainer")


class HistoricalTrainer:
    """
    Train the self-learning AI on historical data
    """

    def __init__(self, lookback_days: int = 90):
        self.lookback_days = lookback_days
        self.client = BinanceClient()
        self.aggregator = SignalAggregatorPro()
        self.learner = AdaptiveLearner()

        # Trading parameters (will be optimized by AI)
        self.signal_threshold = SIGNAL_THRESHOLD
        self.min_adx = MIN_ADX_THRESHOLD
        self.min_candle_body = MIN_CANDLE_BODY_PCT
        self.stop_loss_pct = STOP_LOSS_PCT
        self.take_profit_pct = TAKE_PROFIT_PCT

        log.info(f"🎓 Historical Trainer initialized for {lookback_days} days")

    def download_historical_data(self) -> pd.DataFrame:
        """Download historical klines from Binance"""
        log.info(f"📥 Downloading {self.lookback_days} days of {SYMBOL} data...")

        # Calculate how many 5m candles we need
        candles_needed = self.lookback_days * 24 * 12  # 12 candles per hour
        candles_needed = min(candles_needed, 1000)  # Binance limit

        df = self.client.get_klines(SYMBOL, INTERVAL, limit=candles_needed)

        if df.empty:
            log.error("❌ Failed to download data")
            return pd.DataFrame()

        log.info(f"✅ Downloaded {len(df)} candles ({len(df)/12/24:.1f} days)")
        return df

    def simulate_trading(self, df: pd.DataFrame) -> list:
        """
        Simulate trading on historical data and return all trades
        """
        log.info("🔄 Simulating trading on historical data...")

        # Enrich with indicators
        df = enrich_dataframe(df)

        if df.empty:
            log.error("❌ Failed to enrich dataframe")
            return []

        trades = []
        position = None  # Current open position

        for i in range(100, len(df)):  # Start after warmup period
            row = df.iloc[i]
            current_time = df.index[i]
            current_price = row['close']

            # Get signal
            signal_data = self.aggregator.compute(
                df.iloc[:i+1],  # Only use data up to current point
                {},  # No orderbook in historical
                STRATEGY_WEIGHTS
            )

            combined_signal = signal_data['combined']

            # Manage existing position
            if position:
                duration = (current_time - position['entry_time']).total_seconds()

                # Check exit conditions
                exit_reason = None
                exit_price = current_price

                if position['side'] == 'BUY':
                    # Check stop loss
                    if current_price <= position['stop_loss']:
                        exit_reason = 'stop_loss'
                        exit_price = position['stop_loss']
                    # Check take profit
                    elif current_price >= position['take_profit']:
                        exit_reason = 'take_profit'
                        exit_price = position['take_profit']
                    # Check signal reversal
                    elif combined_signal < -self.signal_threshold * 0.8:
                        exit_reason = 'signal_reversal'
                else:  # SELL
                    # Check stop loss
                    if current_price >= position['stop_loss']:
                        exit_reason = 'stop_loss'
                        exit_price = position['stop_loss']
                    # Check take profit
                    elif current_price <= position['take_profit']:
                        exit_reason = 'take_profit'
                        exit_price = position['take_profit']
                    # Check signal reversal
                    elif combined_signal > self.signal_threshold * 0.8:
                        exit_reason = 'signal_reversal'

                # Close position if exit triggered
                if exit_reason:
                    pnl = self.calculate_pnl(position, exit_price)

                    trade = {
                        'timestamp': current_time.isoformat(),
                        'side': position['side'],
                        'entry_price': position['entry_price'],
                        'exit_price': exit_price,
                        'pnl': pnl,
                        'pnl_pct': (pnl / position['entry_price']) * 100,
                        'duration_sec': int(duration),
                        'reason': exit_reason,
                        'signal_strength': position['signal_strength'],
                        'indicators': position['indicators'],
                        'market_conditions': position['market_conditions']
                    }

                    trades.append(trade)
                    position = None

                    # Log trade
                    win_loss = "WIN" if pnl > 0 else "LOSS"
                    log.info(f"  Trade #{len(trades)}: {win_loss} {position['side'] if position else trade['side']} "
                           f"${pnl:+.2f} ({trade['pnl_pct']:+.2f}%) - {exit_reason}")

            # Entry logic (if no position)
            if not position:
                # Check if signal meets threshold
                if abs(combined_signal) >= self.signal_threshold:
                    side = 'BUY' if combined_signal > 0 else 'SELL'

                    # Apply filters
                    if self.check_filters(row, side, signal_data):
                        # Open position
                        position = self.open_position(side, current_price, current_time,
                                                     row, signal_data)

        # Close any remaining position at end
        if position:
            final_row = df.iloc[-1]
            final_price = final_row['close']
            pnl = self.calculate_pnl(position, final_price)

            trade = {
                'timestamp': df.index[-1].isoformat(),
                'side': position['side'],
                'entry_price': position['entry_price'],
                'exit_price': final_price,
                'pnl': pnl,
                'pnl_pct': (pnl / position['entry_price']) * 100,
                'duration_sec': int((df.index[-1] - position['entry_time']).total_seconds()),
                'reason': 'end_of_data',
                'signal_strength': position['signal_strength'],
                'indicators': position['indicators'],
                'market_conditions': position['market_conditions']
            }
            trades.append(trade)

        log.info(f"✅ Simulation complete: {len(trades)} trades generated")
        return trades

    def check_filters(self, row, side: str, signal_data: dict) -> bool:
        """Apply trading filters"""

        # Filter #1: SuperTrend
        if USE_SUPERTREND:
            supertrend_dir = row.get('supertrend_direction', 0)
            if side == 'BUY' and supertrend_dir != 1:
                return False
            elif side == 'SELL' and supertrend_dir != -1:
                return False

        # Filter #2: ADX
        adx = row.get('adx', 0)
        if adx < self.min_adx:
            return False

        # Filter #3: ATR
        atr_pct = row.get('atr_pct', 0)
        if atr_pct > MAX_ATR_THRESHOLD:
            return False

        # Filter #4: Candle body
        candle_body = row.get('candle_body', 0) / 100
        if candle_body < self.min_candle_body:
            return False

        # Filter #5: Candle direction
        is_bullish = row.get('is_bullish', 0)
        if side == 'BUY' and not is_bullish:
            return False
        elif side == 'SELL' and is_bullish:
            return False

        return True

    def open_position(self, side: str, price: float, time, row, signal_data: dict) -> dict:
        """Create position dict"""
        if side == 'BUY':
            stop_loss = price * (1 - self.stop_loss_pct)
            take_profit = price * (1 + self.take_profit_pct)
        else:
            stop_loss = price * (1 + self.stop_loss_pct)
            take_profit = price * (1 - self.take_profit_pct)

        return {
            'side': side,
            'entry_price': price,
            'entry_time': time,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'signal_strength': abs(signal_data.get('combined', 0)),
            'indicators': {
                'rsi': float(row.get('rsi', 0)),
                'adx': float(row.get('adx', 0)),
                'atr_pct': float(row.get('atr_pct', 0)),
                'candle_body': float(row.get('candle_body', 0)) / 100,
                'macd_hist': float(row.get('macd_hist', 0)),
                'stoch_k': float(row.get('stoch_k', 0)),
            },
            'market_conditions': {
                'bb_squeeze': bool(row.get('bb_squeeze', False)),
                'vol_ratio': float(row.get('vol_ratio', 1.0)),
            }
        }

    def calculate_pnl(self, position: dict, exit_price: float) -> float:
        """Calculate P&L (simplified - no position size)"""
        if position['side'] == 'BUY':
            return (exit_price - position['entry_price']) / position['entry_price'] * 1000
        else:
            return (position['entry_price'] - exit_price) / position['entry_price'] * 1000

    def train_ai(self, trades: list):
        """Feed all historical trades to AI for learning"""
        log.info(f"🧠 Training AI on {len(trades)} historical trades...")

        for trade in trades:
            self.learner.record_trade(trade)

        # Get optimized parameters
        optimized = self.learner.get_optimized_params()
        report = self.learner.get_performance_report()

        log.info("=" * 70)
        log.info("  🎓 AI TRAINING COMPLETE")
        log.info("=" * 70)
        log.info(f"Total Trades: {report['total_trades']}")
        log.info(f"Win Rate: {report['win_rate']*100:.1f}%")
        log.info(f"Wins/Losses: {report['wins']}/{report['losses']}")
        log.info(f"Avg Win: ${report['avg_win']:.2f}")
        log.info(f"Avg Loss: ${report['avg_loss']:.2f}")
        log.info(f"Profit Factor: {report['profit_factor']:.2f}")
        log.info("")
        log.info("  🎯 OPTIMIZED PARAMETERS:")
        log.info(f"Signal Threshold: {optimized['signal_threshold']:.4f}")
        log.info(f"Min Candle Body: {optimized['min_candle_body']*100:.2f}%")
        log.info(f"Min ADX: {optimized['min_adx']:.1f}")
        log.info(f"Stop Loss: {optimized['stop_loss_pct']*100:.1f}%")
        log.info("=" * 70)

        return optimized, report


def main():
    """Main training function"""
    print("=" * 70)
    print("  🎓 HISTORICAL AI TRAINER")
    print("  Pre-train AI on historical data for instant optimization")
    print("=" * 70)
    print()

    # Create trainer
    trainer = HistoricalTrainer(lookback_days=90)

    # Step 1: Download data
    df = trainer.download_historical_data()
    if df.empty:
        log.error("Failed to download data")
        return

    print()

    # Step 2: Simulate trading
    trades = trainer.simulate_trading(df)
    if not trades:
        log.error("No trades generated from simulation")
        return

    print()

    # Step 3: Train AI
    optimized, report = trainer.train_ai(trades)

    print()
    print("=" * 70)
    print("  ✅ TRAINING COMPLETE!")
    print("=" * 70)
    print()
    print("The AI is now pre-trained and ready to trade with optimized parameters!")
    print()
    print("Next steps:")
    print("1. Review the optimized parameters above")
    print("2. Bot will automatically use these parameters")
    print("3. AI will continue learning from live trades")
    print()
    print("Files created:")
    print("  - logs/trade_memory.json (training data)")
    print("  - logs/optimized_params.json (optimized parameters)")
    print("=" * 70)


if __name__ == "__main__":
    main()
