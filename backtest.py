# ============================================================
#  backtest.py — Strategy Backtester (offline, no API needed)
# ============================================================
"""
Usage:
  python backtest.py --symbol BTCUSDT --interval 1m --days 7

Runs the full strategy stack on historical data and prints
a detailed P&L report.
"""
import argparse
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ── Minimal config fallback (run without .env) ────────────────
try:
    from config import (SIGNAL_THRESHOLD, STRATEGY_WEIGHTS,
                        STOP_LOSS_PCT, TAKE_PROFIT_PCT,
                        RISK_PER_TRADE, TRAILING_STOP_PCT)
except ImportError:
    SIGNAL_THRESHOLD = 0.55
    STRATEGY_WEIGHTS = {"rsi_ema":0.30,"bollinger":0.25,
                        "orderbook":0.25,"ml_signal":0.20}
    STOP_LOSS_PCT    = 0.005
    TAKE_PROFIT_PCT  = 0.010
    RISK_PER_TRADE   = 0.01
    TRAILING_STOP_PCT= 0.003

from indicators import enrich_dataframe
from strategies import SignalAggregator


def fetch_historical(symbol: str, interval: str,
                     days: int) -> pd.DataFrame:
    """Fetch OHLCV via python-binance (no API key needed for public data)."""
    from binance.client import Client
    client = Client("", "")
    ms_per_day = 86_400_000
    end_ts   = int(datetime.utcnow().timestamp() * 1000)
    start_ts = end_ts - days * ms_per_day

    raw = client.get_historical_klines(
        symbol, interval,
        start_str=str(start_ts),
        end_str=str(end_ts))

    df = pd.DataFrame(raw, columns=[
        "open_time","open","high","low","close","volume",
        "close_time","quote_vol","trades",
        "taker_base","taker_quote","ignore"])
    for col in ["open","high","low","close","volume"]:
        df[col] = df[col].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df.set_index("open_time", inplace=True)
    return df[["open","high","low","close","volume"]]


def run_backtest(df: pd.DataFrame, starting_capital: float = 10_000.0,
                 verbose: bool = True, use_futures: bool = False,
                 leverage: int = 1) -> dict:
    """
    Run backtest with optional futures mode and leverage.
    Simulates liquidation events when price hits liquidation level.
    """
    aggregator = SignalAggregator()
    df_full = enrich_dataframe(df)

    # Train ML on first 60% of data
    split  = int(len(df_full) * 0.6)
    train_df = df_full.iloc[:split]
    aggregator.ml.train(train_df)
    test_df = df_full.iloc[split:]

    capital     = starting_capital
    trades      = []
    position    = None
    warmup      = 60   # skip first N candles
    liquidations = 0   # NEW: track liquidation events

    for i in range(warmup, len(test_df)):
        window = test_df.iloc[max(0, i-100):i+1]
        price  = float(window["close"].iloc[-1])

        # Use empty order book for backtesting
        signal = aggregator.compute(window, {}, STRATEGY_WEIGHTS)
        combined = signal["combined"]

        # ── Manage open position ──────────────────────────────
        if position:
            entry  = position["entry"]
            side   = position["side"]
            qty    = position["qty"]
            liq_price = position.get("liquidation_price", 0)

            # FUTURES: Check liquidation FIRST
            if use_futures and liq_price > 0:
                liquidated = False
                if side == "BUY" and price <= liq_price:
                    liquidated = True
                elif side == "SELL" and price >= liq_price:
                    liquidated = True

                if liquidated:
                    # Full loss of margin
                    position_value = qty * entry
                    margin = position_value / leverage
                    pnl = -margin
                    capital += pnl
                    trades.append({
                        "side": side, "entry": entry, "exit": price,
                        "qty": qty, "pnl": pnl, "reason": "LIQUIDATION",
                        "bars": i - position["bar"],
                    })
                    liquidations += 1
                    position = None
                    if verbose:
                        print(f"  ⚠️  LIQUIDATED | {side} @ {price:.2f} | Loss: {pnl:.2f}")
                    continue

            # Trailing stop update
            if side == "BUY":
                position["high"] = max(position["high"], price)
                t_stop = position["high"] * (1 - TRAILING_STOP_PCT)
                position["t_stop"] = max(position.get("t_stop", 0), t_stop)
            else:
                position["low"] = min(position["low"], price)
                t_stop = position["low"] * (1 + TRAILING_STOP_PCT)
                position["t_stop"] = min(position.get("t_stop", float("inf")), t_stop)

            exit_reason = None
            if side == "BUY":
                if price <= max(position["sl"], position.get("t_stop", 0)):
                    exit_reason = "stop_loss"
                elif price >= position["tp"]:
                    exit_reason = "take_profit"
                elif combined <= -SIGNAL_THRESHOLD * 0.8:
                    exit_reason = "reversal"
            else:
                if price >= min(position["sl"], position.get("t_stop", float("inf"))):
                    exit_reason = "stop_loss"
                elif price <= position["tp"]:
                    exit_reason = "take_profit"
                elif combined >= SIGNAL_THRESHOLD * 0.8:
                    exit_reason = "reversal"

            if exit_reason:
                pnl = (price - entry) * qty if side == "BUY" \
                       else (entry - price) * qty
                capital += pnl
                trades.append({
                    "side": side, "entry": entry, "exit": price,
                    "qty": qty, "pnl": pnl, "reason": exit_reason,
                    "bars": i - position["bar"],
                })
                position = None
                if verbose and len(trades) % 10 == 0:
                    print(f"  Trade #{len(trades):3d} | PnL={pnl:+.2f} | "
                          f"Capital={capital:.2f} | Reason={exit_reason}")

        # ── Open new position ─────────────────────────────────
        if position is None:
            if combined >= SIGNAL_THRESHOLD:
                side = "BUY"
            elif combined <= -SIGNAL_THRESHOLD:
                side = "SELL"
            else:
                continue

            risk_amount = capital * RISK_PER_TRADE * abs(combined)
            qty         = round(risk_amount / (price * STOP_LOSS_PCT), 4)
            qty         = max(qty, 0.001)

            # Calculate liquidation for futures
            liq_price = 0
            if use_futures:
                maintenance_margin = 0.005  # 0.5% for BTC
                if side == "BUY":
                    liq_price = price * (1 - 1/leverage + maintenance_margin)
                else:
                    liq_price = price * (1 + 1/leverage - maintenance_margin)

            sl = price*(1-STOP_LOSS_PCT) if side=="BUY" else price*(1+STOP_LOSS_PCT)
            tp = price*(1+TAKE_PROFIT_PCT) if side=="BUY" else price*(1-TAKE_PROFIT_PCT)

            # Ensure SL before liquidation
            if use_futures and liq_price > 0:
                if side == "BUY":
                    sl = max(sl, liq_price * 1.05)
                else:
                    sl = min(sl, liq_price * 0.95)

            position = {
                "side": side, "entry": price, "sl": sl, "tp": tp,
                "qty": qty, "bar": i, "high": price, "low": price,
                "liquidation_price": liq_price,
            }

    # ── Results ───────────────────────────────────────────────
    if not trades:
        return {"error": "No trades generated — check signal threshold"}

    pnls  = [t["pnl"] for t in trades]
    wins  = [p for p in pnls if p > 0]
    losses= [p for p in pnls if p <= 0]

    # Max drawdown
    equity = [starting_capital]
    for p in pnls:
        equity.append(equity[-1] + p)
    peak = starting_capital
    mdd  = 0.0
    for e in equity:
        if e > peak:
            peak = e
        dd = (peak - e) / peak
        if dd > mdd:
            mdd = dd

    return {
        "total_trades":    len(trades),
        "win_rate":        round(len(wins)/len(trades)*100, 1),
        "total_pnl":       round(sum(pnls), 2),
        "return_pct":      round(sum(pnls)/starting_capital*100, 2),
        "avg_win":         round(np.mean(wins), 4)   if wins   else 0,
        "avg_loss":        round(np.mean(losses), 4) if losses else 0,
        "profit_factor":   round(sum(wins)/abs(sum(losses)), 2)
                           if losses and sum(losses) != 0 else float("inf"),
        "max_drawdown_pct":round(mdd*100, 2),
        "best_trade":      round(max(pnls), 4),
        "worst_trade":     round(min(pnls), 4),
        "avg_bars_held":   round(np.mean([t["bars"] for t in trades]), 1),
        "final_capital":   round(capital, 2),
        "liquidations":    liquidations,
        "liquidation_rate":round(liquidations / len(trades) * 100, 1) if trades else 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest Scalping Bot")
    parser.add_argument("--symbol",   default="BTCUSDT")
    parser.add_argument("--interval", default="1m")
    parser.add_argument("--days",     type=int, default=30)
    parser.add_argument("--capital",  type=float, default=10000.0)
    parser.add_argument("--futures",  action="store_true", help="Enable futures mode")
    parser.add_argument("--leverage", type=int, default=10, help="Leverage (1-125)")
    args = parser.parse_args()

    mode = f"FUTURES {args.leverage}x" if args.futures else "SPOT"
    print(f"\n📊 Backtesting {args.symbol} | {mode} | {args.interval} | "
          f"Last {args.days} days | Capital=${args.capital:,.0f}\n")
    print("Fetching data...", flush=True)

    try:
        df = fetch_historical(args.symbol, args.interval, args.days)
        print(f"Loaded {len(df)} candles\n")
        results = run_backtest(df, args.capital,
                              use_futures=args.futures,
                              leverage=args.leverage)

        print("\n" + "="*50)
        print(f"  BACKTEST RESULTS ({mode})")
        print("="*50)
        for k, v in results.items():
            print(f"  {k:<22} {v}")
        print("="*50 + "\n")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
