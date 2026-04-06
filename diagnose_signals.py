#!/usr/bin/env python3
"""
Signal Diagnostic Tool - Find out why signals aren't being generated
"""

import pandas as pd
import numpy as np
from binance_client import BinanceClient
from indicators import enrich_dataframe
from strategies_pro import SignalAggregatorPro as SignalAggregator
from config import SYMBOL, INTERVAL, STRATEGY_WEIGHTS, SIGNAL_THRESHOLD

def main():
    print("\n" + "="*70)
    print("🔍 SIGNAL DIAGNOSTIC ANALYSIS")
    print("="*70 + "\n")

    # Initialize
    client = BinanceClient()
    aggregator = SignalAggregator()

    # Download recent data
    print("📊 Downloading last 24 hours of data...")
    df = client.get_klines(SYMBOL, INTERVAL, limit=500)
    df = enrich_dataframe(df)
    print(f"✅ Downloaded {len(df)} candles\n")

    # Analyze signals from last 100 candles
    print("="*70)
    print("SIGNAL GENERATION ANALYSIS (Last 100 Candles)")
    print("="*70 + "\n")

    signal_history = []

    for i in range(len(df)-100, len(df)):
        row = df.iloc[i]
        time = df.index[i]
        price = row['close']

        # Get signal
        signal_data = aggregator.compute(df.iloc[:i+1], {}, STRATEGY_WEIGHTS)
        combined_signal = signal_data.get('combined', 0)  # Correct key is 'combined'

        scores = signal_data.get('scores', {})
        signal_history.append({
            'time': time,
            'price': price,
            'signal': combined_signal,
            'rsi_ema': scores.get('rsi_ema', 0),
            'professional': scores.get('professional', 0),
            'bollinger': scores.get('bollinger', 0),
            'ml_signal': scores.get('ml_signal', 0)
        })

    # Convert to DataFrame for analysis
    signals_df = pd.DataFrame(signal_history)

    # Statistics
    print(f"Signal Threshold: ±{SIGNAL_THRESHOLD}\n")
    print("Signal Statistics:")
    print(f"  Max Signal: {signals_df['signal'].max():+.4f}")
    print(f"  Min Signal: {signals_df['signal'].min():+.4f}")
    print(f"  Mean Signal: {signals_df['signal'].mean():+.4f}")
    print(f"  Std Dev: {signals_df['signal'].std():.4f}\n")

    # Count signals above threshold
    buy_signals = (signals_df['signal'] > SIGNAL_THRESHOLD).sum()
    sell_signals = (signals_df['signal'] < -SIGNAL_THRESHOLD).sum()
    neutral = len(signals_df) - buy_signals - sell_signals

    print("Signal Distribution:")
    print(f"  BUY signals (>{SIGNAL_THRESHOLD}): {buy_signals} ({buy_signals/len(signals_df)*100:.1f}%)")
    print(f"  SELL signals (<-{SIGNAL_THRESHOLD}): {sell_signals} ({sell_signals/len(signals_df)*100:.1f}%)")
    print(f"  Neutral: {neutral} ({neutral/len(signals_df)*100:.1f}%)\n")

    # Show strongest signals
    print("="*70)
    print("STRONGEST SIGNALS (Top 10)")
    print("="*70 + "\n")

    top_signals = signals_df.nlargest(5, 'signal')
    bottom_signals = signals_df.nsmallest(5, 'signal')
    all_top = pd.concat([top_signals, bottom_signals]).sort_values('signal', ascending=False)

    for idx, row in all_top.iterrows():
        direction = "BUY 🟢" if row['signal'] > SIGNAL_THRESHOLD else "SELL 🔴" if row['signal'] < -SIGNAL_THRESHOLD else "NEUTRAL ⚪"
        print(f"{direction}")
        print(f"  Time: {row['time']}")
        print(f"  Price: ${row['price']:.2f}")
        print(f"  Combined Signal: {row['signal']:+.4f} {'✅ ABOVE THRESHOLD' if abs(row['signal']) >= SIGNAL_THRESHOLD else '❌ BELOW THRESHOLD'}")
        print(f"  Strategy Breakdown:")
        print(f"    RSI+EMA (45%):      {row['rsi_ema']:+.4f}")
        print(f"    Professional (25%): {row['professional']:+.4f}")
        print(f"    Bollinger (25%):    {row['bollinger']:+.4f}")
        print(f"    ML (5%):            {row['ml_signal']:+.4f}")
        print()

    # Analyze strategy weights
    print("="*70)
    print("STRATEGY WEIGHTS ANALYSIS")
    print("="*70 + "\n")

    print("Current Weights:")
    for name, weight in STRATEGY_WEIGHTS.items():
        print(f"  {name}: {weight*100:.0f}%")

    print("\nStrategy Signal Ranges:")
    print(f"  RSI+EMA:      {signals_df['rsi_ema'].min():+.4f} to {signals_df['rsi_ema'].max():+.4f}")
    print(f"  Professional: {signals_df['professional'].min():+.4f} to {signals_df['professional'].max():+.4f}")
    print(f"  Bollinger:    {signals_df['bollinger'].min():+.4f} to {signals_df['bollinger'].max():+.4f}")
    print(f"  ML:           {signals_df['ml_signal'].min():+.4f} to {signals_df['ml_signal'].max():+.4f}")

    # Check if threshold is too high
    print("\n" + "="*70)
    print("THRESHOLD ANALYSIS")
    print("="*70 + "\n")

    # Test different thresholds
    thresholds = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10]

    print("Signals Generated at Different Thresholds:")
    for thresh in thresholds:
        buy_count = (signals_df['signal'] > thresh).sum()
        sell_count = (signals_df['signal'] < -thresh).sum()
        total = buy_count + sell_count
        print(f"  ±{thresh:.2f}: {total} signals ({buy_count}B / {sell_count}S)")

    print("\n" + "="*70)
    print("DIAGNOSIS")
    print("="*70 + "\n")

    max_abs_signal = signals_df['signal'].abs().max()

    if max_abs_signal < SIGNAL_THRESHOLD:
        print(f"❌ CRITICAL ISSUE: Signal Never Reaches Threshold!")
        print(f"   Strongest signal: ±{max_abs_signal:.4f}")
        print(f"   Current threshold: ±{SIGNAL_THRESHOLD}")
        print(f"   Gap: {(SIGNAL_THRESHOLD - max_abs_signal):.4f}\n")

        print("POSSIBLE CAUSES:")
        print("  1. Signal threshold too high (0.04 may be too strict)")
        print("  2. Strategy weights producing weak signals")
        print("  3. Market conditions don't match strategy criteria")
        print("  4. Multiple strategies disagreeing (canceling each other out)\n")

        print("RECOMMENDATIONS:")
        print(f"  1. Reduce signal threshold from 0.04 to 0.02 (would generate {(signals_df['signal'].abs() > 0.02).sum()} signals)")
        print("  2. Review strategy weight allocation")
        print("  3. Check if strategies are properly calibrated")

    elif buy_signals == 0 and sell_signals == 0:
        print(f"⚠️ WARNING: Signals generated but none in last 100 candles")
        print(f"   May need to wait for better market conditions")

    else:
        print(f"✅ Signal system working correctly")
        print(f"   Generated {buy_signals + sell_signals} signals in last 100 candles")

    print()

if __name__ == "__main__":
    main()
