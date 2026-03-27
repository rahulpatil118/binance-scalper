#!/bin/bash
# ============================================================
#  Keep Alive - Auto-restart bot if it crashes
#  Run this script to ensure 24/7 uptime
# ============================================================

cd "$(dirname "$0")"

echo "🔄 Starting Keep-Alive monitor for 24/7 operation..."
echo "📊 Dashboard will be available at http://localhost:5000"
echo "Press Ctrl+C to stop monitoring"
echo ""

source venv/bin/activate

while true; do
    # Check if bot is running
    if ! pgrep -f "python bot.py" > /dev/null; then
        echo "⚠️  $(date): Bot not running, restarting..."

        # Kill any zombie processes
        pkill -9 -f "python bot.py" 2>/dev/null
        sleep 2

        # Start bot
        nohup python bot.py > logs/bot_console.log 2>&1 &
        BOT_PID=$!
        echo $BOT_PID > logs/bot.pid

        echo "✅ $(date): Bot restarted with PID: $BOT_PID"

        # Wait for bot to initialize
        sleep 10
    fi

    # Check every 30 seconds
    sleep 30
done
