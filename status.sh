#!/bin/bash
# ============================================================
#  Check Bot Status
# ============================================================

cd "$(dirname "$0")"

echo "=========================================="
echo "  📊 Binance Scalper Bot Status"
echo "=========================================="
echo ""

# Check if bot process is running
if ps aux | grep "[p]ython bot.py" > /dev/null; then
    BOT_PID=$(ps aux | grep "[p]ython bot.py" | awk '{print $2}' | head -1)
    echo "✅ Bot Status: RUNNING"
    echo "   PID: $BOT_PID"

    # Check uptime
    if [ -f logs/bot.pid ]; then
        echo "   PID File: logs/bot.pid"
    fi

    # Check if dashboard is accessible
    if curl -s http://localhost:5000 > /dev/null 2>&1; then
        echo "✅ Dashboard: ONLINE"
        echo "   URL: http://localhost:5000"
    else
        echo "❌ Dashboard: OFFLINE"
    fi

    # Show recent log entries
    echo ""
    echo "📝 Recent Logs (last 5 lines):"
    echo "----------------------------"
    tail -5 logs/bot.log 2>/dev/null || echo "No logs found"

else
    echo "❌ Bot Status: NOT RUNNING"
    echo ""
    echo "To start the bot:"
    echo "  ./start_bot.sh"
fi

echo ""
echo "=========================================="
