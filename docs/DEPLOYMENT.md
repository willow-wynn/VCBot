# VCBot Deployment Guide

This guide covers various deployment options for VCBot, from development to production environments. Because someone has to keep this bot running, and it might as well be you.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Development Deployment](#development-deployment)
3. [Production Deployment](#production-deployment)
4. [Docker Deployment](#docker-deployment)
5. [Cloud Deployment](#cloud-deployment)
6. [Configuration Management](#configuration-management)
7. [Monitoring and Maintenance](#monitoring-and-maintenance)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

Before deploying VCBot, ensure you have:

- **Python 3.12+** (tested on 3.12.3, minimum 3.8)
- **Discord Bot Token** (from Discord Developer Portal)
- **Google Gemini API Key** (from Google AI Studio)
- **Sufficient system resources** (4GB RAM recommended, 2GB minimum)
- **Network connectivity** for Discord and Google APIs
- **Basic understanding of Discord permissions** (because the bot needs to actually do things)

## Development Deployment

### Local Setup (For Testing and Development)

Perfect for testing before you unleash this chaos on your production server, or if you just want to run it on your personal machine.

1. **Clone the repository:**
```bash
git clone https://github.com/willow-wynn/VCBot.git
cd VCBot
```

2. **Create virtual environment:**
```bash
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows (Command Prompt):
venv\Scripts\activate

# On Windows (PowerShell):
venv\Scripts\Activate.ps1
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure environment:**
Create a `.env` file in the project root:
```bash
# Copy the example if it exists, or create from scratch
cp .env.example .env 2>/dev/null || touch .env
```

Edit `.env` with your credentials:
```env
# Required - Get these from Discord Developer Portal and Google AI Studio
BOT_ID=your_bot_user_id_here
DISCORD_TOKEN=your_discord_bot_token_here
GEMINI_API_KEY=your_gemini_api_key_here

# Channel IDs - Right-click channels in Discord and "Copy ID"
RECORDS_CHANNEL=1234567890123456789
NEWS_CHANNEL=1234567890123456789
SIGN_CHANNEL=1234567890123456789
CLERK_CHANNEL=1234567890123456789

# Optional - Your Discord server ID for faster command sync
GUILD=1234567890123456789

# Optional - Set to DEBUG for more verbose logging
LOG_LEVEL=INFO
```

5. **Run the bot:**
```bash
python main.py
```

If successful, you should see:
```
INFO - Starting VCBot...
INFO - Logged in as YourBotName#1234
INFO - Initialized services
INFO - Commands synced: X commands
```

### Local Deployment Options

#### Option 1: Run in Terminal (Simplest)
Just run `python main.py` in your activated virtual environment. Great for testing, but the bot stops when you close the terminal.

#### Option 2: Run as Background Process (macOS/Linux)
```bash
# Run in background
nohup python main.py > bot.log 2>&1 &

# Check if it's running
ps aux | grep "python main.py"

# Stop it
pkill -f "python main.py"
```

#### Option 3: Run with Screen (Persistent Terminal)
```bash
# Start a screen session
screen -S vcbot

# Run the bot
python main.py

# Detach with Ctrl+A, then D
# Reattach later with: screen -r vcbot
```

#### Option 4: macOS LaunchAgent (Auto-start on macOS)
Create `~/Library/LaunchAgents/com.vcbot.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.vcbot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/your/VCBot/venv/bin/python</string>
        <string>/path/to/your/VCBot/main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/your/VCBot</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/path/to/your/VCBot/logs/vcbot.log</string>
    <key>StandardOutPath</key>
    <string>/path/to/your/VCBot/logs/vcbot.log</string>
</dict>
</plist>
```

Then:
```bash
launchctl load ~/Library/LaunchAgents/com.vcbot.plist
launchctl start com.vcbot
```

#### Option 5: Windows Service (Auto-start on Windows)
Use `nssm` (Non-Sucking Service Manager):
1. Download NSSM from https://nssm.cc/
2. Run `nssm install VCBot`
3. Set Application path to your `python.exe` in the venv
4. Set Arguments to the path to `main.py`
5. Set Startup directory to your VCBot folder

### Development Best Practices

- **Use a test Discord server**: Don't spam your production server while testing
- **Enable debug logging**: Set `LOG_LEVEL=DEBUG` for troubleshooting
- **Keep backups**: Copy production data files before testing
- **Monitor resources**: AI models can use significant RAM (watch Activity Monitor/Task Manager)
- **Use virtual environments**: Always activate your venv before running
- **Test commands thoroughly**: Try edge cases and error conditions
- **Check logs regularly**: Monitor the `logs/` directory for errors

## Production Deployment

### System Preparation

1. **Update system packages:**
```bash
sudo apt update && sudo apt upgrade -y
```

2. **Install Python and dependencies:**
```bash
# For Ubuntu/Debian
sudo apt install python3.12 python3.12-venv python3-pip -y

# For CentOS/RHEL
sudo yum install python3 python3-venv python3-pip -y
```

3. **Create dedicated user:**
```bash
sudo useradd -m -s /bin/bash vcbot
sudo su - vcbot
```

### Production Setup

1. **Clone and setup:**
```bash
git clone https://github.com/willow-wynn/VCBot.git
cd VCBot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. **Configure production environment:**
```bash
# Create production config
cat > .env << EOF
# Required settings
BOT_ID=your_bot_id_here
DISCORD_TOKEN=your_production_token
GEMINI_API_KEY=your_production_api_key

# Channel configuration
RECORDS_CHANNEL=1234567890123456789
NEWS_CHANNEL=1234567890123456789
SIGN_CHANNEL=1234567890123456789
CLERK_CHANNEL=1234567890123456789

# Optional but recommended
GUILD=1234567890123456789
LOG_LEVEL=INFO
EOF

# Secure the config (important!)
chmod 600 .env
```

### Systemd Service

Create a systemd service for automatic startup and management (because you don't want to manually restart the bot every time the server reboots):

1. **Create service file:**
```bash
sudo nano /etc/systemd/system/vcbot.service
```

2. **Add service configuration:**
```ini
[Unit]
Description=VCBot Discord Bot
After=network.target

[Service]
Type=simple
User=vcbot
WorkingDirectory=/home/vcbot/VCBot
Environment="PATH=/home/vcbot/VCBot/venv/bin"
ExecStart=/home/vcbot/VCBot/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/vcbot.log
StandardError=append:/var/log/vcbot.log

[Install]
WantedBy=multi-user.target
```

3. **Enable and start service:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable vcbot
sudo systemctl start vcbot
```

4. **Check status:**
```bash
sudo systemctl status vcbot
sudo journalctl -u vcbot -f  # Follow logs
```

## Docker Deployment

For those who prefer containerized chaos.

### Dockerfile

```dockerfile
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 vcbot && chown -R vcbot:vcbot /app
USER vcbot

# Run the bot
CMD ["python", "main.py"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  vcbot:
    build: .
    container_name: vcbot
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./Knowledge:/app/Knowledge
      - ./every-vc-bill:/app/every-vc-bill
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Build and Run

```bash
# Build image
docker build -t vcbot:latest .

# Run with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f vcbot

# Stop
docker-compose down
```

## Cloud Deployment

### AWS EC2

1. **Launch EC2 instance:**
   - AMI: Ubuntu 22.04 LTS
   - Instance type: t3.micro (minimum), t3.small (recommended)
   - Security group: Allow SSH (22) only
   - Key pair: Create or use existing

2. **Connect and deploy:**
```bash
ssh -i your-key.pem ubuntu@your-instance-ip
# Follow production deployment steps above
```

3. **Security considerations:**
   - Use security groups to limit access
   - Set up CloudWatch for monitoring
   - Consider Elastic IP for static addressing

### Google Cloud Platform

1. **Create Compute Engine instance:**
```bash
gcloud compute instances create vcbot \
    --machine-type=e2-micro \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --zone=us-central1-a
```

2. **Deploy application:**
```bash
gcloud compute ssh vcbot --zone=us-central1-a
# Follow production deployment steps
```

### DigitalOcean

1. **Create droplet** (Basic $4/month works fine)
2. **SSH and deploy** using production steps
3. **Set up backups** (DigitalOcean has automated options)

### Heroku (Budget Option)

1. **Create Procfile:**
```
worker: python main.py
```

2. **Deploy:**
```bash
heroku create your-vcbot-app
heroku config:set BOT_ID=your_bot_id
heroku config:set DISCORD_TOKEN=your_token
heroku config:set GEMINI_API_KEY=your_key
heroku config:set RECORDS_CHANNEL=your_channel_id
# ... set other required env vars
git push heroku main
heroku ps:scale worker=1
```

**Note**: Heroku's free tier is gone, but the $7/month plan works fine for this bot.

## Configuration Management

### Environment Variables

```bash
# Required (bot won't start without these)
BOT_ID=                    # Your bot's Discord user ID
DISCORD_TOKEN=             # Discord bot token
GEMINI_API_KEY=           # Google Gemini API key
RECORDS_CHANNEL=          # Channel for bill records
NEWS_CHANNEL=             # Channel for news updates
SIGN_CHANNEL=             # Channel for bill signing
CLERK_CHANNEL=            # Channel for clerk operations

# Optional but recommended
GUILD=                    # Your Discord server ID
LOG_LEVEL=INFO           # Logging level (DEBUG, INFO, WARNING, ERROR)
MAX_RETRIES=3            # API retry attempts
TIMEOUT=30               # API timeout in seconds

# File paths (usually defaults are fine)
BILL_REF_FILE=bill_refs.json
NEWS_FILE=news.txt
QUERIES_FILE=queries.csv
```

### Getting Discord IDs

1. Enable Developer Mode: User Settings → Advanced → Developer Mode
2. Right-click on servers/channels/users → "Copy ID"
3. Use these IDs in your configuration

## Monitoring and Maintenance

### Logging

1. **Configure rotating logs:**
The bot automatically sets up rotating log files in the `logs/` directory.

2. **Monitor logs:**
```bash
# Real-time monitoring
tail -f logs/vcbot_*.log

# Search for errors
grep ERROR logs/vcbot_*.log

# Monitor systemd logs
journalctl -u vcbot -f

# Docker logs
docker logs -f vcbot
```

### Health Checks

The bot includes basic health monitoring. You can add external monitoring:

```bash
# Simple uptime check
curl -f http://your-discord-bot-status-url || alert

# Process check
pgrep -f "python main.py" || systemctl restart vcbot
```

### Backup Strategy

1. **Important files to backup:**
   - `bill_refs.json` - Bill reference numbers
   - `queries.csv` - Query history
   - `every-vc-bill/` - Bill database
   - `Knowledge/` - Knowledge base files
   - `.env` - Configuration (keep secure!)

2. **Automated backup script:**
```bash
#!/bin/bash
# backup.sh
BACKUP_DIR="/backup/vcbot"
DATE=$(date +%Y%m%d)

mkdir -p $BACKUP_DIR
cp bill_refs.json $BACKUP_DIR/bill_refs_$DATE.json
cp queries.csv $BACKUP_DIR/queries_$DATE.csv
tar -czf $BACKUP_DIR/bills_$DATE.tar.gz every-vc-bill/

# Keep last 7 days
find $BACKUP_DIR -name "*_*" -mtime +7 -delete
```

3. **Schedule with cron:**
```bash
0 2 * * * /home/vcbot/backup.sh
```

## Troubleshooting

### Common Issues

1. **Bot not connecting:**
   - Verify Discord token is correct and not expired
   - Check network connectivity
   - Ensure bot has proper permissions in Discord
   - Check if Discord is having outages

2. **High memory usage:**
   - Monitor with `htop` or `top`
   - The AI models can use significant RAM
   - Consider upgrading to more RAM
   - Check for memory leaks in logs

3. **API rate limits:**
   - Gemini API has generous free limits but they exist
   - Implement exponential backoff (already built-in)
   - Monitor API usage in Google Cloud Console
   - Consider upgrading API plan for heavy usage

4. **Commands not syncing:**
   - Set `GUILD` environment variable to your server ID
   - Wait up to an hour for global command sync
   - Check bot permissions in Discord
   - Verify bot is in the server

5. **Permission errors:**
   - Ensure bot has required Discord permissions
   - Check file permissions for data directories
   - Verify systemd service user has access

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
# In .env file
LOG_LEVEL=DEBUG

# Or temporarily
LOG_LEVEL=DEBUG python main.py
```

### Performance Tuning

1. **Memory optimization:**
   - Limit cache sizes in the code
   - Monitor for memory leaks
   - Use swap space on smaller instances

2. **Network optimization:**
   - Use connection keep-alive (already implemented)
   - Monitor API response times
   - Consider CDN for static assets if needed

3. **Database optimization:**
   - The bot uses JSON files, but you could migrate to PostgreSQL
   - Implement connection pooling for database version
   - Regular maintenance and cleanup

## Security Considerations

1. **Secure secrets:**
   - Never commit `.env` files to git
   - Use environment variables or secret management services
   - Rotate API keys regularly
   - Limit bot permissions to minimum required

2. **Network security:**
   - Use firewall rules to limit access
   - Implement rate limiting (built into the bot)
   - Monitor for suspicious activity
   - Keep server updated

3. **Discord security:**
   - Use role-based permissions
   - Monitor bot usage logs
   - Regularly audit bot permissions
   - Watch for unauthorized command usage

4. **Regular updates:**
   - Keep dependencies updated
   - Monitor security advisories
   - Update the bot code regularly
   - Security audit logging

## Scaling

### When to Scale

Scale up when you see:
- Consistent high CPU usage (>80%)
- Memory constraints causing crashes
- Slow response times
- API rate limit errors

### Horizontal Scaling

For multiple instances (if your Discord server gets that busy):

1. **Shared state:**
   - Move to Redis or database for session storage
   - Implement distributed locking for bill references
   - Use central configuration management

2. **Load balancing:**
   - Use Discord sharding for large servers
   - Implement queue-based processing
   - Monitor instance health

### Vertical Scaling

Easier approach for most cases:
- Upgrade to larger instance
- Add more RAM (AI models love RAM)
- Faster CPU for quicker responses
- SSD storage for better I/O

## Cost Considerations

### API Costs
- **Google Gemini**: Generous free tier, pay-per-token after
- **Discord**: Free API usage
- **Server costs**: $4-20/month depending on provider and size

### Optimization Tips
- Monitor Gemini token usage
- Cache frequent queries
- Use smaller models for simple tasks
- Implement smart rate limiting

---

Remember: This is a hobby project that got way too complex. Don't stress if something breaks - just check the logs, restart it, and blame the AI.

For additional support, consult the project documentation, check the logs, or create an issue on GitHub.