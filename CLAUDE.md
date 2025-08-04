# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a multi-platform remote control bot for Claude Code, supporting both Telegram and Slack. Users can send messages through IM platforms to execute Claude Code commands remotely. The system provides session management, message queuing, and real-time feedback.

## Development Commands

### Environment Setup
```bash
# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create configuration from template
cp .env.example .env
# Edit .env with your platform and credentials
```

### Running the Bot
```bash
# Start the bot (preferred - includes process management)
./start.sh

# Alternative direct start
python main.py

# Stop the bot
./stop.sh

# Check bot status
./status.sh
```

### Development Testing
```bash
# Test imports and basic functionality
python3 -c "from config.settings import AppConfig; from modules.im import IMFactory; print('Imports successful!')"

# Check logs in real-time
tail -f logs/bot_*.log

# Manual testing with specific platform
IM_PLATFORM=telegram python main.py
IM_PLATFORM=slack python main.py
```

## Architecture Overview

### Multi-Platform Design Pattern
The system uses an abstract factory pattern with platform-agnostic interfaces:

1. **BaseIMClient** (`modules/base_im_client.py`): Abstract base class defining the IM interface
2. **IMFactory** (`modules/im_factory.py`): Creates appropriate platform clients
3. **Controller** (`core/controller.py`): Platform-agnostic business logic coordinator

### Key Components

- **Configuration System** (`config/settings.py`): Environment-based config with platform-specific validation
- **Session Management** (`modules/session_manager.py`): Per-user message queues and execution state
- **Claude Integration** (`modules/claude_client.py`): Wrapper around Claude Code SDK
- **Settings Management** (`modules/settings_manager.py`): User preferences and message type visibility

### Platform Implementations
- **TelegramBot** (`modules/telegram_bot.py`): Telegram-specific implementation with inline keyboards
- **SlackBot** (`modules/slack_bot.py`): Slack-specific implementation with thread support and Socket Mode

### Message Flow
1. User sends message via IM platform
2. Platform-specific client converts to `MessageContext`
3. Controller queues message per user
4. Claude Code executes message sequentially
5. Real-time output streamed back through same IM platform

## Configuration Requirements

### Essential Environment Variables
- `IM_PLATFORM`: Must be "telegram" or "slack"
- Platform-specific tokens (see `.env.example`)
- `CLAUDE_CWD`: Working directory for Claude Code execution

### Platform Switching
The system dynamically loads the appropriate IM client based on `IM_PLATFORM`. Configuration validation ensures required tokens are present for the selected platform.

## Adding New IM Platforms

To extend support to new platforms (Discord, Teams, etc.):

1. Create new client class inheriting from `BaseIMClient`
2. Implement all abstract methods (send_message, edit_message, etc.)
3. Create platform config class inheriting from `BaseIMConfig`
4. Add platform to `IMFactory.create_client()`
5. Update `AppConfig.from_env()` validation
6. Add environment variables to `.env.example`

Reference `modules/slack_bot.py` for a complete implementation example.

## Thread and Session Management

### Slack Thread Handling
Slack conversations are automatically organized into threads using `thread_timestamps` dict. Each user/channel combination gets a persistent thread for continuity.

### Session Isolation
Each user has an independent message queue and execution state managed by `SessionManager`. This allows concurrent users without interference.

### Callback System
The controller registers command handlers with IM clients through a callback system, allowing platform-agnostic command handling while preserving platform-specific features (inline keyboards, thread replies, etc.).

## Deployment Notes

### Process Management
- `start.sh` provides daemon-style execution with PID tracking
- Logs are automatically rotated and stored in `logs/` directory
- Virtual environment detection and activation is automatic

### Error Handling
- Graceful degradation for missing optional tokens
- Automatic retry with exponential backoff for network failures
- Comprehensive logging for debugging platform-specific issues

### Socket Mode vs Webhooks
For Slack, Socket Mode is preferred as it doesn't require public endpoints. The system automatically uses Socket Mode if `SLACK_APP_TOKEN` is provided.