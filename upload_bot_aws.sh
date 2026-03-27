#!/bin/bash

# ============================================================
# Upload Bot to AWS EC2
# ============================================================

if [ -z "$1" ]; then
    echo "❌ Usage: ./upload_bot_aws.sh <EC2_IP_ADDRESS>"
    echo "Example: ./upload_bot_aws.sh 13.233.123.45"
    exit 1
fi

EC2_IP=$1
KEY_FILE="$HOME/.ssh/trading-bot-key-mumbai.pem"

echo "📤 Uploading bot to AWS EC2..."
echo "================================"
echo "IP: $EC2_IP"
echo ""

# Check key exists
if [ ! -f "$KEY_FILE" ]; then
    echo "❌ Key file not found: $KEY_FILE"
    exit 1
fi

# Upload bot folder
echo "📦 Uploading bot files..."
scp -i "$KEY_FILE" -o StrictHostKeyChecking=no -r \
    bot.py \
    config.py \
    strategies_pro.py \
    indicators.py \
    binance_client.py \
    risk_manager.py \
    trade_logger.py \
    dashboard.py \
    web_server.py \
    close_all_positions.py \
    start_bot.sh \
    stop_bot.sh \
    status.sh \
    requirements.txt \
    README.md \
    PRODUCTION_READY.md \
    CURRENT_BACKTEST_RESULTS.md \
    ubuntu@$EC2_IP:/home/ubuntu/

echo "✅ Files uploaded"
echo ""

# Create directories
echo "📁 Creating directories..."
ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ubuntu@$EC2_IP << 'EOF'
mkdir -p ~/logs ~/models ~/templates ~/static/css ~/static/js
EOF

echo "✅ Directories created"
echo ""

# Upload templates and static files if they exist
if [ -d "templates" ]; then
    echo "📤 Uploading templates..."
    scp -i "$KEY_FILE" -o StrictHostKeyChecking=no -r templates/* ubuntu@$EC2_IP:/home/ubuntu/templates/
fi

if [ -d "static" ]; then
    echo "📤 Uploading static files..."
    scp -i "$KEY_FILE" -o StrictHostKeyChecking=no -r static/* ubuntu@$EC2_IP:/home/ubuntu/static/
fi

echo ""
echo "✅ Upload complete!"
echo ""
echo "Next steps:"
echo "1. SSH into server: ssh -i $KEY_FILE ubuntu@$EC2_IP"
echo "2. Run setup script: ./setup_bot_on_aws.sh"
