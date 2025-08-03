#!/usr/bin/env python3
import os
import sys
import logging
from dotenv import load_dotenv
from config import AppConfig
from core.controller import Controller

# Load environment variables from .env file
load_dotenv()


def setup_logging(level: str = "INFO"):
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('claude_proxy.log')
        ]
    )


def main():
    """Main entry point"""
    try:
        # Load configuration
        config = AppConfig.from_env()
        
        # Setup logging
        setup_logging(config.log_level)
        logger = logging.getLogger(__name__)
        
        logger.info("Starting Claude Proxy...")
        logger.info(f"Working directory: {config.claude.cwd}")
        
        # Create and run controller
        controller = Controller(config)
        controller.run()
        
    except Exception as e:
        logging.error(f"Failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()