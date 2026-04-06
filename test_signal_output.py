#!/usr/bin/env python3
"""Quick test to see what SignalAggregator actually returns"""

from binance_client import BinanceClient
from indicators import enrich_dataframe
from strategies_pro import SignalAggregatorPro as SignalAggregator
from config import SYMBOL, INTERVAL, STRATEGY_WEIGHTS

client = BinanceClient()
aggregator = SignalAggregator()

# Get recent data
df = client.get_klines(SYMBOL, INTERVAL, limit=200)
df = enrich_dataframe(df)

# Compute signal
signal_data = aggregator.compute(df, {}, STRATEGY_WEIGHTS)

print("\n" + "="*70)
print("SIGNAL DATA OUTPUT")
print("="*70)
print(f"\nFull output: {signal_data}")
print(f"\nKeys: {signal_data.keys()}")
print(f"\nCombined: {signal_data.get('combined', 'NOT FOUND')}")
print(f"\nScores: {signal_data.get('scores', {})}")
print(f"\nFilters: {signal_data.get('filters', {})}")

# Check last row
print(f"\n" + "="*70)
print("LAST ROW INDICATORS")
print("="*70)
row = df.iloc[-1]
print(f"ATR%: {row.get('atr_pct', 0):.4f}")
print(f"ADX: {row.get('adx', 0):.2f}")
print(f"BB Bandwidth: {row.get('bb_bandwidth', 0):.6f}")
print(f"Volume Ratio: {row.get('vol_ratio', 0):.2f}")
print(f"Williams %R: {row.get('williams_r', 0):.2f}")
print(f"RSI: {row.get('rsi', 0):.2f}")
print(f"EMA 8: {row.get('ema_8', 0):.2f}")
print(f"EMA 21: {row.get('ema_21', 0):.2f}")
print()
