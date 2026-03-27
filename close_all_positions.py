#!/usr/bin/env python3
"""
Emergency script to close ALL open futures positions on Binance testnet.
Use this to clean up orphaned positions.
"""

import sys
sys.path.insert(0, '.')

from binance_client import BinanceClient
from config import SYMBOL

def main():
    print("=" * 60)
    print("  CLOSING ALL OPEN FUTURES POSITIONS")
    print("=" * 60)
    print()

    client = BinanceClient()

    # Get all open positions
    try:
        positions = client.client.futures_position_information(symbol=SYMBOL)
    except Exception as e:
        print(f"❌ Error getting positions: {e}")
        return

    # Filter for actual open positions (non-zero quantity)
    open_positions = [p for p in positions if float(p['positionAmt']) != 0]

    if not open_positions:
        print("✅ No open positions found")
        return

    print(f"Found {len(open_positions)} open position(s):\n")

    for pos in open_positions:
        amt = float(pos['positionAmt'])
        side = "LONG" if amt > 0 else "SHORT"
        entry = float(pos['entryPrice'])
        unrealized = float(pos['unRealizedProfit'])

        print(f"  {side} | Qty: {abs(amt)} | Entry: ${entry:.2f} | uPnL: ${unrealized:+.2f}")

    print()
    response = input("⚠️  Close ALL these positions? (yes/no): ")

    if response.lower() != 'yes':
        print("❌ Cancelled")
        return

    print()
    print("Closing positions...")

    for pos in open_positions:
        amt = float(pos['positionAmt'])
        if amt == 0:
            continue

        # Determine close side (opposite of position)
        close_side = "SELL" if amt > 0 else "BUY"
        quantity = abs(amt)

        print(f"  Closing {close_side} {quantity} {SYMBOL}...")

        try:
            order = client.place_futures_market_order(SYMBOL, close_side, quantity)
            if order:
                print(f"    ✅ Closed (Order ID: {order['orderId']})")
            else:
                print(f"    ❌ Failed to close")
        except Exception as e:
            print(f"    ❌ Error: {e}")

    print()
    print("=" * 60)
    print("✅ Done")
    print("=" * 60)

if __name__ == "__main__":
    main()
