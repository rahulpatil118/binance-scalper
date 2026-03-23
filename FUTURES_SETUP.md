# Binance Futures Testnet Setup Guide

## Overview

This guide will help you set up the bot for **Binance Futures trading with 10x leverage** on the **Testnet** (fake money for testing).

**IMPORTANT**: NEVER skip testing. Futures trading with leverage can lead to rapid capital loss if not properly tested.

---

## Step 1: Get Binance Futures Testnet API Keys

### Option A: Quick Setup (No Registration)

1. Go to https://testnet.binancefuture.com
2. Click **"Generate HMAC_SHA256 Key"** button
3. Your API Key and Secret Key will be displayed immediately
4. **Copy both keys** - you won't be able to see the secret again!

### Option B: Authenticated Setup (Better for long-term testing)

1. Go to https://testnet.binancefuture.com
2. Login with your GitHub account or email
3. Navigate to **API Keys** section
4. Click **"Create New Key"**
5. Copy both the API Key and Secret Key

**Default Testnet Balance**: ~100,000 USDT (fake money for testing)

---

## Step 2: Configure Your `.env` File

1. Navigate to your project directory:
   ```bash
   cd /Users/rahulpatil/Desktop/binance_scalper
   ```

2. The `.env` file should already exist. Open it and update with your **testnet** keys:
   ```bash
   # Testnet keys for FUTURES
   TESTNET_API_KEY=your_testnet_api_key_here
   TESTNET_API_SECRET=your_testnet_api_secret_here

   # Keep testnet enabled
   USE_TESTNET=1
   ```

3. **IMPORTANT**: Never commit your `.env` file to git!

---

## Step 3: Verify Configuration

Check that `config.py` has the correct settings:

```python
# Should be at the end of config.py
USE_FUTURES = True                    # Enable futures trading
FUTURES_LEVERAGE = 10                 # 10x leverage
MARGIN_TYPE = "ISOLATED"              # Safer than CROSS
POSITION_MODE = "HEDGE"               # Allows LONG+SHORT

# Safety parameters
LIQUIDATION_BUFFER_PCT = 0.20         # Stay 20% from liquidation
MIN_MARGIN_RATIO = 0.30               # Close if margin < 30%
MAX_FUNDING_RATE_PCT = 0.05           # Close if funding too high
```

---

## Step 4: Test Connection

Verify your API keys work:

```bash
cd /Users/rahulpatil/Desktop/binance_scalper
source venv/bin/activate
python -c "from binance_client import BinanceClient; c = BinanceClient(); print(c.get_futures_balance())"
```

**Expected output**:
```
{'available': 100000.0, 'total_equity': 100000.0}
```

If you see an error, check your API keys in `.env`.

---

## Step 5: Run Backtest FIRST (MANDATORY!)

**CRITICAL**: NEVER run the bot without backtesting first!

```bash
source venv/bin/activate
python backtest.py --symbol BTCUSDT --interval 1m --days 30 --futures --leverage 10
```

### What to Look For:

✅ **MUST PASS** criteria:
- **Liquidations: 0** (if any liquidations occur, DO NOT proceed)
- **Win rate: > 55%**
- **Profit factor: > 1.5**
- **Max drawdown: < 20%**
- **Return: Positive**

❌ **RED FLAGS** (Do NOT proceed):
- Any liquidations
- Win rate < 50%
- Profit factor < 1.2
- Max drawdown > 25%
- Negative return

### Example Good Result:
```
==================================================
  BACKTEST RESULTS (FUTURES 10x)
==================================================
  total_trades         142
  win_rate             58.5
  total_pnl            1234.56
  return_pct           12.35
  profit_factor        1.85
  max_drawdown_pct     14.2
  liquidations         0
  liquidation_rate     0.0
==================================================
```

---

## Step 6: Paper Trade for 1 Week Minimum

Even after successful backtest, you MUST paper trade on testnet:

```bash
source venv/bin/activate
python bot.py
```

### What to Monitor:

1. **Dashboard Output**:
   - Leverage displayed correctly (10x)
   - Positions open and close properly
   - Stop-loss triggers before liquidation
   - Liquidation price is shown

2. **Log File** (`logs/bot.log`):
   - Check for any errors
   - Verify orders are placed correctly
   - Monitor liquidation distance

3. **Trade Log** (`logs/trades.csv`):
   - Review each trade
   - Confirm PnL calculations
   - Check exit reasons

### Daily Checklist (For 7 Days):

- [ ] Day 1: Bot runs without crashes
- [ ] Day 2: At least 5 trades executed successfully
- [ ] Day 3: No liquidations, stop-losses trigger correctly
- [ ] Day 4: Win rate matches backtest (±10%)
- [ ] Day 5: Dashboard shows accurate data
- [ ] Day 6: No unusual errors in logs
- [ ] Day 7: Overall PnL is positive

---

## Step 7: Understand the Risks

### What is 10x Leverage?

- **10x leverage** means you control $10,000 worth of Bitcoin with only $1,000 margin
- **Profit/Loss is amplified 10x**
- A 5% price move against you = 50% loss of your margin
- **Liquidation** occurs if price moves ~9% against your position

### Liquidation Example:

**LONG Position**:
- Entry: $50,000
- Leverage: 10x
- Liquidation price: ~$45,500 (9% drop)
- If BTC drops to $45,500, your position is automatically closed and you lose your margin

**SHORT Position**:
- Entry: $50,000
- Leverage: 10x
- Liquidation price: ~$54,500 (9% rise)
- If BTC rises to $54,500, your position is automatically closed and you lose your margin

### How the Bot Prevents Liquidation:

1. **Stop-loss placed 0.5% from entry** (triggers before liquidation)
2. **Liquidation buffer of 20%** (bot closes if within 20% of liquidation)
3. **Pre-trade safety checks** (won't open if liquidation too close)
4. **Real-time monitoring** (checks every 10 seconds)

---

## Step 8: Safety Checklist Before Going Live

**ONLY proceed to live trading if ALL conditions are met:**

### Backtest Requirements:
- [ ] Run backtest on 30 days of data
- [ ] Zero liquidations in backtest
- [ ] Win rate > 55%
- [ ] Profit factor > 1.5
- [ ] Max drawdown < 20%

### Paper Trading Requirements:
- [ ] Ran successfully for 7+ days on testnet
- [ ] Zero liquidations occurred
- [ ] Results match backtest (±10%)
- [ ] All safety mechanisms tested
- [ ] Stop-losses triggered correctly
- [ ] Bot recovered gracefully from any errors

### Understanding:
- [ ] I understand how liquidation works
- [ ] I understand 10x leverage amplifies losses
- [ ] I know this is highly risky
- [ ] I'm only risking money I can afford to lose
- [ ] I've read all the documentation

---

## Step 9: Going Live (PROCEED WITH CAUTION)

If you've passed ALL checks above, you can switch to live:

### For Live Trading:

1. Get **LIVE** Binance Futures API keys:
   - Go to https://www.binance.com
   - Account → API Management
   - Create New Key
   - Enable "Futures" permission
   - **Restrict to specific IPs** for security

2. Update `.env`:
   ```bash
   # Live keys
   LIVE_API_KEY=your_live_api_key_here
   LIVE_API_SECRET=your_live_api_secret_here

   # SWITCH TO LIVE
   USE_TESTNET=0
   ```

3. **Start with LOW leverage**:
   ```python
   # In config.py - START CONSERVATIVE
   FUTURES_LEVERAGE = 2  # Not 10!
   ```

4. **Start with SMALL capital**:
   - Use only 1-5% of your total funds initially
   - Scale up gradually after 1-2 weeks of success

---

## Common Issues & Solutions

### Issue: "APIError: Invalid API key"
**Solution**:
- Double-check your API keys in `.env`
- Ensure you're using **futures testnet keys** from testnet.binancefuture.com
- Make sure there are no extra spaces in the keys

### Issue: "Insufficient margin"
**Solution**:
- Your testnet balance might be low
- Reduce `TRADE_QUANTITY` in config.py
- Reduce `FUTURES_LEVERAGE` to lower margin requirements

### Issue: Bot crashes immediately
**Solution**:
- Check `logs/bot.log` for specific error
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Verify Python version is 3.9+

### Issue: Liquidations in backtest
**Solution**:
- **DO NOT PROCEED** until fixed
- Reduce leverage (try 5x instead of 10x)
- Increase `STOP_LOSS_PCT` in config.py
- Increase `LIQUIDATION_BUFFER_PCT` in config.py

---

## Monitoring Your Bot

### Dashboard (Real-time):
The bot displays a live dashboard showing:
- Current price and signal
- Strategy scores
- Indicators (RSI, EMA, etc.)
- Account balance and PnL
- Open positions
- Win/Loss stats

### Log Files:
- `logs/bot.log` - All bot activity
- `logs/trades.csv` - Detailed trade history

### Check Every 4-6 Hours:
- Dashboard shows reasonable values
- No liquidation warnings
- PnL is trending positive
- Stop-losses are triggering when needed

---

## Emergency: How to Stop the Bot

### Graceful Shutdown:
Press `Ctrl+C` in the terminal where the bot is running. This will:
1. Close all open positions
2. Save final statistics
3. Exit cleanly

### Force Stop:
If the bot is unresponsive:
```bash
ps aux | grep "python bot.py"
kill -9 <process_id>
```

**Note**: Force stopping may leave positions open. Check Binance and close manually if needed.

---

## Final Reminders

1. **80% Win Rate is Unrealistic**
   - Professional traders achieve 55-60% win rate
   - Focus on profit factor, not win rate
   - Risk management is more important than win rate

2. **Leverage Amplifies Everything**
   - 10x leverage = 10x profits AND 10x losses
   - Start with 2-3x, not 10x
   - Higher leverage = higher liquidation risk

3. **Never Trade Without Stop-Losses**
   - The bot automatically sets stop-losses
   - Don't disable this feature
   - Stop-losses save you from liquidation

4. **Markets Are Unpredictable**
   - Past performance ≠ future results
   - Backtest success doesn't guarantee live success
   - Always expect the unexpected

5. **Only Risk What You Can Afford to Lose**
   - Crypto is extremely volatile
   - Futures trading is high risk
   - Never use borrowed money

---

## Support & Resources

- **Binance Futures Testnet**: https://testnet.binancefuture.com
- **Binance Futures Guide**: https://www.binance.com/en/support/faq/futures
- **Bot Issues**: Check `logs/bot.log` first

**Good luck, and trade safely! 🚀**
