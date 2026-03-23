# ============================================================
#  risk_manager.py — Position Sizing & Circuit Breakers
# ============================================================
import time
import logging
from dataclasses import dataclass, field
from typing import Optional
from config import (RISK_PER_TRADE, STOP_LOSS_PCT, TAKE_PROFIT_PCT,
                    TRAILING_STOP_PCT, MAX_OPEN_TRADES,
                    MAX_DAILY_LOSS_PCT, MAX_DAILY_TRADES)

log = logging.getLogger("RiskManager")


@dataclass
class Position:
    symbol: str
    side: str            # "BUY" or "SELL"
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    trailing_stop: float
    order_id: str
    timestamp: float = field(default_factory=time.time)
    highest_price: float = 0.0   # for trailing stop (long)
    lowest_price: float  = 0.0   # for trailing stop (short)
    pnl: float = 0.0

    # NEW: Futures-specific fields
    is_futures: bool = False
    leverage: int = 1
    liquidation_price: float = 0.0
    initial_margin: float = 0.0

    def update_trailing(self, current_price: float):
        """Adjust trailing stop as price moves in our favour."""
        if self.side == "BUY":
            if current_price > self.highest_price:
                self.highest_price = current_price
                new_stop = current_price * (1 - TRAILING_STOP_PCT)
                self.trailing_stop = max(self.trailing_stop, new_stop)
        else:  # SELL
            if current_price < self.lowest_price:
                self.lowest_price = current_price
                new_stop = current_price * (1 + TRAILING_STOP_PCT)
                self.trailing_stop = min(self.trailing_stop, new_stop)

    def should_stop_loss(self, price: float) -> bool:
        if self.side == "BUY":
            return price <= max(self.stop_loss, self.trailing_stop)
        return price >= min(self.stop_loss, self.trailing_stop)

    def should_take_profit(self, price: float) -> bool:
        if self.side == "BUY":
            return price >= self.take_profit
        return price <= self.take_profit

    def unrealised_pnl(self, price: float) -> float:
        if self.side == "BUY":
            return (price - self.entry_price) * self.quantity
        return (self.entry_price - price) * self.quantity

    def unrealised_pct(self, price: float) -> float:
        return self.unrealised_pnl(price) / (self.entry_price * self.quantity) * 100


class RiskManager:
    def __init__(self, starting_capital: float):
        self.capital         = starting_capital
        self.daily_pnl       = 0.0
        self.daily_trades    = 0
        self.open_positions: dict[str, Position] = {}
        self._day_start      = time.time()
        self.paused          = False
        self.pause_reason    = ""
        self.total_pnl       = 0.0
        self.win_count       = 0
        self.loss_count      = 0

    # ── Daily reset ──────────────────────────────────────────
    def _maybe_reset_day(self):
        now = time.time()
        if now - self._day_start > 86_400:   # 24 hours
            log.info(f"New day — resetting daily counters. Day PnL: {self.daily_pnl:.2f}")
            self.daily_pnl    = 0.0
            self.daily_trades = 0
            self._day_start   = now
            self.paused       = False

    # ── Can we open a new trade? ──────────────────────────────
    def can_trade(self) -> tuple[bool, str]:
        self._maybe_reset_day()

        if self.paused:
            return False, f"Bot paused: {self.pause_reason}"

        if len(self.open_positions) >= MAX_OPEN_TRADES:
            return False, f"Max open trades reached ({MAX_OPEN_TRADES})"

        if self.daily_trades >= MAX_DAILY_TRADES:
            self.paused      = True
            self.pause_reason = f"Daily trade limit ({MAX_DAILY_TRADES}) reached"
            return False, self.pause_reason

        loss_limit = self.capital * MAX_DAILY_LOSS_PCT
        if self.daily_pnl < -loss_limit:
            self.paused       = True
            self.pause_reason = f"Daily loss limit hit ({self.daily_pnl:.2f})"
            return False, self.pause_reason

        return True, "OK"

    # ── Position sizing ───────────────────────────────────────
    def calculate_quantity(self, price: float,
                           signal_strength: float,
                           min_qty: float = 0.001) -> float:
        """
        Kelly-inspired sizing:
        risk_amount = capital * RISK_PER_TRADE * |signal_strength|
        quantity    = risk_amount / (entry_price * stop_loss_pct)
        """
        risk_amount = self.capital * RISK_PER_TRADE * abs(signal_strength)
        quantity    = risk_amount / (price * STOP_LOSS_PCT)
        quantity    = max(round(quantity, 3), min_qty)
        log.debug(f"Sizing: capital={self.capital:.2f}, risk={risk_amount:.2f}, "
                  f"qty={quantity}")
        return quantity

    def calculate_futures_quantity(self, price: float, signal_strength: float,
                                   leverage: int, min_qty: float = 0.001) -> tuple[float, float]:
        """
        Calculate position size for futures with leverage.
        Returns: (quantity, initial_margin_required)
        """
        # Use same Kelly-inspired sizing
        risk_amount = self.capital * RISK_PER_TRADE * abs(signal_strength)
        quantity = risk_amount / (price * STOP_LOSS_PCT)
        quantity = max(round(quantity, 3), min_qty)

        # Calculate margin requirement
        position_value = quantity * price
        initial_margin = position_value / leverage

        # Don't use more than 30% of capital per trade
        if initial_margin > self.capital * 0.3:
            quantity = (self.capital * 0.3 * leverage) / price
            initial_margin = self.capital * 0.3
            log.warning("Position size reduced: margin would exceed 30%")

        return quantity, initial_margin

    def check_liquidation_risk(self, position: Position, current_price: float) -> tuple[bool, str]:
        """Check if position approaching liquidation."""
        if not position.is_futures:
            return False, "OK"

        from config import LIQUIDATION_BUFFER_PCT

        liq_price = position.liquidation_price
        if liq_price == 0:
            return False, "No liquidation price"

        if position.side == "BUY":
            distance_pct = (current_price - liq_price) / current_price
        else:
            distance_pct = (liq_price - current_price) / current_price

        if distance_pct < LIQUIDATION_BUFFER_PCT:
            return True, f"Price {distance_pct*100:.1f}% from liquidation"

        return False, "OK"

    # ── Build Position object ─────────────────────────────────
    def create_position(self, symbol: str, side: str,
                        entry_price: float, quantity: float,
                        order_id: str, is_futures: bool = False,
                        leverage: int = 1, liquidation_price: float = 0.0) -> Position:
        """Create position with proper SL/TP. For futures, ensure SL before liquidation."""

        if side == "BUY":
            stop_loss    = entry_price * (1 - STOP_LOSS_PCT)
            take_profit  = entry_price * (1 + TAKE_PROFIT_PCT)
            trailing_stp = entry_price * (1 - TRAILING_STOP_PCT)

            # CRITICAL: Ensure stop-loss is ABOVE liquidation for LONG
            if is_futures and liquidation_price > 0:
                min_sl = liquidation_price * 1.05  # 5% buffer
                if stop_loss < min_sl:
                    stop_loss = min_sl
                    log.warning(f"Adjusted SL to {stop_loss:.2f} (liq={liquidation_price:.2f})")
        else:
            stop_loss    = entry_price * (1 + STOP_LOSS_PCT)
            take_profit  = entry_price * (1 - TAKE_PROFIT_PCT)
            trailing_stp = entry_price * (1 + TRAILING_STOP_PCT)

            # CRITICAL: Ensure stop-loss is BELOW liquidation for SHORT
            if is_futures and liquidation_price > 0:
                max_sl = liquidation_price * 0.95
                if stop_loss > max_sl:
                    stop_loss = max_sl
                    log.warning(f"Adjusted SL to {stop_loss:.2f} (liq={liquidation_price:.2f})")

        pos = Position(
            symbol=symbol, side=side,
            entry_price=entry_price, quantity=quantity,
            stop_loss=stop_loss, take_profit=take_profit,
            trailing_stop=trailing_stp, order_id=order_id,
            highest_price=entry_price, lowest_price=entry_price,
            is_futures=is_futures, leverage=leverage,
            liquidation_price=liquidation_price,
        )
        self.open_positions[order_id] = pos
        self.daily_trades += 1
        return pos

    # ── Close position & update stats ────────────────────────
    def close_position(self, order_id: str, exit_price: float,
                       reason: str = "signal"):
        pos = self.open_positions.pop(order_id, None)
        if pos is None:
            return None

        pnl = pos.unrealised_pnl(exit_price)
        pos.pnl          = pnl
        self.daily_pnl  += pnl
        self.total_pnl  += pnl
        self.capital    += pnl

        if pnl >= 0:
            self.win_count  += 1
        else:
            self.loss_count += 1

        log.info(f"[CLOSE] {pos.side} {pos.symbol} | "
                 f"Entry={pos.entry_price:.4f} Exit={exit_price:.4f} | "
                 f"PnL={pnl:+.4f} | Reason={reason}")
        return pos

    # ── Stats ─────────────────────────────────────────────────
    @property
    def win_rate(self) -> float:
        total = self.win_count + self.loss_count
        return self.win_count / total * 100 if total else 0.0

    @property
    def profit_factor(self) -> float:
        return self.total_pnl / max(abs(self.daily_pnl), 1e-10)

    def summary(self) -> dict:
        return {
            "capital":      round(self.capital, 2),
            "total_pnl":    round(self.total_pnl, 4),
            "daily_pnl":    round(self.daily_pnl, 4),
            "daily_trades": self.daily_trades,
            "open":         len(self.open_positions),
            "win_rate":     round(self.win_rate, 1),
            "wins":         self.win_count,
            "losses":       self.loss_count,
            "paused":       self.paused,
        }
