#!/usr/bin/env python3
"""
Validate the candle filter fix by comparing before/after performance
"""

import sys
import importlib

# Temporarily modify config for testing
import config

print("\n" + "="*70)
print("🔄 VALIDATING CANDLE FILTER FIX")
print("="*70 + "\n")

print("OLD Settings:")
print(f"  MIN_CANDLE_BODY_PCT: 0.33%")
print(f"  USE_DYNAMIC_CANDLE_FILTER: False")
print(f"  Result: 97% signals filtered, -0.17% P&L, missed +11.69%\n")

print("NEW Settings:")
print(f"  MIN_CANDLE_BODY_PCT: {config.MIN_CANDLE_BODY_PCT*100:.2f}%")
print(f"  USE_DYNAMIC_CANDLE_FILTER: {config.USE_DYNAMIC_CANDLE_FILTER}")
print(f"  CANDLE_BODY_ATR_RATIO: {config.CANDLE_BODY_ATR_RATIO}\n")

# Run backtest with new settings
print("="*70)
print("RUNNING BACKTEST WITH NEW SETTINGS...")
print("="*70 + "\n")

from analyze_recent_performance import RecentPerformanceAnalyzer

analyzer = RecentPerformanceAnalyzer()
df = analyzer.download_recent_data(hours=24)

if df is not None:
    analyzer.backtest(df)
    analyzer.analyze_results()

    # Calculate improvement
    if analyzer.trades:
        wins = [t for t in analyzer.trades if t['pnl_pct'] > 0]
        win_rate = len(wins) / len(analyzer.trades) * 100
        total_pnl = sum(t['pnl_pct'] for t in analyzer.trades)

        print("\n" + "="*70)
        print("📊 BEFORE vs AFTER COMPARISON")
        print("="*70 + "\n")

        print("BEFORE (Candle 0.33%):")
        print("  Trades: 3")
        print("  Win Rate: 33.3%")
        print("  Total P&L: -0.17%")
        print("  Signals Filtered: 97.1%\n")

        print("AFTER (Dynamic Candle Filter):")
        print(f"  Trades: {len(analyzer.trades)}")
        print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Total P&L: {total_pnl:+.2f}%")

        filtered_pct = (len(analyzer.filtered_signals) / (len(analyzer.trades) + len(analyzer.filtered_signals)) * 100) if (len(analyzer.trades) + len(analyzer.filtered_signals)) > 0 else 0
        print(f"  Signals Filtered: {filtered_pct:.1f}%\n")

        print("IMPROVEMENT:")
        print(f"  Trades: {len(analyzer.trades) - 3:+d} ({(len(analyzer.trades)/3-1)*100:+.0f}%)")
        print(f"  Win Rate: {win_rate - 33.3:+.1f}%")
        print(f"  Total P&L: {total_pnl - (-0.17):+.2f}%")
        print(f"  Filter Rate: {filtered_pct - 97.1:+.1f}%\n")

        if total_pnl > 0:
            print("✅ FIX SUCCESSFUL - Bot is now profitable!\n")
        elif total_pnl > -0.17:
            print("✅ FIX IMPROVED PERFORMANCE - Better than before\n")
        else:
            print("⚠️ Further tuning may be needed\n")
    else:
        print("\n⚠️ No trades executed - filter may still be too strict\n")
else:
    print("❌ Failed to download data\n")
