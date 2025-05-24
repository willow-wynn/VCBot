# VCBot - A Discord Bot for Virtual Congress

Just a hobby bot for the Virtual Congress Discord server. It answers questions, searches bills, and keeps track of bill numbers.

## What It Does

- **AI Helper**: Uses Google Gemini to answer questions about Virtual Congress
- **Bill Search**: Finds bills using keyword search through titles and content
- **Reference Tracking**: Keeps track of bill numbers (HR 123, S 456, etc.)
- **Economic Impact Reports**: Generates detailed economic analysis for bills
- **Bill Management**: Adds new bills to the corpus with PDF handling

## The Claude Refactor Story

This bot was originally cobbled together by a human (as hobby projects often are). Then Claude (that's me, an AI assistant) came in and refactored the whole thing in a marathon coding session. I added:

- Proper service layers (because separation of concerns is nice)
- A repository pattern (for when this inevitably needs a real database)
- Async/await everywhere (gotta go fast)
- 131 unit tests (though 8 are skipped because Discord.py is weird about testing)
- Way too much documentation for a hobby project
- A tool registry system (because why not make it even more complex?)

Is it overengineered for a Discord bot? Probably. But hey, it works!

## Admin Setup Guide (The Important Stuff)

### Prerequisites

You need these installed on your machine:

- **Python 3.12+** (tested on 3.12.3, but 3.8+ should work)
- **Git** (for cloning and version control)
- **At least 4GB RAM** (2GB minimum, but the AI models are hungry)
- **500MB disk space** (for the bot and bill database)

### Step 1: Clone and Setup

```bash
git clone https://github.com/willow-wynn/VCBot.git
cd VCBot

# Create virtual environment (highly recommended)
python -m venv venv

# Activate it
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Get Your API Keys

#### Discord Bot Token
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application or select existing one
3. Go to "Bot" section → Reset Token → Copy it
4. **IMPORTANT**: Enable "Message Content Intent" under Privileged Gateway Intents
5. Invite bot to your server with Administrator permissions (or at least Read/Send Messages)

#### Google Gemini API Key
1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key → Copy it
3. Note: Free tier has generous limits, but watch your usage

#### Getting Discord IDs
1. Enable Developer Mode: User Settings → Advanced → Developer Mode
2. Right-click channels/users → "Copy ID"
3. You'll need IDs for specific channels (see .env setup below)

### Step 3: Configure Environment

Create a `.env` file in the root directory:

```env
# Required - Bot won't start without these
BOT_ID=your_bot_user_id_here
DISCORD_TOKEN=your_discord_bot_token_here
GEMINI_API_KEY=your_gemini_api_key_here

# Channel Configuration - Get these by right-clicking channels
RECORDS_CHANNEL=1234567890123456789
NEWS_CHANNEL=1234567890123456789
SIGN_CHANNEL=1234567890123456789
CLERK_CHANNEL=1234567890123456789

# Optional but recommended
GUILD=1234567890123456789  # Your server ID for faster command sync
LOG_LEVEL=INFO             # DEBUG for troubleshooting

# File paths (defaults usually work fine)
BILL_REF_FILE=bill_refs.json
NEWS_FILE=news.txt
QUERIES_FILE=queries.csv
```

### Step 4: Run It

```bash
python main.py
```

If everything's set up right, you should see:
```
INFO - Starting VCBot...
INFO - Logged in as YourBotName#1234
INFO - Commands synced: X commands
```

## Commands

### User Commands (Anyone Can Use)
- `/helper [question]` - Ask the AI anything about Virtual Congress
- `/bill_keyword_search [query]` - Search for bills by keyword

### Privileged Commands (Role-Based Access)
- `/reference [link] [type]` - Reference a new bill (HR, HRES, HJRES, HCONRES)
- `/modifyrefs [number] [type]` - Modify reference numbers (Admin/Clerk only)
- `/add_bill [link]` - Add a bill to the database (Admin only)
- `/econ_impact_report [bill_link]` - Generate economic impact report (Admin/Events Team)
- `/role [users] [role]` - Manage user roles (prefix with `-` to remove)

### Bill Types Supported
- `hr` - House Bill
- `hres` - House Resolution  
- `hjres` - House Joint Resolution
- `hconres` - House Concurrent Resolution

## The Overengineered Architecture

```
Discord Commands → Services → Repositories → JSON files
                     ↓
                Google Gemini ← Tools Registry → Knowledge Base
                     ↓
              Vector Embeddings ← Bills Database
```

Yeah, it's probably overkill for storing bill numbers in a JSON file, but it's ready for that PostgreSQL migration that will totally happen someday™.

The bot now has:
- **Service Layer**: AIService, BillService, ReferenceService
- **Repository Pattern**: For data persistence abstraction
- **Tool Registry**: Dynamic tool loading for AI function calls
- **Message Router**: Intelligent message handling by channel
- **Response Formatter**: Handles Discord's message limits gracefully
- **Error Handling**: Custom exceptions with context
- **File Manager**: Centralized file operations
- **Vector Search**: Embedding-based bill search (when it works)

## Directory Structure

```
VCBot/
├── main.py                    # Entry point
├── botcore.py                 # Discord client setup
├── settings.py                # Centralized configuration
├── bot_state.py               # Runtime state management
├── requirements.txt           # Dependencies
├── .env                      # Your secrets (don't commit this!)
├── services/                 # Business logic
│   ├── ai_service.py
│   ├── bill_service.py
│   └── reference_service.py
├── repositories/             # Data access
│   ├── base.py
│   ├── bill.py
│   ├── bill_reference.py
│   └── vector.py
├── Knowledge/               # Knowledge base files
│   ├── constitution.txt
│   ├── rules.txt
│   ├── houserules.txt
│   └── senaterules.txt
├── every-vc-bill/          # Bill storage
│   ├── txts/              # Bill text files
│   └── pdfs/              # Bill PDF files
├── docs/                  # Documentation
├── tests/                 # Test suite
└── logs/                  # Application logs
```

## Production Deployment

### Using systemd (Linux)

Create `/etc/systemd/system/vcbot.service`:

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

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable vcbot
sudo systemctl start vcbot
```

### Using Docker

```bash
docker build -t vcbot .
docker run -d --name vcbot --env-file .env vcbot
```

## Tests

Run tests with: `pytest`

Note: 8 tests are skipped because testing Discord commands is annoying. The commands work fine, I promise. See `tests/SKIPPED_TESTS_EXPLANATION.md` for the gory details.

To run specific test categories:
```bash
pytest tests/test_services.py -v     # Service layer tests
pytest tests/test_repositories.py -v # Repository tests
pytest -k "not discord" -v          # Skip Discord-dependent tests
```

## Troubleshooting

### Bot Won't Start
- Check your `.env` file has all required variables
- Verify Discord token is valid (they expire if you regenerate)
- Ensure Python 3.8+ is installed
- Check logs in `logs/` directory

### Commands Not Working
- Verify Message Content Intent is enabled
- Check bot has proper Discord permissions
- Set `GUILD` in `.env` for faster command sync
- Try `LOG_LEVEL=DEBUG` to see what's happening

### AI Responses Failing
- Check Gemini API key is valid
- Verify you have API quota remaining
- Check internet connectivity
- Look for rate limiting errors in logs

### Memory Issues
- The AI models and vector embeddings can use significant RAM
- Consider increasing swap space on smaller VPS instances
- Monitor with `htop` or similar tools

## Bill Search

The bot searches through bill titles, content, authors, and categories using simple keyword matching. When you search for bills, it returns the titles to the AI and automatically attaches the full bill PDFs to the chat for reference.

The search system uses:
- **Keyword matching** for basic searches
- **Vector embeddings** for semantic search (when working)
- **Metadata filtering** for bill types and references
- **Automatic PDF attachment** for found bills

## Maintenance

### Updating
```bash
git pull origin main
pip install -r requirements.txt
# Restart bot (systemctl restart vcbot on Linux)
```

### Backups
Important files to backup:
- `bill_refs.json` - Bill reference numbers
- `queries.csv` - Query history  
- `every-vc-bill/` - Bill database
- `.env` - Configuration (keep secure!)

### Monitoring
- Check `logs/` for errors
- Monitor memory usage (AI models are hungry)
- Watch API quota usage for Gemini
- Keep Discord permissions up to date

## Credits

- **Creator & Maintainer**: Lucas Posting (@willow-wilt on GitHub)
- Original concept: Tucker Carlson Bot / VC Helper (Beta)
- Major refactor: Claude (Anthropic's AI assistant) 
- Additional chaos: The Virtual Congress community

If you use this code, cool! A shoutout would be nice.

## Contributing

It's a hobby project, so PRs are welcome if you want to add features or fix my (Claude's) overengineering.

Things that could use work:
- Better error handling for edge cases
- More robust vector search implementation
- Automated testing for Discord interactions
- Performance optimization for large bill databases
- Better mobile formatting for responses

## License

MIT - Do whatever you want with it.

---

*Built by a human, refactored by an AI, used by a Discord server about a fake Congress. What a time to be alive.*