# ============================================================
#  trade_logger.py — CSV + Console Trade Journal
# ============================================================
import csv
import os
import logging
import time
from datetime import datetime
from config import LOG_FILE

log = logging.getLogger("TradeLogger")

HEADERS = [
    "timestamp", "symbol", "side", "entry_price", "exit_price",
    "quantity", "pnl", "pnl_pct", "reason",
    "rsi_ema_score", "bollinger_score", "orderbook_score", "ml_score",
    "combined_score", "duration_sec",
]


class TradeLogger:
    def __init__(self, filepath: str = LOG_FILE):
        self.filepath = filepath
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        self._init_file()

    def _init_file(self):
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=HEADERS)
                writer.writeheader()
            log.info(f"Trade log created: {self.filepath}")

    def log_trade(self, position, exit_price: float,
                  reason: str, signal_breakdown: dict):
        duration = time.time() - position.timestamp
        entry    = position.entry_price
        if entry == 0:
            pnl_pct = 0.0
        else:
            pnl_pct  = (exit_price - entry) / entry * 100
            if position.side == "SELL":
                pnl_pct = -pnl_pct

        # Use ENTRY signal, not exit signal for accurate logging
        entry_signal = position.entry_signal if position.entry_signal else signal_breakdown
        scores = entry_signal.get("scores", {})

        row = {
            "timestamp":      datetime.utcnow().isoformat(),
            "symbol":         position.symbol,
            "side":           position.side,
            "entry_price":    round(entry, 4),
            "exit_price":     round(exit_price, 4),
            "quantity":       position.quantity,
            "pnl":            round(position.pnl, 4),
            "pnl_pct":        round(pnl_pct, 4),
            "reason":         reason,
            "rsi_ema_score":  scores.get("rsi_ema", 0),
            "bollinger_score":scores.get("bollinger", 0),
            "orderbook_score":scores.get("orderbook", 0),
            "ml_score":       scores.get("ml_signal", 0),
            "combined_score": round(entry_signal.get("combined", 0), 4),
            "duration_sec":   round(duration, 1),
        }

        with open(self.filepath, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writerow(row)

        emoji = "✅" if position.pnl >= 0 else "❌"
        log.info(f"{emoji} TRADE CLOSED | {position.side} {position.symbol} | "
                 f"PnL={position.pnl:+.4f} ({pnl_pct:+.2f}%) | "
                 f"Reason={reason} | Duration={duration:.0f}s")

    def load_history(self) -> list[dict]:
        trades = []
        try:
            with open(self.filepath, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    trades.append(row)
        except FileNotFoundError:
            pass
        return trades

    def performance_summary(self) -> dict:
        trades = self.load_history()
        if not trades:
            return {}

        pnls     = [float(t["pnl"])     for t in trades]
        pnl_pcts = [float(t["pnl_pct"]) for t in trades]
        wins     = [p for p in pnls if p > 0]
        losses   = [p for p in pnls if p <= 0]

        # Calculate profit factor (JSON-safe, no infinity)
        if losses and sum(losses) != 0:
            profit_factor = round(sum(wins) / abs(sum(losses)), 2)
        else:
            profit_factor = 999.99  # Use large number instead of infinity for JSON compatibility

        return {
            "total_trades":   len(trades),
            "wins":          len(wins),
            "losses":        len(losses),
            "win_rate":       round(len(wins) / len(trades) * 100, 1),
            "total_pnl":      round(sum(pnls), 4),
            "avg_win":        round(sum(wins) / len(wins), 4)    if wins   else 0,
            "avg_loss":       round(sum(losses) / len(losses), 4) if losses else 0,
            "profit_factor":  profit_factor,
            "best_trade":     round(max(pnls), 4),
            "worst_trade":    round(min(pnls), 4),
            "avg_pnl_pct":    round(sum(pnl_pcts) / len(pnl_pcts), 4),
        }
