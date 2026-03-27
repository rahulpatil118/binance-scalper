#!/bin/bash

# ============================================================
# Setup Bot on AWS EC2 Instance
# Run this script ON THE EC2 INSTANCE after uploading files
# ============================================================

echo "🔧 Setting up Trading Bot on AWS EC2"
echo "====================================="
echo ""

# Step 1: Update system
echo "📦 Step 1: Updating system..."
sudo apt update -qq
sudo apt upgrade -y -qq
echo "✅ System updated"
echo ""

# Step 2: Install Python and dependencies
echo "🐍 Step 2: Installing Python..."
sudo apt install -y python3 python3-pip python3-venv git screen htop -qq
echo "✅ Python installed"
echo ""

# Step 3: Create virtual environment
echo "🌐 Step 3: Creating virtual environment..."
cd /home/ubuntu
python3 -m venv venv
source venv/bin/activate
echo "✅ Virtual environment created"
echo ""

# Step 4: Install Python packages
echo "📚 Step 4: Installing Python packages..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "✅ Python packages installed"
echo ""

# Step 5: Make scripts executable
echo "🔐 Step 5: Setting permissions..."
chmod +x start_bot.sh stop_bot.sh status.sh
echo "✅ Permissions set"
echo ""

# Step 6: Create .env file
echo "🔑 Step 6: Creating .env file..."
if [ ! -f .env ]; then
    cat > .env << 'EOF'
TESTNET_API_KEY=your_testnet_key_here
TESTNET_API_SECRET=your_testnet_secret_here
LIVE_API_KEY=your_live_key_here
LIVE_API_SECRET=your_live_secret_here
EOF
    echo "⚠️  .env file created with placeholders"
    echo "⚠️  IMPORTANT: Edit .env with your API keys!"
    echo ""
    echo "Run: nano .env"
    echo "Then replace the placeholder values"
else
    echo "✅ .env file already exists"
fi
echo ""

# Step 7: Create systemd service for auto-restart
echo "🔄 Step 7: Creating systemd service..."
sudo tee /etc/systemd/system/trading-bot.service > /dev/null << EOF
[Unit]
Description=Binance Trading Bot - Professional Strategy (55.4% WR)
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu
Environment="PATH=/home/ubuntu/venv/bin"
ExecStart=/home/ubuntu/venv/bin/python3 /home/ubuntu/bot.py
Restart=always
RestartSec=10
StandardOutput=append:/home/ubuntu/logs/bot_console.log
StandardError=append:/home/ubuntu/logs/bot_console.log

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable trading-bot
echo "✅ Systemd service created (auto-starts on boot)"
echo ""

# Step 8: Setup firewall
echo "🔒 Step 8: Configuring firewall..."
sudo ufw allow 22/tcp -q
sudo ufw allow 5000/tcp -q
echo "✅ Firewall rules added"
echo ""

# Summary
echo "════════════════════════════════════════════════════════════"
echo "✅ SETUP COMPLETE!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "📝 Next Steps:"
echo ""
echo "1. Edit API keys:"
echo "   nano .env"
echo ""
echo "2. Test bot:"
echo "   source venv/bin/activate"
echo "   python3 bot.py"
echo "   (Press Ctrl+C to stop test)"
echo ""
echo "3. Run bot 24/7 using Screen:"
echo "   screen -S trading_bot"
echo "   source venv/bin/activate"
echo "   ./start_bot.sh"
echo "   (Press Ctrl+A then D to detach)"
echo ""
echo "4. OR run bot with systemd (auto-restart):"
echo "   sudo systemctl start trading-bot"
echo "   sudo systemctl status trading-bot"
echo ""
echo "5. View logs:"
echo "   tail -f logs/bot_console.log"
echo ""
echo "════════════════════════════════════════════════════════════"
