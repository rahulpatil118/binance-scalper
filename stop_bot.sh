#!/bin/bash
# ============================================================
#  Stop Bot
# ============================================================

cd "$(dirname "$0")"

echo "🛑 Stopping bot..."

# Read PID from file
if [ -f logs/bot.pid ]; then
    BOT_PID=$(cat logs/bot.pid)
    if ps -p $BOT_PID > /dev/null; then
        kill $BOT_PID
        echo "✅ Bot stopped (PID: $BOT_PID)"
    else
        echo "⚠️  Bot process not found (PID: $BOT_PID)"
    fi
    rm logs/bot.pid
fi

# Fallback: kill all python bot.py processes (force kill -9)
pkill -9 -f "python bot.py"
sleep 1

# Verify all processes are stopped
if ps aux | grep "[p]ython bot.py" > /dev/null; then
    echo "⚠️  Some bot processes still running, force killing..."
    ps aux | grep "[p]ython bot.py" | awk '{print $2}' | xargs kill -9 2>/dev/null
fi

echo "✅ All bot processes stopped"
