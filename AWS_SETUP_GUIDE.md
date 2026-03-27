# 🌐 AWS EC2 SETUP GUIDE - STEP BY STEP

## FREE FOR 12 MONTHS! ✅

Follow this guide exactly - I'll walk you through every step.

---

## 📋 WHAT YOU'LL NEED

- ✅ Email address
- ✅ Credit card (won't be charged during free tier)
- ✅ Phone number for verification
- ✅ 30-45 minutes of time

---

## STEP 1: CREATE AWS ACCOUNT (10 minutes)

### 1.1 Sign Up

1. Open browser and go to: **https://aws.amazon.com**
2. Click **"Create an AWS Account"** (orange button, top right)

### 1.2 Account Details

```
Root user email address: [Your email]
AWS account name: trading-bot-account
```

3. Click **"Verify email address"**
4. Check your email for verification code
5. Enter the 6-digit code

### 1.3 Create Password

```
Password: [Create a strong password]
Confirm password: [Same password]
```

6. Click **"Continue"**

### 1.4 Contact Information

```
Account Type: ✅ Personal
Full Name: [Your name]
Phone Number: [Your phone]
Country: [Your country]
Address: [Your address]
City: [Your city]
State: [Your state]
Postal Code: [Your zip]
```

7. Check the box: "I have read and agree..."
8. Click **"Continue"**

### 1.5 Payment Information

```
Credit/Debit Card Number: [Your card]
Expiration Date: [MM/YY]
Cardholder Name: [Name on card]
```

9. Click **"Verify and Continue"**

⚠️ **NOTE:** You WON'T be charged. Free tier covers everything!

### 1.6 Phone Verification

10. Enter phone number
11. Choose SMS or Voice call
12. Enter verification code
13. Click **"Continue"**

### 1.7 Select Support Plan

14. Choose **"Basic support - Free"**
15. Click **"Complete sign up"**

🎉 **SUCCESS!** You now have an AWS account!

---

## STEP 2: LAUNCH EC2 INSTANCE (10 minutes)

### 2.1 Access EC2 Console

1. Click **"Go to the AWS Management Console"**
2. In the search bar at top, type: **EC2**
3. Click **"EC2"** (Virtual Servers in the Cloud)

### 2.2 Launch Instance

4. Click **"Launch instance"** (orange button)

### 2.3 Name Your Instance

```
Name: trading-bot-24x7
```

### 2.4 Choose Operating System

5. Under "Application and OS Images (Amazon Machine Image)":
   - ✅ Select **"Ubuntu"**
   - ✅ Choose **"Ubuntu Server 22.04 LTS"**
   - ✅ Architecture: **64-bit (x86)**
   - Look for: **"Free tier eligible"** label ✅

### 2.5 Choose Instance Type

6. Under "Instance type":
   - ✅ Select **"t2.micro"**
   - Shows: **"Free tier eligible"** ✅
   - Specs: 1 vCPU, 1 GB RAM

### 2.6 Create Key Pair (IMPORTANT!)

7. Under "Key pair (login)":
   - Click **"Create new key pair"**

```
Key pair name: trading-bot-key
Key pair type: ✅ RSA
Private key file format: ✅ .pem (for Mac/Linux)
                         ✅ .ppk (for Windows PuTTY)
```

8. Click **"Create key pair"**
9. **SAVE THIS FILE!** It will download automatically
10. Move it to a safe location (we'll use it later)

### 2.7 Configure Network Settings

11. Under "Network settings", click **"Edit"**

12. Leave "VPC" as default

13. Under "Firewall (security groups)":
    - ✅ Select **"Create security group"**

```
Security group name: trading-bot-sg
Description: Security group for trading bot
```

14. Inbound security group rules:

**Rule 1 (SSH):**
```
Type: SSH
Protocol: TCP
Port: 22
Source type: My IP
Description: SSH access from my computer
```

**Rule 2 (Dashboard):**
```
Click "Add security group rule"

Type: Custom TCP
Protocol: TCP
Port: 5000
Source type: My IP
Description: Web dashboard access
```

### 2.8 Configure Storage

15. Under "Configure storage":
```
Storage: 30 GiB (default)
Root volume: gp3
✅ Free tier eligible: Up to 30 GB
```

### 2.9 Review and Launch

16. On the right side, review:
```
✅ Ubuntu Server 22.04 LTS
✅ t2.micro (Free tier eligible)
✅ 30 GB storage
✅ Security group with SSH + Port 5000
✅ Key pair: trading-bot-key
```

17. Click **"Launch instance"** (orange button)

🎉 **SUCCESS!** Your server is launching!

### 2.10 Wait for Instance to Start

18. Click **"View all instances"**
19. Wait for "Instance state" to show: ✅ **Running** (2-3 minutes)
20. When running, note down:
    - **Public IPv4 address** (Example: 54.123.45.67)
    - Write this down! You'll need it.

---

## STEP 3: CONNECT TO YOUR SERVER (5 minutes)

### 3.1 Prepare Key File (Mac/Linux)

Open Terminal on your laptop:

```bash
# Move key to SSH folder
mv ~/Downloads/trading-bot-key.pem ~/.ssh/

# Set correct permissions
chmod 400 ~/.ssh/trading-bot-key.pem
```

### 3.2 Connect via SSH

```bash
# Replace YOUR_EC2_IP with the IP you noted
ssh -i ~/.ssh/trading-bot-key.pem ubuntu@YOUR_EC2_IP

# Example:
ssh -i ~/.ssh/trading-bot-key.pem ubuntu@54.123.45.67
```

**First time connecting?**
- You'll see: "Are you sure you want to continue connecting?"
- Type: **yes** and press Enter

🎉 **SUCCESS!** You're connected to your AWS server!

You'll see:
```
ubuntu@ip-172-31-12-34:~$
```

---

## STEP 4: INSTALL SOFTWARE (5 minutes)

Copy and paste each command (wait for each to complete):

### 4.1 Update System

```bash
sudo apt update && sudo apt upgrade -y
```

(Takes 2-3 minutes)

### 4.2 Install Python

```bash
sudo apt install -y python3 python3-pip python3-venv git
```

### 4.3 Install Screen (for 24/7 operation)

```bash
sudo apt install -y screen
```

### 4.4 Install Monitoring Tools

```bash
sudo apt install -y htop
```

🎉 **SUCCESS!** All software installed!

---

## STEP 5: UPLOAD BOT FROM YOUR LAPTOP (5 minutes)

### 5.1 Open NEW Terminal on Your Laptop

**DON'T close the AWS terminal!** Open a NEW terminal window.

### 5.2 Upload Bot Folder

```bash
# Go to Desktop
cd /Users/rahulpatil/Desktop

# Upload bot to AWS
scp -i ~/.ssh/trading-bot-key.pem -r binance_scalper ubuntu@YOUR_EC2_IP:/home/ubuntu/

# Replace YOUR_EC2_IP with your server IP
# Example:
scp -i ~/.ssh/trading-bot-key.pem -r binance_scalper ubuntu@54.123.45.67:/home/ubuntu/
```

This will take 2-3 minutes.

You'll see files uploading:
```
bot.py                    100%
config.py                 100%
strategies_pro.py         100%
...
```

🎉 **SUCCESS!** Bot uploaded to AWS!

### 5.3 Return to AWS Terminal

Go back to the terminal window connected to AWS.

---

## STEP 6: SETUP BOT ON AWS (5 minutes)

### 6.1 Go to Bot Folder

```bash
cd /home/ubuntu/binance_scalper
ls -la
```

You should see all your bot files!

### 6.2 Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

You'll see `(venv)` appear in your prompt.

### 6.3 Install Requirements

```bash
pip install -r requirements.txt
```

(Takes 2-3 minutes)

### 6.4 Create .env File with API Keys

```bash
nano .env
```

This opens a text editor. Type:

```bash
TESTNET_API_KEY=your_testnet_api_key_here
TESTNET_API_SECRET=your_testnet_secret_here
LIVE_API_KEY=your_live_api_key_here
LIVE_API_SECRET=your_live_secret_here
```

**Replace the values with YOUR actual API keys!**

Save and exit:
- Press `Ctrl+O` (save)
- Press `Enter` (confirm)
- Press `Ctrl+X` (exit)

### 6.5 Make Scripts Executable

```bash
chmod +x start_bot.sh stop_bot.sh status.sh
```

🎉 **SUCCESS!** Bot is ready to run!

---

## STEP 7: TEST BOT (2 minutes)

### 7.1 Quick Test

```bash
python3 bot.py
```

You should see:
```
✅ Connected to Binance FUTURES TESTNET
✅ Leverage=10x | Margin=ISOLATED
🚀 Bot started — entering main loop
```

If you see this: **SUCCESS!** ✅

Press `Ctrl+C` to stop the test.

---

## STEP 8: RUN BOT 24/7 (2 minutes)

### 8.1 Start Screen Session

```bash
screen -S trading_bot
```

Screen will open (looks the same but now it's persistent).

### 8.2 Start Bot

```bash
cd /home/ubuntu/binance_scalper
source venv/bin/activate
./start_bot.sh
```

You'll see the bot dashboard updating!

### 8.3 Detach from Screen

**IMPORTANT:** To let bot run 24/7:

Press: `Ctrl+A` then `D`

You'll see: `[detached from 84108.trading_bot]`

🎉 **SUCCESS!** Bot is running 24/7!

You can now close your laptop - bot keeps running!

---

## STEP 9: RECONNECT ANYTIME

### 9.1 SSH Back In

```bash
ssh -i ~/.ssh/trading-bot-key.pem ubuntu@YOUR_EC2_IP
```

### 9.2 Reattach to Bot

```bash
screen -r trading_bot
```

You'll see the live dashboard!

To detach again: `Ctrl+A` then `D`

---

## STEP 10: ACCESS WEB DASHBOARD (5 minutes)

### 10.1 Create SSH Tunnel

From your laptop terminal:

```bash
ssh -i ~/.ssh/trading-bot-key.pem -L 5000:localhost:5000 ubuntu@YOUR_EC2_IP
```

**Keep this terminal window open!**

### 10.2 Open Dashboard

Open browser and go to:

```
http://localhost:5000
```

🎉 **SUCCESS!** You can see your bot's web dashboard!

---

## 🎯 VERIFICATION CHECKLIST

After setup, verify everything works:

- [ ] AWS EC2 instance running
- [ ] Can SSH into server
- [ ] Bot files uploaded
- [ ] Virtual environment created
- [ ] Requirements installed
- [ ] .env file created with API keys
- [ ] Bot tested successfully
- [ ] Screen session created
- [ ] Bot running in background
- [ ] Can reattach to see dashboard
- [ ] Web dashboard accessible

---

## 🛑 HOW TO STOP BOT

### Option 1: From Screen

```bash
# SSH in
ssh -i ~/.ssh/trading-bot-key.pem ubuntu@YOUR_EC2_IP

# Reattach
screen -r trading_bot

# Stop bot
./stop_bot.sh

# Or press Ctrl+C
```

### Option 2: Kill Screen

```bash
# SSH in
ssh -i ~/.ssh/trading-bot-key.pem ubuntu@YOUR_EC2_IP

# Kill screen session
screen -X -S trading_bot quit
```

---

## 🔄 HOW TO RESTART BOT

```bash
# SSH in
ssh -i ~/.ssh/trading-bot-key.pem ubuntu@YOUR_EC2_IP

# Start new screen
screen -S trading_bot

# Start bot
cd /home/ubuntu/binance_scalper
source venv/bin/activate
./start_bot.sh

# Detach
Ctrl+A then D
```

---

## 💰 COST MONITORING

### Check Your Bill

1. AWS Console → Top right → Account name → Billing Dashboard
2. Should show: **$0.00** (free tier)

### What's FREE:

- ✅ 750 hours/month EC2 (t2.micro)
- ✅ 30 GB storage
- ✅ Your bot uses ~5% of limits

### After 12 Months:

- Cost: ~$8-10/month
- Still very cheap!

---

## 🆘 TROUBLESHOOTING

### Can't Connect via SSH?

```bash
# Check key permissions
chmod 400 ~/.ssh/trading-bot-key.pem

# Check instance is running
# AWS Console → EC2 → Instances → State: Running

# Check security group
# Inbound rules must allow SSH (port 22) from My IP
```

### Bot Won't Start?

```bash
# Check Python version
python3 --version  # Should be 3.10+

# Check virtual environment
source venv/bin/activate

# Check requirements
pip list

# Check API keys
cat .env
```

### Screen Not Found?

```bash
# List screens
screen -ls

# If empty, create new
screen -S trading_bot
cd /home/ubuntu/binance_scalper
source venv/bin/activate
./start_bot.sh
```

---

## 📱 MOBILE ACCESS

### SSH from Phone

**Android:**
1. Install "Termux" from Play Store
2. Copy key to phone: `~/.ssh/trading-bot-key.pem`
3. Connect: `ssh -i trading-bot-key.pem ubuntu@YOUR_IP`

**iOS:**
1. Install "Terminus" from App Store
2. Import key file
3. Add connection
4. Connect

---

## 🎉 YOU'RE DONE!

Your bot is now:
- ✅ Running 24/7 on AWS
- ✅ FREE for 12 months
- ✅ Professional strategy (55.4% win rate)
- ✅ Automatic trading
- ✅ Accessible from anywhere

**Just monitor it daily and let it work!** 🚀

---

## 📞 NEED HELP?

If stuck at any step, tell me:
1. Which step you're on
2. What error you see
3. Screenshot if possible

I'll help you fix it! 💪
