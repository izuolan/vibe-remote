# Claude Code Remote Control Bot

A modular system for controlling Claude Code through multiple instant messaging platforms (Telegram, Slack).

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file from template:
```bash
cp .env.example .env
# Edit .env with your platform choice and credentials
```

3. Choose your platform:
   - Set `IM_PLATFORM=telegram` for Telegram
   - Set `IM_PLATFORM=slack` for Slack

4. Run the bot:
```bash
./start.sh
# or
python main.py
```

## Configuration

### Platform Selection

Set `IM_PLATFORM` in your `.env` file:
- `telegram` - Use Telegram Bot
- `slack` - Use Slack Bot

### Telegram Configuration

- `TELEGRAM_BOT_TOKEN` (required): Your Telegram bot token from @BotFather
- `TELEGRAM_TARGET_CHAT_ID` (optional): Whitelist of allowed chat IDs
  - Empty or `[]`: Only accept private messages (DMs)
  - `null` or omit: Accept all chats
  - `[123456789,987654321]`: Only accept messages from these chat IDs
  - Use `/start` command to get your chat ID

### Slack Configuration

- `SLACK_BOT_TOKEN` (required): Your Slack bot token (starts with `xoxb-`)
- `SLACK_APP_TOKEN` (required for Socket Mode): App-level token (starts with `xapp-`)
- `SLACK_TARGET_CHANNEL` (optional): Whitelist of allowed channel IDs
  - Empty or `[]`: Only accept direct messages (DMs)
  - `null` or omit: Accept all channels
  - `[C1234567890,C0987654321]`: Only accept messages from these channel IDs

For detailed Slack setup instructions, see [docs/SLACK_SETUP.md](docs/SLACK_SETUP.md).

### Claude Configuration

- `CLAUDE_CWD`: Working directory for Claude Code (default: `./_tmp`)
- `CLAUDE_PERMISSION_MODE`: Permission mode (default: `bypassPermissions`)
- `CLAUDE_CONTINUE_CONVERSATION`: Continue conversations (default: `true`)
- `CLAUDE_SYSTEM_PROMPT`: Custom system prompt (optional)

### Application Configuration

- `LOG_LEVEL`: Logging level (default: `INFO`)

## Architecture

```
claude-code-bot/
├── config/
│   └── settings.py             # Configuration management
├── modules/
│   ├── __init__.py
│   ├── base_im_client.py       # Abstract base class for IM platforms
│   ├── base_im_config.py       # Base configuration class
│   ├── telegram_bot.py         # Telegram implementation
│   ├── slack_bot.py            # Slack implementation
│   ├── im_factory.py           # Factory for creating IM clients
│   ├── claude_client.py        # Claude Code SDK wrapper
│   ├── session_manager.py      # Session and message queue management
│   └── settings_manager.py     # User settings management
├── core/
│   ├── __init__.py
│   └── controller.py           # Platform-agnostic controller
├── docs/
│   └── SLACK_SETUP.md          # Slack setup documentation
├── main.py                     # Application entry point
└── requirements.txt            # Dependencies
```

## Features

### Core Features
1. **Multi-Platform Support**: Works with Telegram and Slack
2. **Automatic Execution**: Messages are processed automatically in order
3. **Message Queue**: User messages are queued and executed sequentially
4. **Real-time Feedback**: Claude Code outputs are forwarded in real-time
5. **Session Management**: Supports multiple concurrent users with independent queues
6. **Status Tracking**: Visual indicators for queue and execution status
7. **Working Directory Management**: Change Claude Code's working directory on the fly
8. **Personalization Settings**: Configure which message types to display

### Platform-Specific Features

#### Telegram
- Direct message and group chat support
- Inline keyboard for settings
- Message threading via reply-to
- Markdown formatting support

#### Slack
- **Thread Support**: Each conversation is organized in its own thread
- **Socket Mode**: No need for public webhooks
- **Channel & DM Support**: Works in both channels and direct messages
- **Mention-based Triggering**: In channels, mention the bot to interact

## Commands

All platforms support the same commands:
- `/start` - Shows welcome message and IDs
- `/status` - Display queue and execution status
- `/clear` - Clear message queue
- `/cwd` - Show current working directory
- `/set_cwd <path>` - Change working directory
- `/execute` - Manually trigger queue processing
- `/queue` - Show messages in queue
- `/settings` - Configure message visibility

## Usage

### Telegram
1. Start a chat with your bot
2. Send messages directly - they'll be queued and processed automatically
3. Use commands with `/` prefix

### Slack
1. **In Channels**: Mention the bot (`@bot-name your message`)
2. **In DMs**: Send messages directly
3. Commands work with `/` prefix
4. Each user's conversation is organized in a thread

## Adding New Platforms

The architecture supports easy addition of new IM platforms:

1. Create a new class inheriting from `BaseIMClient` 
2. Implement all abstract methods
3. Add configuration class inheriting from `BaseIMConfig`
4. Update `IMFactory` to support the new platform
5. Add platform-specific environment variables

See `modules/slack_bot.py` for a complete implementation example.