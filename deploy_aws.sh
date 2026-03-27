#!/bin/bash

# ============================================================
# AWS EC2 Deployment Script - Mumbai Region
# Deploys trading bot to AWS EC2 in ap-south-1
# ============================================================

set -e

REGION="ap-south-1"  # Mumbai
INSTANCE_TYPE="t2.micro"  # Free tier
AMI_ID="ami-0f58b397bc5c1f2e8"  # Ubuntu 22.04 LTS in Mumbai
KEY_NAME="trading-bot-key-mumbai"
SECURITY_GROUP_NAME="trading-bot-sg"
INSTANCE_NAME="trading-bot-24x7"

echo "🚀 Deploying Trading Bot to AWS EC2 (Mumbai Region)"
echo "======================================================="
echo ""

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install it first."
    exit 1
fi

echo "✅ AWS CLI found"
echo ""

# Check AWS credentials
echo "🔐 Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured."
    echo "Run: aws configure"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "✅ Authenticated as Account: $ACCOUNT_ID"
echo ""

# Step 1: Create Key Pair if not exists
echo "🔑 Step 1: Creating key pair..."
if aws ec2 describe-key-pairs --key-names "$KEY_NAME" --region "$REGION" &> /dev/null; then
    echo "ℹ️  Key pair '$KEY_NAME' already exists"
else
    aws ec2 create-key-pair \
        --key-name "$KEY_NAME" \
        --region "$REGION" \
        --query 'KeyMaterial' \
        --output text > ~/.ssh/"$KEY_NAME".pem

    chmod 400 ~/.ssh/"$KEY_NAME".pem
    echo "✅ Key pair created: ~/.ssh/$KEY_NAME.pem"
fi
echo ""

# Step 2: Create Security Group
echo "🔒 Step 2: Creating security group..."

# Get default VPC
VPC_ID=$(aws ec2 describe-vpcs --region "$REGION" --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text)

if [ "$VPC_ID" == "None" ]; then
    echo "❌ No default VPC found. Please create one first."
    exit 1
fi

echo "✅ Using VPC: $VPC_ID"

# Check if security group exists
SG_ID=$(aws ec2 describe-security-groups --region "$REGION" --filters "Name=group-name,Values=$SECURITY_GROUP_NAME" --query "SecurityGroups[0].GroupId" --output text 2>/dev/null || echo "")

if [ -z "$SG_ID" ] || [ "$SG_ID" == "None" ]; then
    # Create security group
    SG_ID=$(aws ec2 create-security-group \
        --group-name "$SECURITY_GROUP_NAME" \
        --description "Security group for trading bot" \
        --vpc-id "$VPC_ID" \
        --region "$REGION" \
        --query 'GroupId' \
        --output text)

    echo "✅ Security group created: $SG_ID"

    # Get your IP
    MY_IP=$(curl -s https://checkip.amazonaws.com)
    echo "✅ Your IP: $MY_IP"

    # Add SSH rule
    aws ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp \
        --port 22 \
        --cidr "$MY_IP/32" \
        --region "$REGION" \
        --no-cli-pager

    echo "✅ SSH access allowed from $MY_IP"

    # Add dashboard rule
    aws ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp \
        --port 5000 \
        --cidr "$MY_IP/32" \
        --region "$REGION" \
        --no-cli-pager

    echo "✅ Dashboard access allowed from $MY_IP"
else
    echo "ℹ️  Security group already exists: $SG_ID"
fi
echo ""

# Step 3: Launch EC2 Instance
echo "🖥️  Step 3: Launching EC2 instance..."

INSTANCE_ID=$(aws ec2 run-instances \
    --image-id "$AMI_ID" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_NAME" \
    --security-group-ids "$SG_ID" \
    --region "$REGION" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
    --query 'Instances[0].InstanceId' \
    --output text)

echo "✅ Instance launched: $INSTANCE_ID"
echo ""

# Step 4: Wait for instance to start
echo "⏳ Step 4: Waiting for instance to start..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$REGION"
echo "✅ Instance is running"
echo ""

# Step 5: Get instance details
echo "📊 Step 5: Getting instance details..."
INSTANCE_IP=$(aws ec2 describe-instances \
    --instance-ids "$INSTANCE_ID" \
    --region "$REGION" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

echo "✅ Public IP: $INSTANCE_IP"
echo ""

# Step 6: Wait for SSH to be ready
echo "⏳ Step 6: Waiting for SSH to be ready (30 seconds)..."
sleep 30
echo "✅ SSH should be ready"
echo ""

# Save details to file
cat > aws_instance_details.txt << EOF
AWS EC2 Instance Details
========================

Region:           $REGION (Mumbai)
Instance ID:      $INSTANCE_ID
Public IP:        $INSTANCE_IP
Key Pair:         ~/.ssh/$KEY_NAME.pem
Security Group:   $SG_ID

SSH Command:
ssh -i ~/.ssh/$KEY_NAME.pem ubuntu@$INSTANCE_IP

Dashboard Tunnel:
ssh -i ~/.ssh/$KEY_NAME.pem -L 5000:localhost:5000 ubuntu@$INSTANCE_IP

Then open: http://localhost:5000
EOF

echo "✅ Instance details saved to: aws_instance_details.txt"
echo ""

# Summary
echo "════════════════════════════════════════════════════════════"
echo "🎉 AWS EC2 INSTANCE DEPLOYED SUCCESSFULLY!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "📊 Instance Details:"
echo "   Region:       $REGION (Mumbai)"
echo "   Instance ID:  $INSTANCE_ID"
echo "   Public IP:    $INSTANCE_IP"
echo "   Type:         $INSTANCE_TYPE (FREE TIER)"
echo ""
echo "🔑 SSH Connection:"
echo "   ssh -i ~/.ssh/$KEY_NAME.pem ubuntu@$INSTANCE_IP"
echo ""
echo "📝 Next Steps:"
echo "   1. Wait 2 minutes for instance to fully initialize"
echo "   2. Run: ./upload_bot_aws.sh $INSTANCE_IP"
echo "   3. SSH in and setup bot"
echo ""
echo "💾 Details saved to: aws_instance_details.txt"
echo "════════════════════════════════════════════════════════════"
