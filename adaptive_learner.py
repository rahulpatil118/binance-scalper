# ============================================================
#  adaptive_learner.py — Self-Learning Trading AI
#  Learns from every trade and optimizes parameters automatically
# ============================================================
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from pathlib import Path
import numpy as np

log = logging.getLogger("AdaptiveLearner")


class AdaptiveLearner:
    """
    Self-learning system that:
    1. Analyzes trade outcomes
    2. Identifies winning patterns
    3. Adjusts parameters automatically
    4. Improves performance over time
    """

    def __init__(self, memory_file: str = "logs/trade_memory.json"):
        self.memory_file = Path(memory_file)
        self.trade_memory: List[Dict] = []
        self.load_memory()

        # Learning parameters
        self.target_win_rate = 0.55  # Target 55% win rate
        self.learning_window = 20     # Analyze last 20 trades
        self.min_trades_to_learn = 5  # Need 5 trades minimum

        # Current optimized parameters (start with defaults)
        self.optimized_params = {
            "signal_threshold": 0.04,
            "min_candle_body": 0.002,
            "min_adx": 15,
            "stop_loss_pct": 0.010,
        }

        log.info("🧠 Adaptive Learning System initialized")

    def load_memory(self):
        """Load trade history from disk"""
        if self.memory_file.exists():
            try:
                with open(self.memory_file, 'r') as f:
                    self.trade_memory = json.load(f)
                log.info(f"📚 Loaded {len(self.trade_memory)} trades from memory")
            except Exception as e:
                log.error(f"Failed to load memory: {e}")
                self.trade_memory = []
        else:
            self.trade_memory = []

    def save_memory(self):
        """Save trade history to disk"""
        try:
            self.memory_file.parent.mkdir(parents=True, exist_ok=True)

            # Convert numpy types to native Python types for JSON serialization
            def convert_numpy(obj):
                if isinstance(obj, np.bool_):
                    return bool(obj)
                elif isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, dict):
                    return {k: convert_numpy(v) for k, v in obj.items()}
                elif isinstance(obj, (list, tuple)):
                    return [convert_numpy(item) for item in obj]
                return obj

            # Convert all trades
            clean_memory = convert_numpy(self.trade_memory)

            with open(self.memory_file, 'w') as f:
                json.dump(clean_memory, f, indent=2)
        except Exception as e:
            log.error(f"Failed to save memory: {e}")

    def record_trade(self, trade_data: Dict):
        """
        Record a trade with full context for learning

        Args:
            trade_data: {
                'timestamp': str,
                'side': str,
                'entry_price': float,
                'exit_price': float,
                'pnl': float,
                'pnl_pct': float,
                'duration_sec': int,
                'reason': str,
                'indicators': dict,  # All technical indicators at entry
                'signal_strength': float,
                'market_conditions': dict
            }
        """
        # Add trade ID and win/loss classification
        trade_data['trade_id'] = len(self.trade_memory) + 1
        trade_data['win'] = trade_data['pnl'] > 0

        # Add to memory
        self.trade_memory.append(trade_data)
        self.save_memory()

        log.info(f"📝 Trade #{trade_data['trade_id']} recorded: "
                f"{'WIN' if trade_data['win'] else 'LOSS'} "
                f"${trade_data['pnl']:.2f}")

        # Learn from this trade
        if len(self.trade_memory) >= self.min_trades_to_learn:
            self.learn_and_adapt()

    def learn_and_adapt(self):
        """Main learning loop - analyze recent trades and optimize"""
        recent_trades = self.trade_memory[-self.learning_window:]

        if len(recent_trades) < self.min_trades_to_learn:
            return

        # Calculate current performance
        win_rate = sum(1 for t in recent_trades if t['win']) / len(recent_trades)
        avg_pnl = np.mean([t['pnl'] for t in recent_trades])

        log.info(f"📊 Learning from last {len(recent_trades)} trades: "
                f"Win Rate {win_rate*100:.1f}%, Avg P&L ${avg_pnl:.2f}")

        # Analyze patterns
        winning_patterns = self.analyze_winning_patterns()
        losing_patterns = self.analyze_losing_patterns()

        # Optimize parameters
        if win_rate < self.target_win_rate:
            self.optimize_parameters(winning_patterns, losing_patterns, win_rate)

        # Detect market regime changes
        self.detect_market_regime()

    def analyze_winning_patterns(self) -> Dict:
        """Identify characteristics of winning trades"""
        recent_trades = self.trade_memory[-self.learning_window:]
        winning_trades = [t for t in recent_trades if t['win']]

        if not winning_trades:
            return {}

        # Analyze winning trade characteristics
        patterns = {
            'avg_signal_strength': np.mean([t.get('signal_strength', 0) for t in winning_trades]),
            'avg_adx': np.mean([t['indicators'].get('adx', 0) for t in winning_trades]),
            'avg_atr': np.mean([t['indicators'].get('atr_pct', 0) for t in winning_trades]),
            'avg_candle_body': np.mean([t['indicators'].get('candle_body', 0) for t in winning_trades]),
            'avg_duration': np.mean([t['duration_sec'] for t in winning_trades]),
            'sides': {'BUY': 0, 'SELL': 0}
        }

        # Count which side wins more
        for t in winning_trades:
            patterns['sides'][t['side']] += 1

        log.info(f"✅ Winning patterns: Signal {patterns['avg_signal_strength']:.3f}, "
                f"ADX {patterns['avg_adx']:.1f}, "
                f"BUY:{patterns['sides']['BUY']} SELL:{patterns['sides']['SELL']}")

        return patterns

    def analyze_losing_patterns(self) -> Dict:
        """Identify characteristics of losing trades"""
        recent_trades = self.trade_memory[-self.learning_window:]
        losing_trades = [t for t in recent_trades if not t['win']]

        if not losing_trades:
            return {}

        patterns = {
            'avg_signal_strength': np.mean([t.get('signal_strength', 0) for t in losing_trades]),
            'avg_adx': np.mean([t['indicators'].get('adx', 0) for t in losing_trades]),
            'avg_atr': np.mean([t['indicators'].get('atr_pct', 0) for t in losing_trades]),
            'common_reasons': {}
        }

        # Identify common exit reasons
        for t in losing_trades:
            reason = t['reason']
            patterns['common_reasons'][reason] = patterns['common_reasons'].get(reason, 0) + 1

        log.info(f"❌ Losing patterns: Signal {patterns['avg_signal_strength']:.3f}, "
                f"Reasons: {patterns['common_reasons']}")

        return patterns

    def optimize_parameters(self, winning_patterns: Dict, losing_patterns: Dict, current_win_rate: float):
        """
        Automatically adjust trading parameters based on learned patterns
        """
        log.info(f"🔧 Optimizing parameters (current win rate: {current_win_rate*100:.1f}%)")

        adjustments = []

        # 1. Adjust signal threshold
        if winning_patterns and losing_patterns:
            win_avg_signal = winning_patterns.get('avg_signal_strength', 0)
            loss_avg_signal = losing_patterns.get('avg_signal_strength', 0)

            # If winning trades have higher signals, raise threshold
            if win_avg_signal > loss_avg_signal * 1.2:
                new_threshold = (win_avg_signal + loss_avg_signal) / 2
                new_threshold = max(0.03, min(0.08, new_threshold))  # Keep in reasonable range

                if abs(new_threshold - self.optimized_params['signal_threshold']) > 0.005:
                    adjustments.append(f"Signal threshold: {self.optimized_params['signal_threshold']:.3f} → {new_threshold:.3f}")
                    self.optimized_params['signal_threshold'] = new_threshold

        # 2. Adjust ADX based on trend strength
        if winning_patterns:
            win_avg_adx = winning_patterns.get('avg_adx', 15)

            # If winners have higher ADX, require stronger trends
            if win_avg_adx > 20:
                new_adx = min(win_avg_adx * 0.9, 22)  # Slightly below winning average
                if abs(new_adx - self.optimized_params['min_adx']) > 2:
                    adjustments.append(f"Min ADX: {self.optimized_params['min_adx']:.0f} → {new_adx:.0f}")
                    self.optimized_params['min_adx'] = new_adx

        # 3. Adjust candle body requirement
        if winning_patterns and losing_patterns:
            win_candle = winning_patterns.get('avg_candle_body', 0.002)

            # Use winning average as new minimum
            new_candle_body = max(0.001, min(0.004, win_candle * 0.8))
            if abs(new_candle_body - self.optimized_params['min_candle_body']) > 0.0005:
                adjustments.append(f"Min candle body: {self.optimized_params['min_candle_body']*100:.2f}% → {new_candle_body*100:.2f}%")
                self.optimized_params['min_candle_body'] = new_candle_body

        # 4. Adjust stop loss based on volatility
        if losing_patterns:
            loss_reasons = losing_patterns.get('common_reasons', {})
            stop_loss_count = loss_reasons.get('stop_loss', 0)
            total_losses = sum(loss_reasons.values())

            if total_losses > 0:
                stop_loss_rate = stop_loss_count / total_losses

                # If too many stop losses (>60%), widen stops
                if stop_loss_rate > 0.6:
                    new_stop = min(self.optimized_params['stop_loss_pct'] * 1.2, 0.015)
                    if abs(new_stop - self.optimized_params['stop_loss_pct']) > 0.001:
                        adjustments.append(f"Stop loss: {self.optimized_params['stop_loss_pct']*100:.1f}% → {new_stop*100:.1f}%")
                        self.optimized_params['stop_loss_pct'] = new_stop

        # Log adjustments
        if adjustments:
            log.info(f"🎯 Parameter adjustments applied:")
            for adj in adjustments:
                log.info(f"   {adj}")
        else:
            log.info(f"✓ Parameters are optimal, no changes needed")

        # Save optimized parameters
        self.save_optimized_params()

    def detect_market_regime(self):
        """Detect if market conditions have changed"""
        if len(self.trade_memory) < 10:
            return

        recent = self.trade_memory[-10:]
        older = self.trade_memory[-20:-10] if len(self.trade_memory) >= 20 else []

        if not older:
            return

        # Compare volatility
        recent_atr = np.mean([t['indicators'].get('atr_pct', 0) for t in recent])
        older_atr = np.mean([t['indicators'].get('atr_pct', 0) for t in older])

        if recent_atr > older_atr * 1.5:
            log.warning(f"⚠️ Market regime change detected: Volatility increased {(recent_atr/older_atr - 1)*100:.1f}%")
        elif recent_atr < older_atr * 0.6:
            log.info(f"ℹ️ Market regime change: Volatility decreased {(1 - recent_atr/older_atr)*100:.1f}%")

    def save_optimized_params(self):
        """Save optimized parameters to file"""
        try:
            param_file = Path("logs/optimized_params.json")
            param_file.parent.mkdir(parents=True, exist_ok=True)
            with open(param_file, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'parameters': self.optimized_params,
                    'total_trades': len(self.trade_memory)
                }, f, indent=2)
        except Exception as e:
            log.error(f"Failed to save optimized params: {e}")

    def get_optimized_params(self) -> Dict:
        """Return current optimized parameters"""
        return self.optimized_params.copy()

    def get_performance_report(self) -> Dict:
        """Generate performance report"""
        if not self.trade_memory:
            return {"message": "No trades yet"}

        recent = self.trade_memory[-self.learning_window:]

        wins = sum(1 for t in recent if t['win'])
        losses = len(recent) - wins
        win_rate = wins / len(recent) if recent else 0

        avg_win = np.mean([t['pnl'] for t in recent if t['win']]) if wins > 0 else 0
        avg_loss = np.mean([t['pnl'] for t in recent if not t['win']]) if losses > 0 else 0

        return {
            "total_trades": len(self.trade_memory),
            "recent_trades": len(recent),
            "win_rate": win_rate,
            "wins": wins,
            "losses": losses,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": abs(avg_win / avg_loss) if avg_loss != 0 else 0,
            "optimized_params": self.optimized_params
        }
