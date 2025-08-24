import os
import logging
from dataclasses import dataclass
from typing import Optional, List, Union
from modules.im.base import BaseIMConfig

logger = logging.getLogger(__name__)


@dataclass
class TelegramConfig(BaseIMConfig):
    bot_token: str
    target_chat_id: Optional[Union[List[int], str]] = (
        None  # Whitelist of chat IDs. Empty list = DM only, null/None = accept all
    )
    # Webhook 配置
    webhook_url: Optional[str] = None  # Webhook URL for production deployment
    webhook_port: int = 8443  # Port for webhook server
    webhook_listen: str = "0.0.0.0"  # Listen address for webhook
    webhook_secret_token: Optional[str] = None  # Secret token for webhook validation
    webhook_cert_path: Optional[str] = None  # Path to SSL certificate file
    webhook_key_path: Optional[str] = None  # Path to SSL private key file

    @classmethod
    def from_env(cls) -> "TelegramConfig":
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

        target_chat_id = None
        target_chat_id_str = os.getenv("TELEGRAM_TARGET_CHAT_ID")
        if target_chat_id_str:
            # Handle null string
            if target_chat_id_str.lower() in ["null", "none"]:
                target_chat_id = None
            # Handle empty list
            elif target_chat_id_str.strip() in ["[]", ""]:
                target_chat_id = []
            # Handle comma-separated list
            else:
                try:
                    # Remove brackets if present and split by comma
                    ids_str = target_chat_id_str.strip("[]")
                    if ids_str:
                        target_chat_id = [int(id.strip()) for id in ids_str.split(",")]
                    else:
                        target_chat_id = []
                except ValueError:
                    raise ValueError(
                        f"Invalid TELEGRAM_TARGET_CHAT_ID format: {target_chat_id_str}"
                    )

        # Webhook 配置
        webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")
        webhook_port = int(os.getenv("TELEGRAM_WEBHOOK_PORT", "8443"))
        webhook_listen = os.getenv("TELEGRAM_WEBHOOK_LISTEN", "0.0.0.0")
        webhook_secret_token = os.getenv("TELEGRAM_WEBHOOK_SECRET_TOKEN")
        webhook_cert_path = os.getenv("TELEGRAM_WEBHOOK_CERT_PATH")
        webhook_key_path = os.getenv("TELEGRAM_WEBHOOK_KEY_PATH")

        return cls(
            bot_token=bot_token,
            target_chat_id=target_chat_id,
            webhook_url=webhook_url,
            webhook_port=webhook_port,
            webhook_listen=webhook_listen,
            webhook_secret_token=webhook_secret_token,
            webhook_cert_path=webhook_cert_path,
            webhook_key_path=webhook_key_path,
        )

    def validate(self) -> bool:
        """Validate Telegram configuration"""
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        # Telegram bot token format is typically "<digits>:<token>"
        if ":" not in self.bot_token:
            logger.warning("Telegram bot token format might be invalid: missing colon")
        else:
            prefix = self.bot_token.split(":", 1)[0]
            if not prefix.isdigit():
                logger.warning(
                    "Telegram bot token format might be invalid: non-numeric prefix"
                )
        return True


@dataclass
class ClaudeConfig:
    permission_mode: str
    cwd: str
    system_prompt: Optional[str] = None

    @classmethod
    def from_env(cls) -> "ClaudeConfig":
        permission_mode = os.getenv("CLAUDE_PERMISSION_MODE")
        if not permission_mode:
            raise ValueError("CLAUDE_PERMISSION_MODE environment variable is required")

        cwd = os.getenv("CLAUDE_DEFAULT_CWD")
        if not cwd:
            raise ValueError("CLAUDE_DEFAULT_CWD environment variable is required")

        return cls(
            permission_mode=permission_mode,
            cwd=cwd,
            system_prompt=os.getenv("CLAUDE_SYSTEM_PROMPT"),
        )


@dataclass
class SlackConfig(BaseIMConfig):
    bot_token: str
    app_token: Optional[str] = None  # For Socket Mode
    signing_secret: Optional[str] = None  # For webhook mode
    target_channel: Optional[Union[List[str], str]] = (
        None  # Whitelist of channel IDs. Empty list = DM only, null/None = accept all
    )
    require_mention: bool = False  # Require @mention in channels (ignored in DMs)

    @classmethod
    def from_env(cls) -> "SlackConfig":
        bot_token = os.getenv("SLACK_BOT_TOKEN")
        if not bot_token:
            raise ValueError("SLACK_BOT_TOKEN environment variable is required")

        return cls(
            bot_token=bot_token,
            app_token=os.getenv("SLACK_APP_TOKEN"),
            signing_secret=os.getenv("SLACK_SIGNING_SECRET"),
            target_channel=cls._parse_channel_list(os.getenv("SLACK_TARGET_CHANNEL")),
            require_mention=os.getenv("SLACK_REQUIRE_MENTION", "false").lower()
            == "true",
        )

    def validate(self) -> bool:
        """Validate Slack configuration"""
        if not self.bot_token:
            raise ValueError("SLACK_BOT_TOKEN is required")
        if not self.bot_token.startswith("xoxb-"):
            raise ValueError("Invalid Slack bot token format (should start with xoxb-)")
        if self.app_token and not self.app_token.startswith("xapp-"):
            raise ValueError("Invalid Slack app token format (should start with xapp-)")
        return True

    @classmethod
    def _parse_channel_list(
        cls, value: Optional[str]
    ) -> Optional[Union[List[str], str]]:
        """Parse channel list from environment variable"""
        if not value:
            return None

        # Handle null string
        if value.lower() in ["null", "none"]:
            return None

        # Handle empty list
        if value.strip() in ["[]", ""]:
            return []

        # Handle comma-separated list
        # Remove brackets if present and split by comma
        ids_str = value.strip("[]")
        if ids_str:
            return [id.strip() for id in ids_str.split(",")]
        else:
            return []


@dataclass
class AppConfig:
    platform: str  # 'telegram' or 'slack'
    telegram: Optional[TelegramConfig] = None
    slack: Optional[SlackConfig] = None
    claude: ClaudeConfig = None
    log_level: str = "INFO"
    cleanup_enabled: bool = False

    @classmethod
    def from_env(cls) -> "AppConfig":
        platform = os.getenv("IM_PLATFORM")
        if not platform:
            raise ValueError("IM_PLATFORM environment variable is required")

        platform = platform.lower()
        if platform not in ["telegram", "slack"]:
            raise ValueError(
                f"Invalid IM_PLATFORM: {platform}. Must be 'telegram' or 'slack'"
            )

        log_level = os.getenv(
            "LOG_LEVEL", "INFO"
        )  # Keep default for log level as it's optional

        # Cleanup toggle (safe cleanup of completed tasks only)
        cleanup_enabled_env = os.getenv("CLEANUP_ENABLED", "false").lower()
        cleanup_enabled = cleanup_enabled_env in ["1", "true", "yes", "on"]

        config = cls(
            platform=platform,
            claude=ClaudeConfig.from_env(),
            log_level=log_level,
            cleanup_enabled=cleanup_enabled,
        )

        # Load platform-specific config
        if platform == "telegram":
            config.telegram = TelegramConfig.from_env()
            config.telegram.validate()
        elif platform == "slack":
            config.slack = SlackConfig.from_env()
            config.slack.validate()

        return config
