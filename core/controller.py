import asyncio
import logging
import os
from typing import Optional
from telegram.helpers import escape_markdown
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import AppConfig
from modules.telegram_bot import TelegramBot
from modules.claude_client import ClaudeClient
from modules.session_manager import SessionManager
from modules.settings_manager import SettingsManager


logger = logging.getLogger(__name__)


class Controller:
    def __init__(self, config: AppConfig):
        self.config = config
        self.telegram_bot = TelegramBot(config.telegram)
        self.claude_client = ClaudeClient(config.claude)
        self.session_manager = SessionManager()
        self.settings_manager = SettingsManager()
        
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
            on_queue=self.handle_queue,
            on_settings=self.handle_settings,
            on_callback_query=self.handle_callback_query
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
                
                # Get user's CWD from settings if available
                custom_cwd = self.settings_manager.get_custom_cwd(user_id)
                if custom_cwd:
                    # Temporarily set the CWD for this execution
                    original_cwd = self.claude_client.options.cwd
                    self.claude_client.options.cwd = custom_cwd
                
                # Execute with Claude
                async def on_claude_message(claude_msg: str, message_type: str = None):
                    # Check if this message type should be hidden
                    if message_type and self.settings_manager.is_message_type_hidden(user_id, message_type):
                        logger.info(f"Skipping {message_type} message for user {user_id} (hidden in settings)")
                        return
                    
                    # Send Claude's formatted output with smart formatting based on message type
                    await self.telegram_bot.send_message_smart(target_chat_id, claude_msg, message_type)
                
                try:
                    await self.claude_client.stream_execute(message, on_claude_message, user_id)
                    
                    # Restore original CWD if it was changed
                    if custom_cwd:
                        self.claude_client.options.cwd = original_cwd
                    
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
                    # Restore original CWD if it was changed
                    if custom_cwd:
                        self.claude_client.options.cwd = original_cwd
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
            # Check if user has custom CWD in settings
            custom_cwd = self.settings_manager.get_custom_cwd(user_id)
            current_cwd = custom_cwd if custom_cwd else self.claude_client.options.cwd
            absolute_path = os.path.abspath(current_cwd)
            
            response_text = f"📁 Current Working Directory:\n{absolute_path}"
            
            # Check if directory exists
            if os.path.exists(absolute_path):
                response_text += "\n✅ Directory exists"
            else:
                response_text += "\n⚠️ Directory does not exist"
            
            if custom_cwd:
                response_text += "\n💡 (User custom setting)"
            else:
                response_text += "\n💡 (Default from .env)"
            
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
            
            # Save to user settings
            self.settings_manager.set_custom_cwd(user_id, absolute_path)
            
            logger.info(f"User {user_id} changed cwd to: {absolute_path}")
            
            response_text = (
                f"✅ Working directory changed to:\n"
                f"{absolute_path}\n\n"
                f"This setting has been saved for your user."
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
    
    async def handle_settings(self, chat_id: int, user_id: int):
        """Handle settings command - show settings menu with inline keyboard"""
        try:
            # Get current settings
            user_settings = self.settings_manager.get_user_settings(user_id)
            
            # Get available message types and display names
            message_types = self.settings_manager.get_available_message_types()
            display_names = self.settings_manager.get_message_type_display_names()
            
            # Create inline keyboard buttons in 2x2 layout
            keyboard = []
            buttons = []
            
            for msg_type in message_types:
                is_hidden = msg_type in user_settings.hidden_message_types
                checkbox = "☑️" if is_hidden else "⬜"
                display_name = display_names.get(msg_type, msg_type)
                button_text = f"{checkbox} Hide {display_name}"
                callback_data = f"toggle_msg_{msg_type}"
                buttons.append(InlineKeyboardButton(button_text, callback_data=callback_data))
            
            # Arrange buttons in 2x2 layout
            for i in range(0, len(buttons), 2):
                row = buttons[i:i+2]
                keyboard.append(row)
            
            # Add info button on its own line
            keyboard.append([InlineKeyboardButton("ℹ️ About Message Types", callback_data="info_msg_types")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send settings message
            target_chat_id = self.config.telegram.target_chat_id or chat_id
            await self.telegram_bot.send_settings_message(
                target_chat_id,
                "⚙️ *Settings \\- Message Visibility*\n\n"
                "Select which message types to hide from Claude output:",
                reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error showing settings: {e}")
            target_chat_id = self.config.telegram.target_chat_id or chat_id
            await self.telegram_bot.send_message(
                target_chat_id,
                f"❌ Error showing settings: {str(e)}"
            )
    
    async def handle_callback_query(self, callback_query):
        """Handle inline keyboard callbacks"""
        try:
            user_id = callback_query.from_user.id
            data = callback_query.data
            
            # Check permission
            if not self.telegram_bot.check_permission(user_id):
                await callback_query.answer("You are not authorized to use this bot.")
                return
            
            if data.startswith("toggle_msg_"):
                # Toggle message type visibility
                msg_type = data.replace("toggle_msg_", "")
                is_hidden = self.settings_manager.toggle_hidden_message_type(user_id, msg_type)
                
                # Update the keyboard with 2x2 layout
                user_settings = self.settings_manager.get_user_settings(user_id)
                message_types = self.settings_manager.get_available_message_types()
                display_names = self.settings_manager.get_message_type_display_names()
                
                keyboard = []
                buttons = []
                
                for mt in message_types:
                    is_hidden_now = mt in user_settings.hidden_message_types
                    checkbox = "☑️" if is_hidden_now else "⬜"
                    display_name = display_names.get(mt, mt)
                    button_text = f"{checkbox} Hide {display_name}"
                    callback_data = f"toggle_msg_{mt}"
                    buttons.append(InlineKeyboardButton(button_text, callback_data=callback_data))
                
                # Arrange buttons in 2x2 layout
                for i in range(0, len(buttons), 2):
                    row = buttons[i:i+2]
                    keyboard.append(row)
                
                keyboard.append([InlineKeyboardButton("ℹ️ About Message Types", callback_data="info_msg_types")])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Update message
                await callback_query.edit_message_reply_markup(reply_markup=reply_markup)
                
                # Answer callback with display name
                display_names = self.settings_manager.get_message_type_display_names()
                display_name = display_names.get(msg_type, msg_type)
                action = "hidden" if is_hidden else "shown"
                await callback_query.answer(f"{display_name} messages are now {action}")
                
            elif data == "info_msg_types":
                # Show info about message types
                info_text = (
                    "📋 *Message Types Info:*\n\n"
                    "• *System* \- System initialization and status messages\n"
                    "• *Response* \- Tool execution responses and results\n"
                    "• *Assistant* \- Claude's messages and explanations\n"
                    "• *Result* \- Final execution results and summaries\n\n"
                    "Hidden messages won't be sent to Telegram\."
                )
                await callback_query.answer()
                await callback_query.message.reply_text(info_text, parse_mode='MarkdownV2')
                
        except Exception as e:
            logger.error(f"Error handling callback query: {e}")
            await callback_query.answer(f"Error: {str(e)}")
    
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