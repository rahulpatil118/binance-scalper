#!/usr/bin/env python3
"""
Analyze Recent Performance - Deep Dive into Missed $3,400 Move
Backtest the last 24 hours to understand why profitable trades were missed
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from binance_client import BinanceClient
from indicators import enrich_dataframe, check_mtf_alignment
from strategies_pro import SignalAggregatorPro as SignalAggregator
from config import (
    SYMBOL, INTERVAL, STRATEGY_WEIGHTS, SIGNAL_THRESHOLD,
    MIN_ATR_THRESHOLD, MAX_ATR_THRESHOLD, MIN_ADX_THRESHOLD,
    REQUIRE_STRONG_CANDLE, MIN_CANDLE_BODY_PCT,
    USE_SUPERTREND, USE_TREND_FILTER, TREND_EMA_PERIOD,
    USE_MTF_FILTER, ATR_SL_MULTIPLIER, ATR_TP_MULTIPLIER,
    TESTNET_API_KEY, TESTNET_API_SECRET, USE_TESTNET
)

class RecentPerformanceAnalyzer:
    def __init__(self):
        self.client = BinanceClient()
        self.aggregator = SignalAggregator()
        self.trades = []
        self.filtered_signals = []

    def download_recent_data(self, hours=24):
        """Download recent market data"""
        print(f"\n{'='*70}")
        print(f"📊 DOWNLOADING LAST {hours} HOURS OF MARKET DATA")
        print(f"{'='*70}\n")

        # Calculate number of candles needed (5m interval)
        candles_needed = (hours * 60) // 5 + 200  # Extra for indicators

        df = self.client.get_klines(SYMBOL, INTERVAL, limit=candles_needed)

        if df.empty:
            print("❌ Failed to download data")
            return None

        # Enrich with indicators
        df = enrich_dataframe(df)

        print(f"✅ Downloaded {len(df)} candles")
        print(f"📅 Period: {df.index[0]} to {df.index[-1]}")
        print(f"💰 Price Range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
        print(f"📈 Move: ${df['close'].iloc[-1] - df['close'].iloc[0]:.2f} ({(df['close'].iloc[-1]/df['close'].iloc[0]-1)*100:.2f}%)\n")

        return df

    def check_filters(self, df, i, side, signal_value):
        """Check all filters and return which ones pass/fail"""
        row = df.iloc[i]
        filters = {}

        # Filter 0: Multi-Timeframe Alignment
        if USE_MTF_FILTER:
            try:
                mtf_allowed, mtf_reason = check_mtf_alignment(self.client, SYMBOL, side)
                filters['mtf_filter'] = {
                    'passed': mtf_allowed,
                    'reason': mtf_reason
                }
            except Exception as e:
                filters['mtf_filter'] = {
                    'passed': False,
                    'reason': f"MTF error: {str(e)}"
                }
        else:
            filters['mtf_filter'] = {'passed': True, 'reason': 'Disabled'}

        # Filter 1: ATR Volatility
        atr_pct = row.get('atr_pct', 0)
        atr_ok = MIN_ATR_THRESHOLD <= atr_pct <= MAX_ATR_THRESHOLD
        filters['atr_filter'] = {
            'passed': atr_ok,
            'value': f"{atr_pct:.2f}%",
            'range': f"{MIN_ATR_THRESHOLD:.2f}%-{MAX_ATR_THRESHOLD:.2f}%"
        }

        # Filter 2: ADX Trend Strength
        adx = row.get('adx', 0)
        adx_ok = adx >= MIN_ADX_THRESHOLD
        filters['adx_filter'] = {
            'passed': adx_ok,
            'value': f"{adx:.1f}",
            'required': f">={MIN_ADX_THRESHOLD}"
        }

        # Filter 3: SuperTrend Alignment
        if USE_SUPERTREND:
            st_direction = row.get('supertrend_direction', 0)
            required_st = 1 if side == "BUY" else -1
            st_ok = st_direction == required_st
            filters['supertrend_filter'] = {
                'passed': st_ok,
                'value': 'Bullish' if st_direction > 0 else 'Bearish',
                'required': 'Bullish' if side == "BUY" else 'Bearish'
            }
        else:
            filters['supertrend_filter'] = {'passed': True, 'reason': 'Disabled'}

        # Filter 4: Trend Filter (EMA-200)
        if USE_TREND_FILTER:
            # Calculate EMA-200 if not in dataframe
            if 'ema_200' not in df.columns:
                from indicators import compute_ema
                df['ema_200'] = compute_ema(df['close'], TREND_EMA_PERIOD)

            price = row['close']
            ema_200 = row.get('ema_200', price)

            if side == "BUY":
                trend_ok = price > ema_200
            else:
                trend_ok = price < ema_200

            filters['trend_filter'] = {
                'passed': trend_ok,
                'value': f"Price ${price:.2f} {'>' if price > ema_200 else '<'} EMA200 ${ema_200:.2f}",
                'required': f"Price {'>' if side == 'BUY' else '<'} EMA200"
            }
        else:
            filters['trend_filter'] = {'passed': True, 'reason': 'Disabled'}

        # Filter 5: Candle Body Strength
        if REQUIRE_STRONG_CANDLE:
            candle_body = row.get('candle_body', 0) / 100  # Convert from percentage
            candle_ok = candle_body >= MIN_CANDLE_BODY_PCT
            filters['candle_filter'] = {
                'passed': candle_ok,
                'value': f"{candle_body*100:.3f}%",
                'required': f">={MIN_CANDLE_BODY_PCT*100:.3f}%"
            }
        else:
            filters['candle_filter'] = {'passed': True, 'reason': 'Disabled'}

        # Overall signal threshold
        filters['signal_threshold'] = {
            'passed': abs(signal_value) >= SIGNAL_THRESHOLD,
            'value': f"{signal_value:.4f}",
            'required': f"±{SIGNAL_THRESHOLD}"
        }

        return filters

    def simulate_trade(self, entry_price, side, atr, exit_price=None):
        """Simulate a trade with ATR-based stops"""
        if side == "BUY":
            stop_loss = entry_price - (atr * ATR_SL_MULTIPLIER)
            take_profit = entry_price + (atr * ATR_TP_MULTIPLIER)
        else:
            stop_loss = entry_price + (atr * ATR_SL_MULTIPLIER)
            take_profit = entry_price - (atr * ATR_TP_MULTIPLIER)

        # If exit price provided, calculate actual P&L
        if exit_price:
            if side == "BUY":
                pnl_pct = (exit_price - entry_price) / entry_price * 100
            else:
                pnl_pct = (entry_price - exit_price) / entry_price * 100

            # Check if hit SL or TP
            if side == "BUY":
                if exit_price <= stop_loss:
                    outcome = "STOP_LOSS"
                elif exit_price >= take_profit:
                    outcome = "TAKE_PROFIT"
                else:
                    outcome = "MANUAL_EXIT"
            else:
                if exit_price >= stop_loss:
                    outcome = "STOP_LOSS"
                elif exit_price <= take_profit:
                    outcome = "TAKE_PROFIT"
                else:
                    outcome = "MANUAL_EXIT"
        else:
            pnl_pct = 0
            outcome = "OPEN"

        return {
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'pnl_pct': pnl_pct,
            'outcome': outcome
        }

    def backtest(self, df, start_index=200):
        """Backtest recent period with detailed analysis"""
        print(f"\n{'='*70}")
        print(f"🔄 BACKTESTING FROM INDEX {start_index} TO {len(df)-1}")
        print(f"{'='*70}\n")

        position = None
        signals_generated = 0
        signals_filtered = 0

        for i in range(start_index, len(df)):
            row = df.iloc[i]
            current_time = df.index[i]
            current_price = row['close']
            atr = row['atr']

            # Get signal
            signal_data = self.aggregator.compute(df.iloc[:i+1], {}, STRATEGY_WEIGHTS)
            signal_value = signal_data.get('combined', 0)  # Correct key

            # Manage existing position
            if position:
                trade = self.simulate_trade(
                    position['entry_price'],
                    position['side'],
                    position['atr'],
                    current_price
                )

                # Check if SL/TP hit
                if position['side'] == "BUY":
                    if current_price <= trade['stop_loss']:
                        # Stop loss hit
                        position['exit_price'] = trade['stop_loss']
                        position['exit_time'] = current_time
                        position['outcome'] = "STOP_LOSS"
                        position['pnl_pct'] = (trade['stop_loss'] - position['entry_price']) / position['entry_price'] * 100
                        position['duration_minutes'] = (current_time - position['entry_time']).total_seconds() / 60
                        self.trades.append(position)
                        position = None
                        continue
                    elif current_price >= trade['take_profit']:
                        # Take profit hit
                        position['exit_price'] = trade['take_profit']
                        position['exit_time'] = current_time
                        position['outcome'] = "TAKE_PROFIT"
                        position['pnl_pct'] = (trade['take_profit'] - position['entry_price']) / position['entry_price'] * 100
                        position['duration_minutes'] = (current_time - position['entry_time']).total_seconds() / 60
                        self.trades.append(position)
                        position = None
                        continue
                else:  # SELL
                    if current_price >= trade['stop_loss']:
                        # Stop loss hit
                        position['exit_price'] = trade['stop_loss']
                        position['exit_time'] = current_time
                        position['outcome'] = "STOP_LOSS"
                        position['pnl_pct'] = (position['entry_price'] - trade['stop_loss']) / position['entry_price'] * 100
                        position['duration_minutes'] = (current_time - position['entry_time']).total_seconds() / 60
                        self.trades.append(position)
                        position = None
                        continue
                    elif current_price <= trade['take_profit']:
                        # Take profit hit
                        position['exit_price'] = trade['take_profit']
                        position['exit_time'] = current_time
                        position['outcome'] = "TAKE_PROFIT"
                        position['pnl_pct'] = (position['entry_price'] - trade['take_profit']) / position['entry_price'] * 100
                        position['duration_minutes'] = (current_time - position['entry_time']).total_seconds() / 60
                        self.trades.append(position)
                        position = None
                        continue

                # Check for signal reversal
                if position['side'] == "BUY" and signal_value < -SIGNAL_THRESHOLD:
                    position['exit_price'] = current_price
                    position['exit_time'] = current_time
                    position['outcome'] = "SIGNAL_REVERSAL"
                    position['pnl_pct'] = (current_price - position['entry_price']) / position['entry_price'] * 100
                    position['duration_minutes'] = (current_time - position['entry_time']).total_seconds() / 60
                    self.trades.append(position)
                    position = None
                elif position['side'] == "SELL" and signal_value > SIGNAL_THRESHOLD:
                    position['exit_price'] = current_price
                    position['exit_time'] = current_time
                    position['outcome'] = "SIGNAL_REVERSAL"
                    position['pnl_pct'] = (position['entry_price'] - current_price) / position['entry_price'] * 100
                    position['duration_minutes'] = (current_time - position['entry_time']).total_seconds() / 60
                    self.trades.append(position)
                    position = None

            # Check for new entry signal
            if not position:
                side = None
                if signal_value > SIGNAL_THRESHOLD:
                    side = "BUY"
                    signals_generated += 1
                elif signal_value < -SIGNAL_THRESHOLD:
                    side = "SELL"
                    signals_generated += 1

                if side:
                    # Check all filters
                    filters = self.check_filters(df, i, side, signal_value)

                    all_passed = all(f.get('passed', True) for f in filters.values())

                    if all_passed:
                        # Open position
                        trade_sim = self.simulate_trade(current_price, side, atr)
                        position = {
                            'entry_time': current_time,
                            'entry_price': current_price,
                            'side': side,
                            'signal': signal_value,
                            'atr': atr,
                            'stop_loss': trade_sim['stop_loss'],
                            'take_profit': trade_sim['take_profit'],
                            'filters': {k: 'PASS' for k in filters.keys()}
                        }
                    else:
                        # Signal filtered
                        signals_filtered += 1
                        failed_filters = [k for k, v in filters.items() if not v.get('passed', True)]

                        self.filtered_signals.append({
                            'time': current_time,
                            'price': current_price,
                            'side': side,
                            'signal': signal_value,
                            'filters': filters,
                            'failed_filters': failed_filters
                        })

        # Close any open position at end
        if position:
            position['exit_price'] = df.iloc[-1]['close']
            position['exit_time'] = df.index[-1]
            position['outcome'] = "END_OF_PERIOD"
            position['pnl_pct'] = (position['exit_price'] - position['entry_price']) / position['entry_price'] * 100 if position['side'] == "BUY" else (position['entry_price'] - position['exit_price']) / position['entry_price'] * 100
            position['duration_minutes'] = (position['exit_time'] - position['entry_time']).total_seconds() / 60
            self.trades.append(position)

        print(f"✅ Backtest Complete")
        print(f"   📊 Signals Generated: {signals_generated}")
        print(f"   🚫 Signals Filtered: {signals_filtered} ({signals_filtered/signals_generated*100:.1f}%)" if signals_generated > 0 else "")
        print(f"   ✅ Trades Executed: {len(self.trades)}\n")

    def analyze_results(self):
        """Analyze and display results"""
        print(f"\n{'='*70}")
        print(f"📈 BACKTEST RESULTS")
        print(f"{'='*70}\n")

        if not self.trades:
            print("❌ No trades executed during backtest period\n")
            return

        # Calculate statistics
        wins = [t for t in self.trades if t['pnl_pct'] > 0]
        losses = [t for t in self.trades if t['pnl_pct'] < 0]

        win_rate = len(wins) / len(self.trades) * 100
        avg_win = np.mean([t['pnl_pct'] for t in wins]) if wins else 0
        avg_loss = np.mean([t['pnl_pct'] for t in losses]) if losses else 0
        total_pnl = sum(t['pnl_pct'] for t in self.trades)

        print(f"Total Trades: {len(self.trades)}")
        print(f"Win Rate: {win_rate:.1f}% ({len(wins)}W / {len(losses)}L)")
        print(f"Avg Win: {avg_win:+.2f}%")
        print(f"Avg Loss: {avg_loss:+.2f}%")
        print(f"Total P&L: {total_pnl:+.2f}%")
        print(f"Profit Factor: {abs(avg_win * len(wins) / (avg_loss * len(losses))):.2f}" if losses else "∞")
        print()

        # Display each trade
        print(f"{'='*70}")
        print(f"TRADE DETAILS")
        print(f"{'='*70}\n")

        for i, trade in enumerate(self.trades, 1):
            pnl_symbol = "✅" if trade['pnl_pct'] > 0 else "❌"
            print(f"{pnl_symbol} Trade #{i} - {trade['side']}")
            print(f"   Entry: {trade['entry_time']} @ ${trade['entry_price']:.2f}")
            print(f"   Exit:  {trade['exit_time']} @ ${trade['exit_price']:.2f}")
            print(f"   P&L: {trade['pnl_pct']:+.2f}% | Outcome: {trade['outcome']}")
            print(f"   Duration: {trade['duration_minutes']:.1f} minutes")
            print(f"   Signal: {trade['signal']:+.4f}")
            print(f"   SL: ${trade['stop_loss']:.2f} | TP: ${trade['take_profit']:.2f}")
            print()

    def analyze_filtered_signals(self):
        """Analyze why signals were filtered"""
        print(f"\n{'='*70}")
        print(f"🚫 FILTERED SIGNALS ANALYSIS")
        print(f"{'='*70}\n")

        if not self.filtered_signals:
            print("✅ No signals were filtered (all passed)\n")
            return

        print(f"Total Filtered: {len(self.filtered_signals)}\n")

        # Count filter failures
        filter_failures = {}
        for sig in self.filtered_signals:
            for failed_filter in sig['failed_filters']:
                filter_failures[failed_filter] = filter_failures.get(failed_filter, 0) + 1

        print("Filter Failure Breakdown:")
        for filter_name, count in sorted(filter_failures.items(), key=lambda x: x[1], reverse=True):
            pct = count / len(self.filtered_signals) * 100
            print(f"  {filter_name}: {count} times ({pct:.1f}%)")
        print()

        # Show first 10 filtered signals with details
        print(f"{'='*70}")
        print(f"SAMPLE OF FILTERED SIGNALS (First 10)")
        print(f"{'='*70}\n")

        for i, sig in enumerate(self.filtered_signals[:10], 1):
            print(f"❌ Filtered Signal #{i} - {sig['side']}")
            print(f"   Time: {sig['time']}")
            print(f"   Price: ${sig['price']:.2f}")
            print(f"   Signal: {sig['signal']:+.4f}")
            print(f"   Failed Filters: {', '.join(sig['failed_filters'])}")

            # Show details of failed filters
            for filter_name in sig['failed_filters']:
                filter_info = sig['filters'][filter_name]
                if 'value' in filter_info:
                    print(f"      {filter_name}: {filter_info['value']} (need: {filter_info.get('required', filter_info.get('range', 'N/A'))})")
                else:
                    print(f"      {filter_name}: {filter_info.get('reason', 'Failed')}")
            print()

    def find_missed_opportunities(self, df):
        """Find potential profitable setups that were filtered"""
        print(f"\n{'='*70}")
        print(f"💰 MISSED OPPORTUNITIES ANALYSIS")
        print(f"{'='*70}\n")

        missed_profits = []

        for sig in self.filtered_signals:
            # Find what would have happened if we took this trade
            entry_time = sig['time']
            entry_price = sig['price']
            side = sig['side']

            # Find next N candles to simulate
            entry_idx = df.index.get_loc(entry_time)
            if entry_idx + 50 < len(df):
                future_prices = df.iloc[entry_idx:entry_idx+50]

                # Calculate ATR-based stops
                atr = df.iloc[entry_idx]['atr']
                if side == "BUY":
                    stop_loss = entry_price - (atr * ATR_SL_MULTIPLIER)
                    take_profit = entry_price + (atr * ATR_TP_MULTIPLIER)
                else:
                    stop_loss = entry_price + (atr * ATR_SL_MULTIPLIER)
                    take_profit = entry_price - (atr * ATR_TP_MULTIPLIER)

                # Simulate trade outcome
                outcome = None
                exit_price = None
                exit_idx = None

                for j, (idx, row) in enumerate(future_prices.iterrows()):
                    if side == "BUY":
                        if row['low'] <= stop_loss:
                            outcome = "STOP_LOSS"
                            exit_price = stop_loss
                            exit_idx = j
                            break
                        elif row['high'] >= take_profit:
                            outcome = "TAKE_PROFIT"
                            exit_price = take_profit
                            exit_idx = j
                            break
                    else:
                        if row['high'] >= stop_loss:
                            outcome = "STOP_LOSS"
                            exit_price = stop_loss
                            exit_idx = j
                            break
                        elif row['low'] <= take_profit:
                            outcome = "TAKE_PROFIT"
                            exit_price = take_profit
                            exit_idx = j
                            break

                if outcome:
                    if side == "BUY":
                        pnl_pct = (exit_price - entry_price) / entry_price * 100
                    else:
                        pnl_pct = (entry_price - exit_price) / entry_price * 100

                    if pnl_pct > 0:  # Profitable missed opportunity
                        missed_profits.append({
                            'time': entry_time,
                            'side': side,
                            'entry_price': entry_price,
                            'exit_price': exit_price,
                            'pnl_pct': pnl_pct,
                            'outcome': outcome,
                            'candles': exit_idx,
                            'failed_filters': sig['failed_filters'],
                            'signal': sig['signal']
                        })

        if missed_profits:
            missed_profits.sort(key=lambda x: x['pnl_pct'], reverse=True)
            total_missed = sum(m['pnl_pct'] for m in missed_profits)

            print(f"Found {len(missed_profits)} PROFITABLE trades that were filtered out!")
            print(f"Total Missed P&L: {total_missed:+.2f}%\n")

            print(f"{'='*70}")
            print(f"TOP MISSED OPPORTUNITIES")
            print(f"{'='*70}\n")

            for i, opp in enumerate(missed_profits[:10], 1):
                print(f"💸 Missed Trade #{i} - {opp['side']}")
                print(f"   Time: {opp['time']}")
                print(f"   Entry: ${opp['entry_price']:.2f}")
                print(f"   Exit: ${opp['exit_price']:.2f}")
                print(f"   Potential P&L: {opp['pnl_pct']:+.2f}%")
                print(f"   Outcome: {opp['outcome']} after {opp['candles']} candles")
                print(f"   Signal Strength: {opp['signal']:+.4f}")
                print(f"   Blocked By: {', '.join(opp['failed_filters'])}")
                print()
        else:
            print("✅ No profitable opportunities were missed by filters\n")

        return missed_profits

def main():
    analyzer = RecentPerformanceAnalyzer()

    # Download recent data (24 hours)
    df = analyzer.download_recent_data(hours=24)

    if df is None or df.empty:
        print("Failed to download data")
        return

    # Run backtest
    analyzer.backtest(df)

    # Analyze results
    analyzer.analyze_results()

    # Analyze filtered signals
    analyzer.analyze_filtered_signals()

    # Find missed opportunities
    missed = analyzer.find_missed_opportunities(df)

    # Summary and recommendations
    print(f"\n{'='*70}")
    print(f"📋 RECOMMENDATIONS")
    print(f"{'='*70}\n")

    if analyzer.trades:
        wins = [t for t in analyzer.trades if t['pnl_pct'] > 0]
        win_rate = len(wins) / len(analyzer.trades) * 100

        if win_rate < 50:
            print("⚠️ Win Rate Below 50%:")
            print("   - Review entry criteria (too aggressive)")
            print("   - Consider tighter filters or better confirmation")
            print()

        # Check if most losses were quick stop-outs
        quick_losses = [t for t in analyzer.trades if t['pnl_pct'] < 0 and t['duration_minutes'] < 10]
        if len(quick_losses) > len(analyzer.trades) * 0.5:
            print("⚠️ Many Quick Stop-Outs:")
            print(f"   - {len(quick_losses)}/{len(analyzer.trades)} trades stopped out within 10 minutes")
            print("   - Consider wider ATR multiplier (1.5x → 2.0x)")
            print("   - Add entry confirmation (wait 1-2 candles)")
            print()

    if missed:
        # Find most common blocking filter
        all_blocks = {}
        for m in missed:
            for f in m['failed_filters']:
                all_blocks[f] = all_blocks.get(f, 0) + 1

        most_common = max(all_blocks.items(), key=lambda x: x[1]) if all_blocks else None

        if most_common:
            print(f"⚠️ Filter Blocking Profitable Trades:")
            print(f"   - '{most_common[0]}' blocked {most_common[1]} profitable setups")
            print(f"   - Consider relaxing this filter or making it dynamic")
            print()

    print("✅ Analysis Complete!\n")

if __name__ == "__main__":
    main()
