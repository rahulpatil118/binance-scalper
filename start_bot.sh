#!/bin/bash
# ============================================================
#  Start Bot - 24/7 Background Process
# ============================================================

cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Kill any existing bot processes
pkill -f "python bot.py"
sleep 2

# Create logs directory if it doesn't exist
mkdir -p logs

# Start bot with nohup (runs in background, persists after terminal closes)
nohup python bot.py > logs/bot_console.log 2>&1 &

BOT_PID=$!
echo "✅ Bot started with PID: $BOT_PID"
echo $BOT_PID > logs/bot.pid

# Wait a few seconds and check if it's running
sleep 5

if ps -p $BOT_PID > /dev/null; then
    echo "✅ Bot is running successfully"
    echo "📊 Dashboard: http://localhost:5000"
    echo "📝 Logs: tail -f logs/bot_console.log"
    echo "🛑 Stop: ./stop_bot.sh"
else
    echo "❌ Bot failed to start. Check logs/bot_console.log"
    exit 1
fi
