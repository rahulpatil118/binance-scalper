# 🤖 Binance Scalping Bot

Advanced cryptocurrency scalping bot for Binance Futures with multi-strategy approach, machine learning, and real-time web dashboard.

## ✨ Features

### Trading Strategies
- **RSI + EMA Crossover**: Momentum-based strategy with trend filters
- **Bollinger Bands**: Mean reversion and breakout detection
- **Order Book Imbalance**: Live liquidity analysis
- **Machine Learning**: Random Forest classifier with adaptive retraining

### Risk Management
- Dynamic position sizing based on signal strength
- Stop-loss, take-profit, and trailing stops
- Liquidation risk monitoring for futures
- Daily loss limits and circuit breakers
- Leverage support (1-125x)

### Advanced Filters (Research-Backed)
- **ADX Trend Filter**: Avoids choppy markets (ADX < 20)
- **ATR Volatility Filter**: Filters low-volatility periods
- **Bollinger Squeeze Detection**: Waits for breakout confirmation

### Web Dashboard
Real-time monitoring at \`http://localhost:5000\`:
- Live signal visualization with strategy breakdown
- Open positions with unrealized P&L
- Technical indicators (RSI, EMA, MACD, ADX, Stochastic, etc.)
- Performance charts and equity curve
- Trade history with pagination
- Auto-updates every 1 second

## 📊 Optimized Configuration

Based on comprehensive research for Bitcoin/crypto scalping:

- **Timeframe**: 5-minute candles (optimal for scalping)
- **Win Rate Target**: 60-65% (realistic vs 80% unrealistic)
- **Risk/Reward**: 2:1 ratio (0.3% SL / 0.6% TP)
- **Signal Threshold**: 0.20 (balanced selectivity)
- **Max Daily Trades**: 25 (quality over quantity)

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Binance account with API keys
- Testnet keys recommended for testing

### Installation

1. Clone the repository:
\`\`\`bash
git clone https://github.com/yourusername/binance_scalper.git
cd binance_scalper
\`\`\`

2. Create virtual environment:
\`\`\`bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate
\`\`\`

3. Install dependencies:
\`\`\`bash
pip install -r requirements.txt
\`\`\`

4. Configure API keys:
Create a \`.env\` file in the project root:
\`\`\`
TESTNET_API_KEY=your_testnet_api_key
TESTNET_API_SECRET=your_testnet_api_secret
LIVE_API_KEY=your_live_api_key
LIVE_API_SECRET=your_live_api_secret
\`\`\`

Get testnet keys from: https://testnet.binancefuture.com

5. Run the bot:
\`\`\`bash
python bot.py
\`\`\`

6. Access dashboard:
Open browser to \`http://localhost:5000\`

## ⚙️ Configuration

Edit \`config.py\` to customize trading parameters, risk management, and strategy weights.

## ⚠️ Risk Warning

**This bot is for educational purposes only.**

- Cryptocurrency trading carries substantial risk
- Never trade with money you can't afford to lose
- Always test thoroughly on testnet before live trading
- Use at your own risk - no warranty provided

## 📊 Performance Expectations

Based on research and optimization:

- **Expected Win Rate**: 60-65%
- **Risk/Reward Ratio**: 2:1
- **Typical Trades/Day**: 10-25 (on 5m timeframe)

## 📝 License

MIT License

---

**⚡ Happy Trading! Remember: Always start with testnet!**
