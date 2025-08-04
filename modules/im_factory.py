import logging
from typing import Union

from .base_im_client import BaseIMClient
from .telegram_bot import TelegramBot
from .slack_bot import SlackBot
from config.settings import AppConfig, TelegramConfig, SlackConfig

logger = logging.getLogger(__name__)


class IMFactory:
    """Factory class to create the appropriate IM client based on platform"""
    
    @staticmethod
    def create_client(config: AppConfig) -> BaseIMClient:
        """Create and return the appropriate IM client based on configuration
        
        Args:
            config: Application configuration
            
        Returns:
            Instance of platform-specific IM client
            
        Raises:
            ValueError: If platform is not supported
        """
        platform = config.platform.lower()
        
        if platform == "telegram":
            if not config.telegram:
                raise ValueError("Telegram configuration not found")
            logger.info("Creating Telegram client")
            return TelegramBot(config.telegram)
            
        elif platform == "slack":
            if not config.slack:
                raise ValueError("Slack configuration not found")
            logger.info("Creating Slack client")
            return SlackBot(config.slack)
            
        else:
            raise ValueError(f"Unsupported IM platform: {platform}")
    
    @staticmethod
    def get_supported_platforms() -> list[str]:
        """Get list of supported platforms
        
        Returns:
            List of supported platform names
        """
        return ["telegram", "slack"]