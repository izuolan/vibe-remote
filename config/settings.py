import os
import logging
from dataclasses import dataclass
from typing import Optional
from modules.im.base import BaseIMConfig

logger = logging.getLogger(__name__)


@dataclass
class TelegramConfig(BaseIMConfig):
    bot_token: str
    target_chat_id: Optional[int] = None  # Target chat ID to send all messages
    
    @classmethod
    def from_env(cls) -> 'TelegramConfig':
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        
        target_chat_id = None
        target_chat_id_str = os.getenv("TELEGRAM_TARGET_CHAT_ID")
        if target_chat_id_str:
            target_chat_id = int(target_chat_id_str)
        
        return cls(bot_token=bot_token, target_chat_id=target_chat_id)
    
    def validate(self) -> bool:
        """Validate Telegram configuration"""
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        if not self.bot_token.startswith(('bot', 'xox')):
            # Basic token format check
            logger.warning("Telegram bot token format might be invalid")
        return True


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
class SlackConfig(BaseIMConfig):
    bot_token: str
    app_token: Optional[str] = None  # For Socket Mode
    signing_secret: Optional[str] = None  # For webhook mode
    target_channel: Optional[str] = None  # Default channel for outputs
    
    @classmethod
    def from_env(cls) -> 'SlackConfig':
        bot_token = os.getenv("SLACK_BOT_TOKEN")
        if not bot_token:
            raise ValueError("SLACK_BOT_TOKEN environment variable is required")
        
        return cls(
            bot_token=bot_token,
            app_token=os.getenv("SLACK_APP_TOKEN"),
            signing_secret=os.getenv("SLACK_SIGNING_SECRET"),
            target_channel=os.getenv("SLACK_TARGET_CHANNEL")
        )
    
    def validate(self) -> bool:
        """Validate Slack configuration"""
        if not self.bot_token:
            raise ValueError("SLACK_BOT_TOKEN is required")
        if not self.bot_token.startswith('xoxb-'):
            raise ValueError("Invalid Slack bot token format (should start with xoxb-)")
        if self.app_token and not self.app_token.startswith('xapp-'):
            raise ValueError("Invalid Slack app token format (should start with xapp-)")
        return True


@dataclass
class AppConfig:
    platform: str  # 'telegram' or 'slack'
    telegram: Optional[TelegramConfig] = None
    slack: Optional[SlackConfig] = None
    claude: ClaudeConfig = None
    log_level: str = "INFO"
    
    @classmethod
    def from_env(cls) -> 'AppConfig':
        platform = os.getenv("IM_PLATFORM", "telegram").lower()
        
        if platform not in ["telegram", "slack"]:
            raise ValueError(f"Invalid IM_PLATFORM: {platform}. Must be 'telegram' or 'slack'")
        
        config = cls(
            platform=platform,
            claude=ClaudeConfig.from_env(),
            log_level=os.getenv("LOG_LEVEL", "INFO")
        )
        
        # Load platform-specific config
        if platform == "telegram":
            config.telegram = TelegramConfig.from_env()
            config.telegram.validate()
        elif platform == "slack":
            config.slack = SlackConfig.from_env()
            config.slack.validate()
        
        return config