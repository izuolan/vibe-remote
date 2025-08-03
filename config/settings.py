import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class TelegramConfig:
    bot_token: str
    target_chat_id: Optional[int] = None  # Target chat ID to send all messages
    allowed_users: Optional[list[int]] = None  # Optional: Restrict who can use the bot
    
    @classmethod
    def from_env(cls) -> 'TelegramConfig':
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        
        target_chat_id = None
        target_chat_id_str = os.getenv("TARGET_CHAT_ID")
        if target_chat_id_str:
            target_chat_id = int(target_chat_id_str)
        
        allowed_users_str = os.getenv("ALLOWED_USERS", "")
        allowed_users = [int(uid) for uid in allowed_users_str.split(",") if uid] if allowed_users_str else None
        
        return cls(bot_token=bot_token, target_chat_id=target_chat_id, allowed_users=allowed_users)


@dataclass
class ClaudeConfig:
    permission_mode: str = "bypassPermissions"
    cwd: str = "./_tmp"
    continue_conversation: bool = True
    system_prompt: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> 'ClaudeConfig':
        return cls(
            permission_mode=os.getenv("CLAUDE_PERMISSION_MODE", "bypassPermissions"),
            cwd=os.getenv("CLAUDE_CWD", "./_tmp"),
            continue_conversation=os.getenv("CLAUDE_CONTINUE_CONVERSATION", "true").lower() == "true",
            system_prompt=os.getenv("CLAUDE_SYSTEM_PROMPT")
        )


@dataclass
class AppConfig:
    telegram: TelegramConfig
    claude: ClaudeConfig
    log_level: str = "INFO"
    
    @classmethod
    def from_env(cls) -> 'AppConfig':
        return cls(
            telegram=TelegramConfig.from_env(),
            claude=ClaudeConfig.from_env(),
            log_level=os.getenv("LOG_LEVEL", "INFO")
        )