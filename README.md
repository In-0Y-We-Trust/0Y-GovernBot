# 0Y Governance Bot

A Telegram bot that helps users track and receive updates on DAO governance proposals via the Tally API. Currently available at: https://t.me/Governor0Y_test_bot

## Features

- Subscribe to multiple DAOs to monitor their governance activities
- Receive real-time notifications when new proposals are created
- Get alerts when proposal statuses change
- View recent proposals for your subscribed DAOs
- Search for DAOs with fuzzy matching for easier discovery

## Requirements

- Python 3.8+
- Telegram Bot Token
- Tally API Key

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/0y-governance-bot.git
cd 0y-governance-bot
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root with the following content:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TALLY_API_KEY=your_tally_api_key
```

## Usage

1. Start the bot:
```bash
python main.py
```

2. In Telegram, start a conversation with your bot and use the following commands:

- `/start` - Initialize the bot
- `/subscribe` - Subscribe to a DAO (you'll be prompted to enter the DAO slug, you can find supported DAOs and their slugs at https://www.tally.xyz/ )
- `/unsubscribe` - Unsubscribe from a DAO
- `/my_subscriptions` - View your current DAO subscriptions
- `/recent_proposals` - Check recent proposals from your subscribed DAOs
- `/help` - Show the help message

## How It Works

The bot connects to the Tally API to fetch information about DAOs and their proposals. It maintains a local SQLite database to store user subscriptions and proposal statuses.

When a user subscribes to a DAO, the bot starts monitoring that DAO's proposals. It periodically checks for updates and sends notifications when:
- A new proposal is created
- The status of an existing proposal changes

## Configuration

You can modify the following constants in `main.py` to adjust the bot's behavior:

- `MAX_SUBSCRIPTIONS` - Maximum number of DAOs a user can subscribe to (default: 10)
- `MAX_PROPOSALS` - Number of proposals to show in the `/recent_proposals` command (default: 5)
- `TRACKED_PROPOSALS_PER_DAO` - Number of proposals to track for each DAO (default: 20)
- `DAO_UPDATE_INTERVAL` - How often to update the DAO list in seconds (default: 3600 seconds / 1 hour)
- `CACHE_EXPIRY` - How long to keep the DAO cache before refreshing (default: 240 hours / 10 days)

## Development

The bot uses the `python-telegram-bot` library to interact with the Telegram API and makes GraphQL queries to the Tally API.

Key components:
- `Database` class - Handles SQLite database operations
- `UserState` class - Manages user subscription state
- `fetch_tally_data()` - Makes requests to the Tally API
- `check_proposal_updates()` - Periodic job that checks for proposal updates

## Contributing

Contributions(and fixes:) are welcome, please feel free to submit a Pull Request.

## License

[MIT License](LICENSE)

## Acknowledgements

- [Tally](https://www.tally.xyz/) for providing the API to access DAO governance data
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) for the Telegram bot framework
- [fuzzywuzzy](https://github.com/seatgeek/fuzzywuzzy) for fuzzy string matching
