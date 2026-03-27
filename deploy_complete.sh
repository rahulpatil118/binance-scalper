#!/bin/bash

# ============================================================
# Complete AWS Deployment - One Command Setup
# ============================================================

set -e

echo "🚀 COMPLETE AWS DEPLOYMENT - MUMBAI REGION"
echo "==========================================="
echo ""
echo "This will:"
echo "  1. Create EC2 instance in Mumbai"
echo "  2. Upload bot files"
echo "  3. Install all dependencies"
echo "  4. Configure bot"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi
echo ""

# Step 1: Deploy EC2 instance
echo "════════════════════════════════════════════════════════════"
echo "Step 1/4: Deploying EC2 Instance..."
echo "════════════════════════════════════════════════════════════"
./deploy_aws.sh

# Get instance IP from saved file
if [ ! -f aws_instance_details.txt ]; then
    echo "❌ Instance details not found. Deployment failed."
    exit 1
fi

INSTANCE_IP=$(grep "Public IP:" aws_instance_details.txt | awk '{print $3}')
KEY_FILE="$HOME/.ssh/trading-bot-key-mumbai.pem"

echo ""
echo "✅ Instance deployed: $INSTANCE_IP"
echo ""

# Step 2: Wait for instance to be ready
echo "════════════════════════════════════════════════════════════"
echo "Step 2/4: Waiting for instance to be ready..."
echo "════════════════════════════════════════════════════════════"
echo "⏳ Waiting 60 seconds for SSH to be ready..."
sleep 60
echo "✅ Instance should be ready"
echo ""

# Step 3: Upload bot files
echo "════════════════════════════════════════════════════════════"
echo "Step 3/4: Uploading bot files..."
echo "════════════════════════════════════════════════════════════"
./upload_bot_aws.sh $INSTANCE_IP
echo ""

# Step 4: Setup bot on EC2
echo "════════════════════════════════════════════════════════════"
echo "Step 4/4: Setting up bot on EC2..."
echo "════════════════════════════════════════════════════════════"

# Upload setup script
scp -i "$KEY_FILE" -o StrictHostKeyChecking=no setup_bot_on_aws.sh ubuntu@$INSTANCE_IP:/home/ubuntu/

# Run setup script
ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP << 'EOF'
chmod +x setup_bot_on_aws.sh
./setup_bot_on_aws.sh
EOF

echo ""
echo "════════════════════════════════════════════════════════════"
echo "🎉 DEPLOYMENT COMPLETE!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Your trading bot is deployed to AWS EC2 (Mumbai)"
echo ""
echo "📊 Instance Details:"
echo "   IP Address: $INSTANCE_IP"
echo "   Region: ap-south-1 (Mumbai)"
echo "   Type: t2.micro (FREE TIER)"
echo ""
echo "🔑 SSH Connection:"
echo "   ssh -i $KEY_FILE ubuntu@$INSTANCE_IP"
echo ""
echo "📝 IMPORTANT Next Steps:"
echo ""
echo "1. SSH into server:"
echo "   ssh -i $KEY_FILE ubuntu@$INSTANCE_IP"
echo ""
echo "2. Edit API keys:"
echo "   nano .env"
echo "   Add your Binance API keys"
echo "   Save: Ctrl+O, Enter, Ctrl+X"
echo ""
echo "3. Start bot in screen:"
echo "   screen -S trading_bot"
echo "   source venv/bin/activate"
echo "   ./start_bot.sh"
echo "   Detach: Ctrl+A then D"
echo ""
echo "4. Access dashboard from laptop:"
echo "   ssh -i $KEY_FILE -L 5000:localhost:5000 ubuntu@$INSTANCE_IP"
echo "   Open browser: http://localhost:5000"
echo ""
echo "💾 Details saved to: aws_instance_details.txt"
echo "════════════════════════════════════════════════════════════"
