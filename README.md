# 0Y GovernBot (Governor Bot)

A Telegram bot that helps users track and receive updates on DAO governance proposals via the Tally API. 

**Live Bot**: [@Governor0Y_test_bot](https://t.me/Governor0Y_test_bot)

## Features

- Subscribe to multiple DAOs to monitor their governance activities
- Receive real-time notifications when new proposals are created
- Get alerts when proposal statuses change
- View recent proposals for your subscribed DAOs
- Search for DAOs with fuzzy matching for easier discovery

## Quick Start

For experienced developers:

```bash
# Install dependencies
sudo apt update && sudo apt install build-essential python3-dev python3.12-venv git

# Clone and setup
git clone https://github.com/In-0Y-We-Trust/0Y-GovernBot.git
cd 0y-governance-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env  # Edit with your tokens
python main.py
```

## Prerequisites

### System Requirements
- Ubuntu 20.04+ (or similar Linux distribution)
- Python 3.8+
- Git
- Build tools for compiling Python packages

### API Keys Required
- **Telegram Bot Token**: Get from [@BotFather](https://t.me/BotFather) on Telegram
- **Tally API Key**: Request from [Tally.xyz](https://www.tally.xyz/)

### Install System Dependencies

```bash
# Update package manager
sudo apt update

# Install required packages
sudo apt install build-essential python3-dev python3.12-venv git

# Optional: Install additional tools
sudo apt install htop curl wget nano
```

## Obtaining API Keys

### 1. Telegram Bot Token

1. Start a chat with [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Follow the prompts to name your bot
4. Save the token provided (format: `123456789:ABCdefGhIJKlmNoPQRSTUVwxyZ`)

### 2. Tally API Key

1. Visit [Tally.xyz](https://www.tally.xyz/)
2. Contact their support or check their developer documentation
3. Request API access for your bot
4. Save the API key provided

## Development Setup

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/0y-governance-bot.git
cd 0y-governance-bot
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate
```

### 3. Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt

# If you encounter compilation errors, ensure build tools are installed:
sudo apt install build-essential python3-dev
```

### 4. Configure Environment

```bash
# Create environment file
cp .env.example .env

# Edit with your actual tokens
nano .env
```

Add your tokens to `.env`:
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TALLY_API_KEY=your_tally_api_key_here
```

Secure the file:
```bash
chmod 600 .env
```

### 5. Test the Bot

```bash
python main.py
```

Test by sending `/start` to your bot on Telegram. Press `Ctrl+C` to stop.

## Production Deployment

### Single Instance Setup

For a simple deployment:

```bash
# Create deployment directory
sudo mkdir -p /opt/telegram-bots/main-bot
sudo chown -R $USER:$USER /opt/telegram-bots/

# Copy files
cp -r * /opt/telegram-bots/main-bot/
cd /opt/telegram-bots/main-bot

# Setup virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Multiple Instance Setup

To run both test and production bots:

```bash
# Create directories
sudo mkdir -p /opt/telegram-bots/{test-bot,main-bot}
sudo chown -R $USER:$USER /opt/telegram-bots/

# Setup main bot
cd /opt/telegram-bots/main-bot
git clone https://github.com/In-0Y-We-Trust/0Y-GovernBot.git
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create separate .env with different bot token
nano .env
```

### Systemd Service Setup

Create a systemd service for automatic startup and management:

```bash
sudo nano /etc/systemd/system/telegram-bot-main.service
```

Add this content (replace `your-username` with your actual username):

```ini
[Unit]
Description=Telegram GovernBot Main Instance
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/opt/telegram-bots/main-bot
Environment=PATH=/opt/telegram-bots/main-bot/venv/bin
ExecStart=/opt/telegram-bots/main-bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot-main.service
sudo systemctl start telegram-bot-main.service

# Check status
sudo systemctl status telegram-bot-main.service
```

## Bot Commands

Once running, users can interact with these commands:

- `/start` - Initialize the bot
- `/subscribe` - Subscribe to a DAO (enter DAO slug when prompted)
- `/unsubscribe` - Unsubscribe from a DAO
- `/my_subscriptions` - View your current DAO subscriptions
- `/recent_proposals` - Check recent proposals from subscribed DAOs
- `/help` - Show help message

**Finding DAO slugs**: Browse [Tally.xyz](https://www.tally.xyz/) to find DAOs and their slugs (e.g., `uniswap`, `compound`, `aave`).

## Configuration

Modify these constants in `main.py` to adjust bot behavior:

```python
MAX_SUBSCRIPTIONS = 10              # Max DAOs per user
MAX_PROPOSALS = 5                   # Proposals shown in /recent_proposals
TRACKED_PROPOSALS_PER_DAO = 20      # Proposals monitored per DAO
DAO_UPDATE_INTERVAL = 3600          # DAO list update interval (seconds)
CACHE_EXPIRY = timedelta(hours=240) # Cache expiration time
```

## Management Commands

### Service Management

```bash
# Check status
sudo systemctl status telegram-bot-main.service

# View logs
sudo journalctl -u telegram-bot-main.service -f

# Restart bot
sudo systemctl restart telegram-bot-main.service

# Stop bot
sudo systemctl stop telegram-bot-main.service
```

### Updates

```bash
# Stop the service
sudo systemctl stop telegram-bot-main.service

# Navigate to bot directory
cd /opt/telegram-bots/main-bot

# Pull latest changes
git pull origin main

# Update dependencies if needed
source venv/bin/activate
pip install -r requirements.txt

# Start the service
sudo systemctl start telegram-bot-main.service
```

### Backups

```bash
# Create backup directory
mkdir -p /opt/backups/telegram-bots

# Backup database (add to crontab for automation)
cp /opt/telegram-bots/main-bot/tally-bot.db /opt/backups/telegram-bots/main-bot-$(date +%Y%m%d).db

# Backup DAO cache
cp /opt/telegram-bots/main-bot/dao_cache.json /opt/backups/telegram-bots/dao_cache-$(date +%Y%m%d).json
```

## Troubleshooting

### Common Issues

#### "Could not build wheels for Levenshtein"
```bash
sudo apt install build-essential python3-dev
pip install -r requirements.txt
```

#### "No JobQueue set up" Error
```bash
pip install "python-telegram-bot[job-queue]"
```

#### "429 Too Many Requests" from Tally API
- Stop other bot instances temporarily
- Copy `dao_cache.json` from existing instance
- Wait before restarting (rate limit resets)

#### Permission Denied Errors
```bash
sudo chown -R $USER:$USER /opt/telegram-bots/
chmod 600 .env
chmod +x venv/bin/python
```

#### Bot Not Responding
```bash
# Check logs
sudo journalctl -u telegram-bot-main.service -f

# Verify .env file exists and has correct tokens
cat .env

# Test API connection
python -c "import requests; print(requests.get('https://api.telegram.org/bot<YOUR_TOKEN>/getMe').json())"
```

### Performance Optimization

#### Using DAO Cache
- Copy `dao_cache.json` between instances to avoid API calls
- Cache expires after 240 hours by default
- Significantly reduces startup time

#### Rate Limiting
- Stagger multiple bot startups
- Don't run identical bots simultaneously during startup
- Consider increasing retry delays in `fetch_tally_data()`

## Security Considerations

1. **Protect Environment Files**:
   ```bash
   chmod 600 .env
   ```

2. **Use Non-Root User**: Run bots as a dedicated user, not root

3. **Firewall Configuration**: Ensure only necessary ports are open

4. **Regular Updates**: Keep dependencies and system packages updated

5. **Monitor Logs**: Set up log monitoring for suspicious activity

## Development

### Project Structure

```
├── main.py              # Main bot application
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (not in git)
├── .env.example        # Environment template
├── dao_cache.json      # Cached DAO list (auto-generated)
├── tally-bot.db        # SQLite database (auto-generated)
└── README.md           # This file
```

### Key Components

- **Database Class**: Handles SQLite operations for users and proposals
- **UserState Class**: Manages user subscription state
- **fetch_tally_data()**: Makes GraphQL requests to Tally API
- **check_proposal_updates()**: Periodic job monitoring proposal changes

### Adding Features

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Requirements

Current dependencies in `requirements.txt`:

```txt
python-telegram-bot[job-queue]==20.7
requests==2.31.0
fuzzywuzzy==0.18.0
python-dotenv==1.0.0
python-Levenshtein==0.21.1
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request. (However, it might take a while for us to actually review it, honestly)

## License

[MIT License](LICENSE)

## Acknowledgements

- [Tally](https://www.tally.xyz/) for providing the API to access DAO governance data
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) for the Telegram bot framework
- [fuzzywuzzy](https://github.com/seatgeek/fuzzywuzzy) for fuzzy string matching

## Support

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review the logs: `sudo journalctl -u telegram-bot-main.service -f`
3. Open an issue on GitHub with detailed error information. (We might try to fix it, but most likely, you are better off fixing it yourself with some LLM magic or, you know, hiring a real dev)
4. For Tally API issues, contact Tally support directly
