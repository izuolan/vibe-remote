import asyncio
import logging
from typing import Callable, Optional
from telegram import Update, Bot, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.helpers import escape_markdown
from telegram.error import TelegramError
from config import TelegramConfig


logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, config: TelegramConfig):
        self.config = config
        self.application = Application.builder().token(config.bot_token).build()
        self.message_callback: Optional[Callable] = None
        self.execute_callback: Optional[Callable] = None
        self.status_callback: Optional[Callable] = None
        self.clear_callback: Optional[Callable] = None
        self.cwd_callback: Optional[Callable] = None
        self.set_cwd_callback: Optional[Callable] = None
        self.queue_callback: Optional[Callable] = None
        self.settings_callback: Optional[Callable] = None
        self.callback_query_handler: Optional[Callable] = None
        
    def check_permission(self, user_id: int) -> bool:
        """Check if user is allowed to use the bot"""
        if not self.config.allowed_users:
            return True
        return user_id in self.config.allowed_users
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if not self.check_permission(user_id):
            await update.message.reply_text("Sorry, you are not authorized to use this bot.")
            return
            
        message_text = f"""Welcome to Claude Code Remote Control Bot!

Your Chat ID: {chat_id}

Commands:
/start - Show this message and IDs  
/execute - Manually start processing queue
/clear - Clear message queue
/status - Show current status
/queue - Show messages in queue
/cwd - Show current working directory
/set_cwd <path> - Set working directory
/settings - Personalization settings

How it works:
• Send any message to add it to the queue
• Messages are automatically processed in order
• Claude Code executes each message sequentially"""

        # Use official escape function for the entire message
        escaped_message = escape_markdown(message_text, version=2)
        
        await update.message.reply_text(escaped_message, parse_mode='MarkdownV2')
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages"""
        if not self.check_permission(update.effective_user.id):
            return
            
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        message_text = update.message.text
        
        if self.message_callback:
            response = await self.message_callback(chat_id, user_id, message_text)
            if response:
                await update.message.reply_text(response)
    
    async def execute_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /execute command"""
        if not self.check_permission(update.effective_user.id):
            return
            
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if self.execute_callback:
            await self.execute_callback(chat_id, user_id)
    
    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /clear command"""
        if not self.check_permission(update.effective_user.id):
            return
            
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if self.clear_callback:
            response = await self.clear_callback(chat_id, user_id)
            if response:
                await update.message.reply_text(response)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        if not self.check_permission(update.effective_user.id):
            return
            
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if self.status_callback:
            response = await self.status_callback(chat_id, user_id)
            if response:
                await update.message.reply_text(response)
    
    async def cwd_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cwd command"""
        if not self.check_permission(update.effective_user.id):
            return
            
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if self.cwd_callback:
            response = await self.cwd_callback(chat_id, user_id)
            if response:
                await update.message.reply_text(response, parse_mode='MarkdownV2')
    
    async def set_cwd_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /set_cwd command"""
        if not self.check_permission(update.effective_user.id):
            return
            
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        # Extract path from command
        message_text = update.message.text
        parts = message_text.split(maxsplit=1)
        
        if len(parts) < 2:
            await update.message.reply_text("Usage: /set_cwd <path>")
            return
        
        new_path = parts[1].strip()
        
        if self.set_cwd_callback:
            response = await self.set_cwd_callback(chat_id, user_id, new_path)
            if response:
                await update.message.reply_text(response, parse_mode='MarkdownV2')
    
    async def queue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /queue command"""
        if not self.check_permission(update.effective_user.id):
            return
            
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if self.queue_callback:
            response = await self.queue_callback(chat_id, user_id)
            if response:
                await update.message.reply_text(response)
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command"""
        if not self.check_permission(update.effective_user.id):
            return
            
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if self.settings_callback:
            await self.settings_callback(chat_id, user_id)
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline keyboards"""
        if self.callback_query_handler:
            await self.callback_query_handler(update.callback_query)
    
    def register_callbacks(self, 
                         on_message: Callable = None,
                         on_execute: Callable = None,
                         on_status: Callable = None,
                         on_clear: Callable = None,
                         on_cwd: Callable = None,
                         on_set_cwd: Callable = None,
                         on_queue: Callable = None,
                         on_settings: Callable = None,
                         on_callback_query: Callable = None):
        """Register callback functions"""
        self.message_callback = on_message
        self.execute_callback = on_execute
        self.status_callback = on_status
        self.clear_callback = on_clear
        self.cwd_callback = on_cwd
        self.set_cwd_callback = on_set_cwd
        self.queue_callback = on_queue
        self.settings_callback = on_settings
        self.callback_query_handler = on_callback_query
    
    def setup_handlers(self):
        """Setup bot command and message handlers"""
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("execute", self.execute_command))
        self.application.add_handler(CommandHandler("clear", self.clear_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("queue", self.queue_command))
        self.application.add_handler(CommandHandler("cwd", self.cwd_command))
        self.application.add_handler(CommandHandler("set_cwd", self.set_cwd_command))
        self.application.add_handler(CommandHandler("settings", self.settings_command))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback_query))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
    
    async def send_message(self, chat_id: int, text: str, parse_mode: str = None):
        """Send message to specific chat"""
        bot = self.application.bot
        
        # Split long messages
        if len(text) > 4000:
            for i in range(0, len(text), 4000):
                await bot.send_message(
                    chat_id=chat_id,
                    text=text[i:i+4000],
                    parse_mode=parse_mode if parse_mode != 'Markdown' else 'MarkdownV2'
                )
                await asyncio.sleep(0.1)  # Avoid rate limiting
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode if parse_mode != 'Markdown' else 'MarkdownV2'
            )
    
    async def send_settings_message(self, chat_id: int, text: str, reply_markup: InlineKeyboardMarkup):
        """Send message with inline keyboard"""
        bot = self.application.bot
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode='MarkdownV2',
            reply_markup=reply_markup
        )
    
    async def send_message_smart(self, chat_id: int, text: str, message_type: str = None):
        """Send message with smart format fallback for different message types"""
        bot = self.application.bot
        
        # Split long messages
        if len(text) > 4000:
            for i in range(0, len(text), 4000):
                await self.send_message_smart(chat_id, text[i:i+4000], message_type)
                await asyncio.sleep(0.1)
            return
        
        # For result messages, try to preserve formatting
        if message_type == 'result':
            # Try original Markdown first
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode='Markdown'
                )
                return
            except TelegramError:
                pass
            
            # Try HTML as fallback
            try:
                # Simple Markdown to HTML conversion
                html_text = self._markdown_to_html(text)
                await bot.send_message(
                    chat_id=chat_id,
                    text=html_text,
                    parse_mode='HTML'
                )
                return
            except TelegramError:
                pass
        
        # Default to escaped MarkdownV2 for all other cases
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='MarkdownV2'
            )
        except TelegramError:
            # Last resort: send as plain text
            await bot.send_message(
                chat_id=chat_id,
                text=text
            )
    
    def _markdown_to_html(self, text: str) -> str:
        """Simple Markdown to HTML conversion for common patterns"""
        import re
        
        # First escape HTML entities
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        
        # Convert code blocks (must be done before inline code)
        text = re.sub(r'```([^`]+)```', r'<pre>\1</pre>', text, flags=re.DOTALL)
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        
        # Convert bold and italic
        text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', text)
        
        # Convert links
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
        
        return text
    
    def run(self):
        """Run the bot with infinite retry mechanism"""
        import time
        
        self.setup_handlers()
        
        retry_delay = 5  # seconds
        attempt = 1
        
        while True:
            try:
                logger.info(f"Starting Telegram bot (attempt {attempt})...")
                self.application.run_polling()
                break  # If successful, break out of retry loop
                
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, shutting down...")
                break
                
            except Exception as e:
                logger.error(f"Telegram bot failed (attempt {attempt}): {e}")
                logger.info(f"Retrying in {retry_delay} seconds...")
                
                try:
                    time.sleep(retry_delay)
                except KeyboardInterrupt:
                    logger.info("Received keyboard interrupt during retry wait, shutting down...")
                    break
                    
                retry_delay = min(retry_delay * 1.5, 60)  # Exponential backoff, max 60s
                attempt += 1