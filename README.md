# Claude Proxy - Telegram Bot for Remote Claude Code Control

A modular system for controlling Claude Code through Telegram Bot.

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file from template:
```bash
cp .env.example .env
# Edit .env with your Telegram bot token
```

3. Run the bot:
```bash
./start.sh
# or
python main.py
```

## Configuration

### Environment Variables

- `TELEGRAM_BOT_TOKEN` (required): Your Telegram bot token from @BotFather
- `TARGET_CHAT_ID` (optional): Specific chat ID to send all Claude Code outputs
  - Use `/start` command to get your chat ID
  - If set, all outputs go to this chat regardless of where commands come from
- `ALLOWED_USERS` (optional): Comma-separated list of allowed user IDs
  - Leave empty to allow all users
  - Example: `ALLOWED_USERS=123456789,987654321`
- `CLAUDE_CWD`: Working directory for Claude Code (default: `./_tmp`)
- `LOG_LEVEL`: Logging level (default: `INFO`)

## Architecture

```
claude-proxy/
├── config/
│   └── settings.py          # Configuration management
├── modules/
│   ├── __init__.py
│   ├── telegram_bot.py      # Telegram bot interface
│   ├── claude_client.py     # Claude Code SDK wrapper
│   └── session_manager.py   # Session and message queue management
├── core/
│   ├── __init__.py
│   └── controller.py        # Main application controller
├── utils/
│   ├── __init__.py
│   └── message_formatter.py # Message formatting utilities
├── main.py                  # Application entry point
└── requirements.txt         # Dependencies
```

## Features

1. **Automatic Execution**: Messages are processed automatically in order - no manual trigger needed
2. **Message Queue**: User messages are queued and executed sequentially
3. **Real-time Feedback**: Claude Code outputs are forwarded to Telegram in real-time
4. **Target Chat Support**: Optionally send all outputs to a specific chat ID
5. **Session Management**: Supports multiple concurrent users with independent queues
6. **Permission Control**: Configure allowed users via environment variables
7. **Status Tracking**: Visual indicators for queue and execution status
8. **Working Directory Management**: Change Claude Code's working directory on the fly

## Modules

### telegram_bot
- Handles all Telegram interactions
- Commands: 
  - `/start` - Shows chat ID and user ID
  - `/status` - Display queue and execution status
  - `/clear` - Clear message queue
  - `/cwd` - Show current working directory
  - `/set_cwd <path>` - Change working directory
  - `/execute` - Manually trigger queue processing
- Automatic message queue processing
- Message formatting and rate limiting

### claude_client
- Wraps Claude Code SDK
- Manages Claude Code options and queries
- Handles streaming responses

### session_manager
- Manages user sessions
- Message queue operations
- Session state tracking

### controller
- Coordinates between modules
- Main application logic
- Error handling