import os
import logging
import json
import time
import sqlite3
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
    MenuButtonCommands,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import requests
from datetime import datetime, timedelta
from fuzzywuzzy import process
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Initialize bot
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")

TALLY_API_KEY = os.getenv("TALLY_API_KEY")
if not TALLY_API_KEY:
    raise ValueError("TALLY_API_KEY not found in environment variables")

TALLY_API_URL = "https://api.tally.xyz/query"

# Constants
MAX_SUBSCRIPTIONS = 10
MAX_PROPOSALS = 5
TRACKED_PROPOSALS_PER_DAO = 20
DAO_UPDATE_INTERVAL = 3600  # Update the DAO list every hour
DAO_CACHE_FILE = "dao_cache.json"
CACHE_EXPIRY = timedelta(hours=240)

# Conversation states
WAITING_FOR_DAO_SLUG, CONFIRM_SUBSCRIPTION = range(2)

ALL_DAOS = []


class UserState:
    def __init__(self, json_data=None):
        if json_data is not None:
            self.subscriptions = json_data["subscriptions"]
        else:
            self.subscriptions = []

    def get_json(self):
        return {"subscriptions": self.subscriptions}

    def subscribe(self, dao_slug: str):
        self.subscriptions.append(dao_slug)

    def unsubscribe(self, dao_slug: str):
        self.subscriptions.remove(dao_slug)


db = None


class Database:
    def __init__(self, db_name: str):
        self.connection = sqlite3.connect(db_name)
        self.cursor = self.connection.cursor()
        self._create_tables()

    def _create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                state TEXT
            );
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS proposals (
                id INTEGER PRIMARY KEY,
                status TEXT
            );
        """)
        self.connection.commit()

    def read_user_state(self, user_id: str):
        self.cursor.execute("SELECT state FROM users WHERE id = :id", {"id": user_id})
        row = self.cursor.fetchone()
        if row is None:
            logger.error(f"Failed to fetch user state: ")
            return
        return UserState(json_data=json.loads(row[0]))

    def write_user_state(self, user_id: str, state: UserState):
        logger.info(f"STATE: {state.get_json()}")
        self.cursor.execute(
            "INSERT OR REPLACE INTO users VALUES (:id, :state)",
            {
                "id": user_id,
                "state": json.dumps(state.get_json()),
            },
        )
        self.connection.commit()

    # Returns mapping of dao_slug to list of subscribed users
    def read_all_subscriptions(self):
        self.cursor.execute("SELECT id,state FROM users")
        subscriptions = {}
        for row in self.cursor.fetchall():
            state = UserState(json_data=json.loads(row[1]))
            for sub in state.subscriptions:
                if sub in subscriptions:
                    subscriptions[sub].append(row[0])
                else:
                    subscriptions[sub] = [row[0]]
        return subscriptions

    def read_all_proposals(self):
        self.cursor.execute("SELECT id, status FROM proposals")
        proposals = {}
        for row in self.cursor.fetchall():
            proposals[row[0]] = row[1]
        return proposals

    def write_proposal(self, proposal_id, proposal_status):
        self.cursor.execute(
            "INSERT OR REPLACE INTO proposals VALUES (:id, :status)",
            {
                "id": proposal_id,
                "status": proposal_status,
            },
        )
        self.connection.commit()


FALLBACK_DAOS = [
    {"id": "1", "name": "Uniswap", "slug": "uniswap"},
    {"id": "2", "name": "Compound", "slug": "compound"},
    {"id": "3", "name": "Aave", "slug": "aave"},
    {"id": "4", "name": "MakerDAO", "slug": "makerdao"},
    {"id": "5", "name": "Curve", "slug": "curve"},
]


def fetch_tally_data(query, variables=None, max_retries=3, retry_delay=5):
    headers = {"Content-Type": "application/json", "Api-Key": TALLY_API_KEY}
    data = {"query": query, "variables": variables}

    for attempt in range(max_retries):
        try:
            response = requests.post(
                TALLY_API_URL, json=data, headers=headers, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(
                f"API request failed (attempt {attempt + 1}/{max_retries}): {str(e)}"
            )
            if response.text:
                logger.error(f"Response content: {response.text}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error(
                    "Max retries reached. Unable to fetch data from Tally API."
                )
                return None


def find_dao_by_slug(slug):
    dao_cache = load_dao_cache()
    if not dao_cache:
        return None

    dao = next((dao for dao in dao_cache if dao["slug"].lower() == slug.lower()), None)
    if dao:
        logger.info(f"Found DAO in cache: {dao['name']}")
        return dao


def load_dao_cache():
    logger.info(f"Loading DAO cache from {DAO_CACHE_FILE}")
    if os.path.exists(DAO_CACHE_FILE):
        with open(DAO_CACHE_FILE, "r") as f:
            cache = json.load(f)
        if datetime.now() - datetime.fromisoformat(cache["timestamp"]) < CACHE_EXPIRY:
            return cache["daos"]
    return None


def save_dao_cache(daos):
    cache = {"timestamp": datetime.now().isoformat(), "daos": daos}
    with open(DAO_CACHE_FILE, "w") as f:
        json.dump(cache, f)


def get_dao_info(slug):
    # First, try to find the DAO in the cached list
    dao = next((dao for dao in ALL_DAOS if dao["slug"].lower() == slug.lower()), None)
    if dao:
        logger.info(f"Found DAO in cache: {dao['name']}")
        return dao

    # If not found in cache, try to fetch from API
    query = """
    query($input: OrganizationInput!) {
        organization(input: $input) {
            id
            name
            slug
            chainIds
            governorIds
            tokenIds
        }
    }
    """
    variables = {"input": {"slug": slug}}
    result = fetch_tally_data(query, variables)
    if result and "data" in result and "organization" in result["data"]:
        return result["data"]["organization"]

    logger.warning(f"DAO info not found for slug: {slug}")
    return None


def get_recent_proposals(org_id, limit=MAX_PROPOSALS):
    query = """
    query($input: ProposalsInput!) {
        proposals(input: $input) {
            nodes {
                ... on Proposal {
                    id
                    status

                    start {
                        ... on Block {
                            timestamp
                        }
                        ... on BlocklessTimestamp {
                            timestamp
                        }
                    }
                    end {
                        ... on Block {
                            timestamp
                        }
                        ... on BlocklessTimestamp {
                            timestamp
                        }
                    }

                    metadata {
                        title
                    }

                    organization {
                        name
                        slug
                    }
                }
            }
            pageInfo {
                lastCursor
                count
            }
        }
    }
    """
    variables = {
        "input": {
            "filters": {"organizationId": org_id},
            "sort": {"sortBy": "id", "isDescending": True},
            "page": {"limit": limit},
        }
    }
    result = fetch_tally_data(query, variables)
    if result and "data" in result and "proposals" in result["data"]:
        proposals = result["data"]["proposals"]["nodes"]
        logger.info(f"Fetched {len(proposals)} proposals for org_id: {org_id}")
        return proposals
    logger.warning(f"No proposals found for org_id: {org_id}")
    return []


def fetch_all_daos():
    cached_daos = load_dao_cache()
    if cached_daos:
        logger.info(f"Using cached DAO list with {len(cached_daos)} DAOs")
        return cached_daos

    query = """
    query($input: OrganizationsInput!) {
        organizations(input: $input) {
            nodes {
                ... on Organization {
                    id
                    name
                    slug
                    hasActiveProposals
                    proposalsCount
                    delegatesCount
                    delegatesVotesCount
                }
            }
            pageInfo {
                lastCursor
                count
            }
        }
    }
    """
    variables = {"input": {"sort": {"sortBy": "id", "isDescending": True}, "page": {}}}

    all_daos = []
    last_cursor = None

    while True:
        if last_cursor:
            variables["input"]["page"]["afterCursor"] = last_cursor

        result = fetch_tally_data(query, variables)
        logger.info(result)
        if result and "data" in result and "organizations" in result["data"]:
            daos = result["data"]["organizations"]["nodes"]
            all_daos.extend(daos)

            page_info = result["data"]["organizations"]["pageInfo"]
            last_cursor = page_info["lastCursor"]

            # The last page would have empty cursor
            if len(last_cursor) == 0:
                break
        else:
            logger.error("Failed to fetch DAOs from API")
            break
        time.sleep(1)

    if all_daos:
        logger.info(f"Fetched {len(all_daos)} DAOs from API")
        save_dao_cache(all_daos)
        return all_daos

    logger.error("No DAOs fetched from API")
    return []


def update_dao_list(context: ContextTypes.DEFAULT_TYPE):
    global ALL_DAOS
    ALL_DAOS = fetch_all_daos()
    logger.info(f"Updated DAO list. Total DAOs: {len(ALL_DAOS)}")


def find_closest_dao(input_slug):
    global ALL_DAOS
    if not ALL_DAOS:
        ALL_DAOS = fetch_all_daos()

    dao_slugs = [dao["slug"] for dao in ALL_DAOS]
    closest_match, score = process.extractOne(input_slug, dao_slugs)

    logger.info(
        f"Closest match for '{input_slug}' is '{closest_match}' with score {score}"
    )
    if score >= 60:  # Lowered threshold to 60
        return next((dao for dao in ALL_DAOS if dao["slug"] == closest_match), None)
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome to 0Y Governance Bot, powered by Tally API. Use the menu or type commands to interact."
    )


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_chat.id

    user_state = db.read_user_state(user_id)
    if user_state is not None and len(user_state.subscriptions) >= MAX_SUBSCRIPTIONS:
        await update.message.reply_text(
            f"You've reached the maximum number of subscriptions ({MAX_SUBSCRIPTIONS}). Please unsubscribe from a DAO before adding a new one."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "Please enter the DAO slug you want to subscribe to:"
    )
    return WAITING_FOR_DAO_SLUG


async def process_dao_slug(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    dao_slug = update.message.text.strip().lower()
    context.user_data["temp_dao_slug"] = dao_slug

    logger.info(f"Processing DAO slug: {dao_slug}")
    dao_info = find_dao_by_slug(dao_slug)

    if dao_info:
        logger.info(f"Found DAO: {dao_info['name']}")
        await update.message.reply_text(
            f"Do you want to subscribe to {dao_info['name']} (slug: {dao_slug})?\n"
            "Please reply with 'yes' or 'no'."
        )
        return CONFIRM_SUBSCRIPTION
    else:
        logger.info(f"DAO not found, trying fuzzy match for: {dao_slug}")
        closest_dao = find_closest_dao(dao_slug)
        if closest_dao:
            logger.info(f"Found closest match: {closest_dao['name']}")
            context.user_data["temp_dao_slug"] = closest_dao["slug"]
            await update.message.reply_text(
                f"I couldn't find '{dao_slug}'. Did you mean '{closest_dao['name']}' (slug: {closest_dao['slug']})?\n"
                "Do you want to subscribe to this DAO? Please reply with 'yes' or 'no'."
            )
            return CONFIRM_SUBSCRIPTION
        else:
            logger.warning(f"No match found for: {dao_slug}")
            await update.message.reply_text(
                f"Sorry, I couldn't find a DAO with the slug '{dao_slug}'. "
                "The Tally API might be experiencing issues. Please try again later or check the slug."
            )
            return WAITING_FOR_DAO_SLUG


async def confirm_subscription(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    user_response = update.message.text.strip().lower()
    user_id = update.effective_chat.id
    dao_slug = context.user_data["temp_dao_slug"]

    if user_response == "yes":
        user_state = db.read_user_state(user_id)

        if user_state is not None and dao_slug in user_state.subscriptions:
            await update.message.reply_text(f"You're already subscribed to {dao_slug}")
            return

        if user_state is None:
            user_state = UserState()

        user_state.subscribe(dao_slug)

        all_subcriptions = db.read_all_subscriptions()
        # For new subscriptions we need to initialize base states of proposals
        if dao_slug not in all_subcriptions:
            dao_info = get_dao_info(dao_slug)
            proposals = get_recent_proposals(dao_info["id"], limit=TRACKED_PROPOSALS_PER_DAO)
            for prop in proposals:
                db.write_proposal(int(prop["id"]), prop["status"])

        db.write_user_state(user_id, user_state)

        dao_info = get_dao_info(dao_slug)
        await update.message.reply_text(
            f"You've successfully subscribed to {dao_info['name']} (slug: {dao_slug})!"
        )
    else:
        await update.message.reply_text("Subscription cancelled.")

    del context.user_data["temp_dao_slug"]
    return ConversationHandler.END


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_chat.id

    global db
    user_state = db.read_user_state(user_id)
    if user_state is None or not user_state.subscriptions:
        await update.message.reply_text("You're not subscribed to any DAOs.")
        return

    keyboard = [
        [InlineKeyboardButton(slug, callback_data=f"unsub_{slug}")]
        for slug in user_state.subscriptions
    ]
    keyboard.append([InlineKeyboardButton("Cancel", callback_data="unsub_cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Select a DAO to unsubscribe from:", reply_markup=reply_markup
    )


async def unsubscribe_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()

    user_id = update.effective_chat.id
    data = query.data

    if data == "unsub_cancel":
        await query.edit_message_text("Unsubscribe cancelled.")
        return

    dao_slug = data.split("_")[1]
    user_state = db.read_user_state(user_id)
    if user_state is not None and dao_slug in user_state.subscriptions:
        user_state.unsubscribe(dao_slug)
        db.write_user_state(user_id, user_state)
        await query.edit_message_text(
            f"You've successfully unsubscribed from {dao_slug}."
        )
    else:
        await query.edit_message_text(f"You weren't subscribed to {dao_slug}.")


async def my_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_state = db.read_user_state(user_id)
    if user_state is None or len(user_state.subscriptions) == 0:
        await update.message.reply_text("You're not subscribed to any DAOs.")
    else:
        subscriptions = "\n".join(user_state.subscriptions)
        await update.message.reply_text(f"Your subscriptions:\n{subscriptions}")


async def recent_proposals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    logger.info(f"CHAT ID {update.effective_chat.id}")
    user_state = db.read_user_state(user_id)
    if user_state is None or len(user_state.subscriptions) == 0:
        await update.message.reply_text(
            "You're not subscribed to any DAOs. Use /subscribe to add a DAO."
        )
        return

    for dao_slug in user_state.subscriptions:
        dao_info = get_dao_info(dao_slug)
        if not dao_info:
            await update.message.reply_text(
                f"Couldn't fetch information for {dao_slug}."
            )
            continue

        proposals = get_recent_proposals(dao_info["id"])
        logger.info(f"proposals {json.dumps(proposals)}")
        if proposals:
            message = f"Recent proposals for {dao_info['name']}:\n\n"
            for prop in proposals:
                message += format_proposal(prop, dao_info['slug']) + "\n\n"
        else:
            message = f"No recent proposals found for {dao_info['name']}."

        await update.message.reply_text(message, parse_mode='Markdown')


def format_proposal(prop, dao_slug):
    try:
        start_time = datetime.fromisoformat(
            prop["start"]["timestamp"]
        ).strftime("%Y-%m-%d %H:%M:%S UTC")
        end_time = datetime.fromisoformat(
            prop["end"]["timestamp"]
        ).strftime("%Y-%m-%d %H:%M:%S UTC")
        return (
            f"- **{prop['metadata']['title']}**\n"
            f"  Status: {prop['status']}\n"
            f"  Start: {start_time}\n"
            f"  End: {end_time}\n"
            f"  Link: https://www.tally.xyz/gov/{dao_slug}/proposal/{prop['id']}"
        )
    except KeyError as e:
        logger.error(f"Error processing proposal: {e}")
        logger.error(f"Proposal data: {prop}")
        return f"- Error processing proposal {prop.get('id', 'Unknown ID')}"


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """
    Available commands:
    /start - Start the bot
    /subscribe - Subscribe to a DAO
    /unsubscribe - Unsubscribe from a DAO
    /my_subscriptions - View your current subscriptions
    /recent_proposals - Check recent proposals
    /help - Show this help message
    """
    await update.message.reply_text(help_text)


async def setup_commands_and_menu(application: Application) -> None:
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("subscribe", "Subscribe to a DAO"),
        BotCommand("unsubscribe", "Unsubscribe from a DAO"),
        BotCommand("my_subscriptions", "View your current subscriptions"),
        BotCommand("recent_proposals", "Check recent proposals"),
        BotCommand("help", "Show help message"),
    ]

    await application.bot.set_my_commands(commands)
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())


async def check_proposal_updates(application: Application):
    global db

    subscriptions = db.read_all_subscriptions()
    all_proposals = db.read_all_proposals()
    logger.info(f"Checking dao subscriptions {subscriptions}")
    logger.info(f"All proposals {all_proposals}")
    for dao_slug, chat_ids in subscriptions.items():
        dao_info = get_dao_info(dao_slug)
        if not dao_info:
            logger.error(f"Failed to fetch DAO info for {dao_slug}")
            continue

        proposals = get_recent_proposals(dao_info["id"], limit=TRACKED_PROPOSALS_PER_DAO)
        for proposal in proposals:
            proposal_id = int(proposal["id"])
            if proposal_id in all_proposals:
                if all_proposals[proposal_id] != proposal["status"]:
                    db.write_proposal(proposal_id, proposal["status"])
                    message = "🔄 Status changed\n\n" + format_proposal(proposal, dao_info["slug"])
                    for chat_id in chat_ids:
                        logger.info(f"Sending proposal status changed notification to {chat_id}")
                        await application.bot.send_message(
                            chat_id, message
                        )
            else:
                db.write_proposal(proposal_id, proposal["status"])
                message = "🆕🆕🆕\n\n" + format_proposal(proposal, dao_info["slug"])
                for chat_id in chat_ids:
                    logger.info(f"Sending new proposal notification to {chat_id}")
                    await application.bot.send_message(
                        chat_id, message
                    )
                


def test_api_connection():
    query = """
    query {
        chains {
            id
            name
        }
    }
    """
    result = fetch_tally_data(query)
    if result and "data" in result and "chains" in result["data"]:
        logger.info("API connection successful")
        logger.info(f"Chains: {result['data']['chains']}")
    else:
        logger.error("API connection failed")
        if result:
            if "errors" in result:
                logger.error(f"API errors: {json.dumps(result['errors'], indent=2)}")
            else:
                logger.error(f"Unexpected API response: {json.dumps(result, indent=2)}")
        else:
            logger.error("No response from API")


def main() -> None:
    test_api_connection()  # Test API connection before starting

    global db
    db = Database("tally-bot.db")
    db.write_user_state("1", UserState({"subscriptions": []}))
    db.read_user_state("1")

    global ALL_DAOS
    ALL_DAOS = fetch_all_daos()
    if not ALL_DAOS:
        logger.warning(
            "Failed to fetch DAOs from API and no cache available. Using fallback list."
        )
        ALL_DAOS = FALLBACK_DAOS
    logger.info(f"Initialized with {len(ALL_DAOS)} DAOs")

    application = Application.builder().token(TOKEN).build()

    # Set up commands and menu
    application.job_queue.run_once(setup_commands_and_menu, when=0)

    application.job_queue.run_repeating(check_proposal_updates, 10)

    # Update DAO list periodically
    # application.job_queue.run_repeating(
    #     update_dao_list, interval=DAO_UPDATE_INTERVAL, first=0
    # )

    # Set up conversation handler for subscribing
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("subscribe", subscribe)],
        states={
            WAITING_FOR_DAO_SLUG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_dao_slug)
            ],
            CONFIRM_SUBSCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_subscription)
            ],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))
    application.add_handler(CommandHandler("my_subscriptions", my_subscriptions))
    application.add_handler(CommandHandler("recent_proposals", recent_proposals))
    application.add_handler(conv_handler)
    application.add_handler(
        CallbackQueryHandler(unsubscribe_callback, pattern="^unsub_")
    )

    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
