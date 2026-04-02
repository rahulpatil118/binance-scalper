# ============================================================
#  risk_manager.py — Position Sizing & Circuit Breakers
# ============================================================
import time
import logging
from dataclasses import dataclass, field
from typing import Optional
from config import (RISK_PER_TRADE, STOP_LOSS_PCT, TAKE_PROFIT_PCT,
                    TRAILING_STOP_PCT, MAX_OPEN_TRADES,
                    MAX_DAILY_LOSS_PCT, MAX_DAILY_TRADES,
                    MAX_DRAWDOWN_PCT, ENABLE_CIRCUIT_BREAKERS,
                    CONSECUTIVE_LOSS_LIMIT, LOSS_STREAK_PAUSE_LIMIT,
                    LOSS_STREAK_PAUSE_HOURS, DRAWDOWN_RISK_REDUCTION,
                    TRADE_COOLDOWN_SECONDS)

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

    # Store entry signal for accurate logging
    entry_signal: dict = field(default_factory=dict)

    # Trailing take-profit fields
    tp_trailing_active: bool = False
    highest_profit_price: float = 0.0
    lowest_profit_price: float = float('inf')
    trailing_take_profit: float = 0.0

    def update_trailing(self, current_price: float):
        """Adjust trailing stop AND trailing take-profit as price moves in our favour."""
        if self.side == "BUY":
            # Update trailing stop-loss
            if current_price > self.highest_price:
                self.highest_price = current_price
                new_stop = current_price * (1 - TRAILING_STOP_PCT)
                self.trailing_stop = max(self.trailing_stop, new_stop)

            # Activate trailing take-profit once we hit initial TP target
            if current_price >= self.take_profit and not self.tp_trailing_active:
                self.tp_trailing_active = True
                self.highest_profit_price = current_price
                log.info(f"[TRAILING TP] Activated for BUY at {current_price:.2f}")

            # Update trailing take-profit (lock in profits)
            if self.tp_trailing_active:
                if current_price > self.highest_profit_price:
                    self.highest_profit_price = current_price
                # Trail TP below the highest profit price
                self.trailing_take_profit = self.highest_profit_price * (1 - TRAILING_STOP_PCT)

        else:  # SELL
            # Update trailing stop-loss
            if current_price < self.lowest_price:
                self.lowest_price = current_price
                new_stop = current_price * (1 + TRAILING_STOP_PCT)
                self.trailing_stop = min(self.trailing_stop, new_stop)

            # Activate trailing take-profit once we hit initial TP target
            if current_price <= self.take_profit and not self.tp_trailing_active:
                self.tp_trailing_active = True
                self.lowest_profit_price = current_price
                log.info(f"[TRAILING TP] Activated for SELL at {current_price:.2f}")

            # Update trailing take-profit (lock in profits)
            if self.tp_trailing_active:
                if current_price < self.lowest_profit_price:
                    self.lowest_profit_price = current_price
                # Trail TP above the lowest profit price
                self.trailing_take_profit = self.lowest_profit_price * (1 + TRAILING_STOP_PCT)

    def should_stop_loss(self, price: float) -> bool:
        if self.side == "BUY":
            return price <= max(self.stop_loss, self.trailing_stop)
        return price >= min(self.stop_loss, self.trailing_stop)

    def should_take_profit(self, price: float) -> bool:
        """
        Check if we should exit for take-profit.
        Uses trailing TP once activated (price went past initial TP and then reversed).
        """
        if self.side == "BUY":
            if self.tp_trailing_active:
                # In trailing mode: exit if price drops to trailing TP level
                return price <= self.trailing_take_profit
            else:
                # Not trailing yet: just check if we hit initial target
                # (Note: update_trailing() will activate trailing, we won't exit immediately)
                return False  # Never exit on first touch, let it trail
        else:  # SELL
            if self.tp_trailing_active:
                # In trailing mode: exit if price rises to trailing TP level
                return price >= self.trailing_take_profit
            else:
                # Not trailing yet
                return False  # Never exit on first touch, let it trail

    def unrealised_pnl(self, price: float) -> float:
        if self.side == "BUY":
            return (price - self.entry_price) * self.quantity
        return (self.entry_price - price) * self.quantity

    def unrealised_pct(self, price: float) -> float:
        if self.entry_price == 0 or self.quantity == 0:
            return 0.0
        return self.unrealised_pnl(price) / (self.entry_price * self.quantity) * 100


class RiskManager:
    def __init__(self, starting_capital: float):
        self.capital         = starting_capital
        self.starting_capital = starting_capital  # Track initial capital for drawdown
        self.peak_capital    = starting_capital   # Track highest capital reached
        self.daily_pnl       = 0.0
        self.daily_trades    = 0
        self.open_positions: dict[str, Position] = {}
        self._day_start      = time.time()
        self.paused          = False
        self.pause_reason    = ""
        self.total_pnl       = 0.0
        self.win_count       = 0
        self.loss_count      = 0

        # Circuit Breaker tracking
        self.consecutive_losses = 0
        self.pause_until_time = 0  # Timestamp when pause expires
        self.risk_reduction_active = False

        # Trade cooldown tracking (prevent rapid re-entry)
        self.last_exit_time = {"BUY": 0, "SELL": 0}  # Track last exit time per side
        self.trade_cooldown_seconds = TRADE_COOLDOWN_SECONDS  # Cooldown after closing

    # ── Daily reset ──────────────────────────────────────────
    def _maybe_reset_day(self):
        now = time.time()
        if now - self._day_start > 86_400:   # 24 hours
            log.info(f"New day — resetting daily counters. Day PnL: {self.daily_pnl:.2f}")
            self.daily_pnl    = 0.0
            self.daily_trades = 0
            self._day_start   = now
            self.paused       = False

    # ── Circuit Breaker Checks ──────────────────────────────────
    def check_circuit_breakers(self) -> tuple[bool, str]:
        """Check if circuit breakers should halt trading."""
        if not ENABLE_CIRCUIT_BREAKERS:
            return True, "OK"

        # Check if we're in a timed pause
        if self.pause_until_time > 0:
            now = time.time()
            if now < self.pause_until_time:
                remaining = (self.pause_until_time - now) / 3600  # hours
                return False, f"Paused for {remaining:.1f} more hours (loss streak protection)"
            else:
                # Pause expired, clear it
                self.pause_until_time = 0
                self.consecutive_losses = 0
                self.risk_reduction_active = False
                log.info("🟢 Loss streak pause expired - resuming trading")

        # Check drawdown limit
        current_drawdown = (self.peak_capital - self.capital) / self.peak_capital
        if current_drawdown >= MAX_DRAWDOWN_PCT:
            return False, f"Max drawdown reached ({current_drawdown*100:.1f}% >= {MAX_DRAWDOWN_PCT*100:.0f}%)"

        return True, "OK"

    # ── Can we open a new trade? ──────────────────────────────
    def can_trade(self, new_side: str = None) -> tuple[bool, str]:
        """
        Check if we can open a new trade.
        Args:
            new_side: Optional side ("BUY" or "SELL") to check for same-direction positions
        """
        self._maybe_reset_day()

        # Check circuit breakers first
        can_trade_cb, reason_cb = self.check_circuit_breakers()
        if not can_trade_cb:
            self.paused = True
            self.pause_reason = reason_cb
            return False, reason_cb

        if self.paused:
            return False, f"Bot paused: {self.pause_reason}"

        # Check trade cooldown (prevent rapid re-entry after closing)
        if new_side:
            now = time.time()
            last_exit = self.last_exit_time.get(new_side, 0)
            cooldown_remaining = self.trade_cooldown_seconds - (now - last_exit)

            if cooldown_remaining > 0:
                return False, f"Trade cooldown: {int(cooldown_remaining)}s remaining for {new_side}"

        if len(self.open_positions) >= MAX_OPEN_TRADES:
            return False, f"Max open trades reached ({MAX_OPEN_TRADES})"

        # SMART POSITION LOGIC: Prevent duplicate same-direction positions, allow hedging
        # This ensures we only open new positions with different signals/directions
        if new_side:
            for pos in self.open_positions.values():
                if pos.side == new_side:
                    return False, f"Already have {new_side} position open (preventing duplicate). Close existing or wait for opposite signal to hedge."

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

        Apply risk reduction if circuit breaker is active.
        """
        risk_per_trade = RISK_PER_TRADE

        # Apply risk reduction if consecutive losses detected
        if self.risk_reduction_active:
            risk_per_trade *= DRAWDOWN_RISK_REDUCTION
            log.info(f"📉 Risk reduced to {risk_per_trade*100:.1f}% due to consecutive losses")

        risk_amount = self.capital * risk_per_trade * abs(signal_strength)
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

        Apply risk reduction if circuit breaker is active.
        """
        risk_per_trade = RISK_PER_TRADE

        # Apply risk reduction if consecutive losses detected
        if self.risk_reduction_active:
            risk_per_trade *= DRAWDOWN_RISK_REDUCTION
            log.info(f"📉 Risk reduced to {risk_per_trade*100:.1f}% due to consecutive losses")

        # Use same Kelly-inspired sizing
        risk_amount = self.capital * risk_per_trade * abs(signal_strength)
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
                        leverage: int = 1, liquidation_price: float = 0.0,
                        entry_signal: dict = None, atr: float = 0.0) -> Position:
        """
        Create position with proper SL/TP. For futures, ensure SL before liquidation.

        If USE_ATR_EXITS is enabled and ATR is provided, use ATR-based exits for better R:R.
        """
        from config import USE_ATR_EXITS, ATR_SL_MULTIPLIER, ATR_TP_MULTIPLIER

        # Determine if we should use ATR-based exits
        use_atr = USE_ATR_EXITS and atr > 0

        if side == "BUY":
            if use_atr:
                # ATR-based exits: SL = entry - (ATR × multiplier)
                stop_loss    = entry_price - (atr * ATR_SL_MULTIPLIER)
                take_profit  = entry_price + (atr * ATR_TP_MULTIPLIER)
                trailing_stp = entry_price - (atr * ATR_SL_MULTIPLIER * 0.5)
                log.debug(f"ATR-based exits: SL={stop_loss:.2f} TP={take_profit:.2f} (R:R = 1:{ATR_TP_MULTIPLIER/ATR_SL_MULTIPLIER:.1f})")
            else:
                # Fixed percentage exits
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
            if use_atr:
                # ATR-based exits: SL = entry + (ATR × multiplier)
                stop_loss    = entry_price + (atr * ATR_SL_MULTIPLIER)
                take_profit  = entry_price - (atr * ATR_TP_MULTIPLIER)
                trailing_stp = entry_price + (atr * ATR_SL_MULTIPLIER * 0.5)
                log.debug(f"ATR-based exits: SL={stop_loss:.2f} TP={take_profit:.2f} (R:R = 1:{ATR_TP_MULTIPLIER/ATR_SL_MULTIPLIER:.1f})")
            else:
                # Fixed percentage exits
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
            entry_signal=entry_signal or {},
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

        # Update peak capital for drawdown tracking
        if self.capital > self.peak_capital:
            self.peak_capital = self.capital

        # Record exit time for cooldown tracking
        self.last_exit_time[pos.side] = time.time()
        log.debug(f"🕐 Cooldown activated for {pos.side}: {self.trade_cooldown_seconds}s")

        if pnl >= 0:
            self.win_count  += 1
            # Reset consecutive losses on a win
            self.consecutive_losses = 0
            self.risk_reduction_active = False
        else:
            self.loss_count += 1

            # Circuit Breaker: Track consecutive losses
            if ENABLE_CIRCUIT_BREAKERS:
                self.consecutive_losses += 1

                # Trigger risk reduction after consecutive loss limit
                if self.consecutive_losses >= CONSECUTIVE_LOSS_LIMIT:
                    self.risk_reduction_active = True
                    log.warning(f"⚠️ {self.consecutive_losses} consecutive losses - "
                              f"reducing position size by {DRAWDOWN_RISK_REDUCTION*100:.0f}%")

                # Trigger pause after loss streak limit
                if self.consecutive_losses >= LOSS_STREAK_PAUSE_LIMIT:
                    self.pause_until_time = time.time() + (LOSS_STREAK_PAUSE_HOURS * 3600)
                    self.paused = True
                    self.pause_reason = f"{self.consecutive_losses} consecutive losses - pausing for {LOSS_STREAK_PAUSE_HOURS}h"
                    log.error(f"🛑 CIRCUIT BREAKER: {self.pause_reason}")

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
