import asyncio
import logging
import os
from typing import Optional
from telegram.helpers import escape_markdown
from config import AppConfig
from modules.telegram_bot import TelegramBot
from modules.claude_client import ClaudeClient
from modules.session_manager import SessionManager


logger = logging.getLogger(__name__)


class Controller:
    def __init__(self, config: AppConfig):
        self.config = config
        self.telegram_bot = TelegramBot(config.telegram)
        self.claude_client = ClaudeClient(config.claude)
        self.session_manager = SessionManager()
        
        # Setup callbacks
        self._setup_callbacks()
        
        # Background task for cleanup
        self.cleanup_task: Optional[asyncio.Task] = None
    
    def _setup_callbacks(self):
        """Setup callback connections between modules"""
        self.telegram_bot.register_callbacks(
            on_message=self.handle_user_message,
            on_execute=self.handle_execute,
            on_status=self.handle_status,
            on_clear=self.handle_clear,
            on_cwd=self.handle_cwd,
            on_set_cwd=self.handle_set_cwd,
            on_queue=self.handle_queue
        )
    
    async def handle_user_message(self, chat_id: int, user_id: int, message: str) -> str:
        """Handle incoming user message"""
        try:
            await self.session_manager.add_message(user_id, chat_id, message)
            logger.info(f"User {user_id} added message to queue")
            
            # Check if not already executing, then start processing
            if not await self.session_manager.is_executing(user_id):
                asyncio.create_task(self.process_user_queue(chat_id, user_id))
            
            # Don't return any message - user doesn't want confirmation
            return None
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return "Error adding message to queue."
    
    async def process_user_queue(self, chat_id: int, user_id: int):
        """Process all messages in user's queue sequentially"""
        try:
            # Mark as executing
            await self.session_manager.set_executing(user_id, True)
            
            # Use target chat ID if configured, otherwise use the original chat
            target_chat_id = self.config.telegram.target_chat_id or chat_id
            
            while await self.session_manager.has_messages(user_id):
                # Get next message
                message = await self.session_manager.get_next_message(user_id)
                if not message:
                    break
                
                # Don't send processing notification - user doesn't want it
                # await self.telegram_bot.send_message(
                #     target_chat_id,
                #     f"🚀 Processing: {message[:50]}..."
                # )
                
                # Execute with Claude
                async def on_claude_message(claude_msg: str):
                    # Send Claude's formatted output with MarkdownV2 parsing
                    await self.telegram_bot.send_message(target_chat_id, claude_msg, parse_mode='MarkdownV2')
                
                try:
                    await self.claude_client.stream_execute(message, on_claude_message)
                    
                    # Check if there are more messages
                    remaining = await self.session_manager.has_messages(user_id)
                    if remaining:
                        await self.telegram_bot.send_message(
                            target_chat_id,
                            f"✅ Completed. Processing next message..."
                        )
                    else:
                        await self.telegram_bot.send_message(
                            target_chat_id,
                            "✅ All messages processed!"
                        )
                        
                except Exception as e:
                    logger.error(f"Error during Claude execution: {e}")
                    await self.telegram_bot.send_message(
                        target_chat_id,
                        f"❌ Error processing message: {str(e)}\nStopping queue processing."
                    )
                    break
                
                # Small delay between messages
                await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"Error in process_user_queue: {e}")
            target_chat_id = self.config.telegram.target_chat_id or chat_id
            await self.telegram_bot.send_message(
                target_chat_id,
                f"❌ Unexpected error: {str(e)}"
            )
        finally:
            await self.session_manager.set_executing(user_id, False)
    
    async def handle_execute(self, chat_id: int, user_id: int):
        """Handle manual execute command - now just starts queue processing"""
        target_chat_id = self.config.telegram.target_chat_id or chat_id
        
        if await self.session_manager.is_executing(user_id):
            await self.telegram_bot.send_message(
                target_chat_id, 
                "Already processing messages. Please wait..."
            )
            return
        
        if not await self.session_manager.has_messages(user_id):
            await self.telegram_bot.send_message(
                target_chat_id,
                "No messages in queue."
            )
            return
        
        # Start processing
        asyncio.create_task(self.process_user_queue(chat_id, user_id))
    
    async def handle_status(self, chat_id: int, user_id: int) -> str:
        """Handle status command"""
        try:
            status = await self.session_manager.get_status(user_id)
            return status
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return "Error getting status."
    
    async def handle_clear(self, chat_id: int, user_id: int) -> str:
        """Handle clear command"""
        try:
            response = await self.session_manager.clear_queue(user_id)
            logger.info(f"User {user_id} cleared queue")
            return response
        except Exception as e:
            logger.error(f"Error clearing queue: {e}")
            return "Error clearing queue."
    
    async def handle_cwd(self, chat_id: int, user_id: int) -> str:
        """Handle cwd command - show current working directory"""
        try:
            current_cwd = self.claude_client.options.cwd
            absolute_path = os.path.abspath(current_cwd)
            
            response_text = f"📁 Current Working Directory:\n{absolute_path}"
            
            # Check if directory exists
            if os.path.exists(absolute_path):
                response_text += "\n✅ Directory exists"
            else:
                response_text += "\n⚠️ Directory does not exist"
            
            return escape_markdown(response_text, version=2)
        except Exception as e:
            logger.error(f"Error getting cwd: {e}")
            return f"Error getting working directory: {str(e)}"
    
    async def handle_set_cwd(self, chat_id: int, user_id: int, new_path: str) -> str:
        """Handle set_cwd command - change working directory"""
        try:
            # Expand user path and get absolute path
            expanded_path = os.path.expanduser(new_path)
            absolute_path = os.path.abspath(expanded_path)
            
            # Check if directory exists
            if not os.path.exists(absolute_path):
                # Try to create it
                try:
                    os.makedirs(absolute_path, exist_ok=True)
                    logger.info(f"Created directory: {absolute_path}")
                except Exception as e:
                    return f"❌ Cannot create directory: {str(e)}"
            
            if not os.path.isdir(absolute_path):
                error_text = f"❌ Path exists but is not a directory: {absolute_path}"
                return escape_markdown(error_text, version=2)
            
            # Update Claude client options
            self.claude_client.options.cwd = absolute_path
            
            logger.info(f"User {user_id} changed cwd to: {absolute_path}")
            
            response_text = (
                f"✅ Working directory changed to:\n"
                f"{absolute_path}\n\n"
                f"All Claude Code commands will now execute in this directory."
            )
            return escape_markdown(response_text, version=2)
            
        except Exception as e:
            logger.error(f"Error setting cwd: {e}")
            return f"❌ Error setting working directory: {str(e)}"
    
    async def handle_queue(self, chat_id: int, user_id: int) -> str:
        """Handle queue command - show queue details"""
        try:
            response = await self.session_manager.get_queue_details(user_id)
            logger.info(f"User {user_id} requested queue status")
            return response
        except Exception as e:
            logger.error(f"Error getting queue details: {e}")
            return f"Error getting queue information: {str(e)}"
    
    async def periodic_cleanup(self):
        """Periodic cleanup of inactive sessions"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                removed = await self.session_manager.cleanup_inactive_sessions()
                if removed > 0:
                    logger.info(f"Cleaned up {removed} inactive sessions")
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
    
    def run(self):
        """Run the controller"""
        logger.info("Starting Claude Proxy Controller...")
        
        # Start cleanup task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.cleanup_task = loop.create_task(self.periodic_cleanup())
        
        # Run telegram bot
        self.telegram_bot.run()