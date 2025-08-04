import asyncio
import logging
import os
from typing import Optional
from config.settings import AppConfig
from modules.base_im_client import BaseIMClient, MessageContext, InlineKeyboard, InlineButton
from modules.im_factory import IMFactory
from modules.claude_client import ClaudeClient
from modules.session_manager import SessionManager
from modules.settings_manager import SettingsManager


logger = logging.getLogger(__name__)


class Controller:
    def __init__(self, config: AppConfig):
        self.config = config
        self.im_client: BaseIMClient = IMFactory.create_client(config)
        self.claude_client = ClaudeClient(config.claude)
        self.session_manager = SessionManager()
        self.settings_manager = SettingsManager()
        
        # Setup callbacks
        self._setup_callbacks()
        
        # Background task for cleanup
        self.cleanup_task: Optional[asyncio.Task] = None
    
    def _setup_callbacks(self):
        """Setup callback connections between modules"""
        # Create command handlers dict
        self.command_handlers = {
            'start': self.handle_start,
            'execute': self.handle_execute,
            'status': self.handle_status,
            'clear': self.handle_clear,
            'cwd': self.handle_cwd,
            'set_cwd': self.handle_set_cwd,
            'queue': self.handle_queue,
            'settings': self.handle_settings
        }
        
        # Register callbacks with the IM client
        self.im_client.register_callbacks(
            on_message=self.handle_user_message,
            on_command=self.command_handlers,
            on_callback_query=self.handle_callback_query
        )
    
    async def handle_start(self, context: MessageContext, args: str = ""):
        """Handle /start command with interactive buttons"""
        platform_name = self.config.platform.capitalize()
        
        # Get user and channel info
        user_info = await self.im_client.get_user_info(context.user_id)
        channel_info = await self.im_client.get_channel_info(context.channel_id)
        
        # For non-Slack platforms, use traditional text message
        if self.config.platform != "slack":
            message_text = f"""Welcome to Claude Code Remote Control Bot!

Platform: {platform_name}
User ID: {context.user_id}
Channel/Chat ID: {context.channel_id}

Commands:
/start - Show this message
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
            
            await self.im_client.send_message(context, message_text)
            return
        
        # For Slack, create interactive buttons using Block Kit
        user_name = user_info.get('real_name') or user_info.get('name') or 'User'
        
        # Create interactive buttons for commands
        buttons = [
            # Row 1: Status commands
            [
                InlineButton(text="📊 Queue Status", callback_data="cmd_status"),
                InlineButton(text="📋 Show Queue", callback_data="cmd_queue")
            ],
            # Row 2: Queue management  
            [
                InlineButton(text="🚀 Execute Queue", callback_data="cmd_execute"),
                InlineButton(text="🗑️ Clear Queue", callback_data="cmd_clear")
            ],
            # Row 3: Directory commands
            [
                InlineButton(text="📁 Current Dir", callback_data="cmd_cwd"),
                InlineButton(text="⚙️ Settings", callback_data="cmd_settings")
            ],
            # Row 4: Help and info
            [
                InlineButton(text="ℹ️ How it Works", callback_data="info_how_it_works"),
                InlineButton(text="📖 All Commands", callback_data="info_all_commands")
            ]
        ]
        
        keyboard = InlineKeyboard(buttons=buttons)
        
        welcome_text = f"""🎉 **Welcome to Claude Code Remote Control Bot!**

👋 Hello **{user_name}**!
🔧 Platform: **{platform_name}**
📍 Channel: **{channel_info.get('name', 'Unknown')}**

**Quick Actions:**
Choose a command below or type any message to add it to the processing queue."""

        target_context = self._get_target_context(context)
        await self.im_client.send_message_with_buttons(
            target_context,
            welcome_text,
            keyboard,
            parse_mode='markdown'
        )
    
    async def handle_user_message(self, context: MessageContext, message: str):
        """Handle incoming user message"""
        try:
            await self.session_manager.add_message(context.user_id, context.channel_id, message)
            logger.info(f"User {context.user_id} added message to queue")
            
            # Check if not already executing, then start processing
            if not await self.session_manager.is_executing(context.user_id):
                asyncio.create_task(self.process_user_queue(context))
            
            # Don't send confirmation - user doesn't want it
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await self.im_client.send_message(context, "Error adding message to queue.")
    
    async def process_user_queue(self, context: MessageContext):
        """Process all messages in user's queue sequentially"""
        try:
            # Mark as executing
            await self.session_manager.set_executing(context.user_id, True)
            
            # Determine target context (use configured target channel/chat if available)
            target_context = self._get_target_context(context)
            
            while await self.session_manager.has_messages(context.user_id):
                # Get next message
                message = await self.session_manager.get_next_message(context.user_id)
                if not message:
                    break
                
                # Get user's CWD from settings if available
                custom_cwd = self.settings_manager.get_custom_cwd(context.user_id)
                if custom_cwd:
                    # Temporarily set the CWD for this execution
                    original_cwd = self.claude_client.options.cwd
                    self.claude_client.options.cwd = custom_cwd
                
                # Execute with Claude
                async def on_claude_message(claude_msg: str, message_type: str = None):
                    # Check if this message type should be hidden
                    if message_type and self.settings_manager.is_message_type_hidden(context.user_id, message_type):
                        logger.info(f"Skipping {message_type} message for user {context.user_id} (hidden in settings)")
                        return
                    
                    # Send Claude's formatted output
                    # For Slack, we want to maintain thread context
                    if self.config.platform == "slack" and hasattr(self.im_client, 'get_or_create_thread'):
                        # Get or create thread for this conversation
                        thread_ts = await self.im_client.get_or_create_thread(
                            target_context.channel_id, 
                            target_context.user_id
                        )
                        if thread_ts:
                            target_context.thread_id = thread_ts
                    
                    await self.im_client.send_message(target_context, claude_msg, parse_mode='markdown')
                
                try:
                    await self.claude_client.stream_execute(message, on_claude_message, context.user_id)
                    
                    # Restore original CWD if it was changed
                    if custom_cwd:
                        self.claude_client.options.cwd = original_cwd
                    
                    # Check if there are more messages
                    remaining = await self.session_manager.has_messages(context.user_id)
                    if remaining:
                        await self.im_client.send_message(
                            target_context,
                            "✅ Completed. Processing next message..."
                        )
                    else:
                        await self.im_client.send_message(
                            target_context,
                            "✅ All messages processed!"
                        )
                        
                except Exception as e:
                    logger.error(f"Error during Claude execution: {e}")
                    # Restore original CWD if it was changed
                    if custom_cwd:
                        self.claude_client.options.cwd = original_cwd
                    await self.im_client.send_message(
                        target_context,
                        f"❌ Error processing message: {str(e)}\nStopping queue processing."
                    )
                    break
                
                # Small delay between messages
                await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"Error in process_user_queue: {e}")
            target_context = self._get_target_context(context)
            await self.im_client.send_message(
                target_context,
                f"❌ Unexpected error: {str(e)}"
            )
        finally:
            await self.session_manager.set_executing(context.user_id, False)
    
    def _get_target_context(self, context: MessageContext) -> MessageContext:
        """Get target context based on configuration"""
        target_context = MessageContext(
            user_id=context.user_id,
            channel_id=context.channel_id,
            thread_id=context.thread_id,
            platform_specific=context.platform_specific
        )
        
        # Override channel_id if target is configured
        if self.config.platform == "telegram" and self.config.telegram and self.config.telegram.target_chat_id:
            target_context.channel_id = str(self.config.telegram.target_chat_id)
        elif self.config.platform == "slack" and self.config.slack and self.config.slack.target_channel:
            target_context.channel_id = self.config.slack.target_channel
        
        return target_context
    
    async def handle_execute(self, context: MessageContext, args: str = ""):
        """Handle manual execute command"""
        target_context = self._get_target_context(context)
        
        if await self.session_manager.is_executing(context.user_id):
            await self.im_client.send_message(
                target_context, 
                "Already processing messages. Please wait..."
            )
            return
        
        if not await self.session_manager.has_messages(context.user_id):
            await self.im_client.send_message(
                target_context,
                "No messages in queue."
            )
            return
        
        # Start processing
        asyncio.create_task(self.process_user_queue(context))
    
    async def handle_status(self, context: MessageContext, args: str = ""):
        """Handle status command"""
        try:
            status = await self.session_manager.get_status(context.user_id)
            await self.im_client.send_message(context, status)
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            await self.im_client.send_message(context, "Error getting status.")
    
    async def handle_clear(self, context: MessageContext, args: str = ""):
        """Handle clear command"""
        try:
            response = await self.session_manager.clear_queue(context.user_id)
            logger.info(f"User {context.user_id} cleared queue")
            await self.im_client.send_message(context, response)
        except Exception as e:
            logger.error(f"Error clearing queue: {e}")
            await self.im_client.send_message(context, "Error clearing queue.")
    
    async def handle_cwd(self, context: MessageContext, args: str = ""):
        """Handle cwd command - show current working directory"""
        try:
            # Check if user has custom CWD in settings
            custom_cwd = self.settings_manager.get_custom_cwd(context.user_id)
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
            
            await self.im_client.send_message(context, response_text, parse_mode='markdown')
        except Exception as e:
            logger.error(f"Error getting cwd: {e}")
            await self.im_client.send_message(context, f"Error getting working directory: {str(e)}")
    
    async def handle_set_cwd(self, context: MessageContext, args: str):
        """Handle set_cwd command - change working directory"""
        try:
            if not args:
                await self.im_client.send_message(context, "Usage: /set_cwd <path>")
                return
            
            new_path = args.strip()
            
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
                    await self.im_client.send_message(context, f"❌ Cannot create directory: {str(e)}")
                    return
            
            if not os.path.isdir(absolute_path):
                await self.im_client.send_message(
                    context, 
                    f"❌ Path exists but is not a directory: {absolute_path}"
                )
                return
            
            # Save to user settings
            self.settings_manager.set_custom_cwd(context.user_id, absolute_path)
            
            logger.info(f"User {context.user_id} changed cwd to: {absolute_path}")
            
            response_text = (
                f"✅ Working directory changed to:\n"
                f"{absolute_path}\n\n"
                f"This setting has been saved for your user."
            )
            await self.im_client.send_message(context, response_text, parse_mode='markdown')
            
        except Exception as e:
            logger.error(f"Error setting cwd: {e}")
            await self.im_client.send_message(context, f"❌ Error setting working directory: {str(e)}")
    
    async def handle_queue(self, context: MessageContext, args: str = ""):
        """Handle queue command - show queue details"""
        try:
            response = await self.session_manager.get_queue_details(context.user_id)
            logger.info(f"User {context.user_id} requested queue status")
            await self.im_client.send_message(context, response)
        except Exception as e:
            logger.error(f"Error getting queue details: {e}")
            await self.im_client.send_message(context, f"Error getting queue information: {str(e)}")
    
    async def handle_settings(self, context: MessageContext, args: str = ""):
        """Handle settings command - show settings menu with inline keyboard"""
        try:
            # Get current settings
            user_settings = self.settings_manager.get_user_settings(context.user_id)
            
            # Get available message types and display names
            message_types = self.settings_manager.get_available_message_types()
            display_names = self.settings_manager.get_message_type_display_names()
            
            # Create inline keyboard buttons
            buttons = []
            
            for msg_type in message_types:
                is_hidden = msg_type in user_settings.hidden_message_types
                checkbox = "☑️" if is_hidden else "⬜"
                display_name = display_names.get(msg_type, msg_type)
                button = InlineButton(
                    text=f"{checkbox} Hide {display_name}",
                    callback_data=f"toggle_msg_{msg_type}"
                )
                buttons.append([button])  # One button per row for now
            
            # Add info button
            buttons.append([InlineButton("ℹ️ About Message Types", callback_data="info_msg_types")])
            
            keyboard = InlineKeyboard(buttons=buttons)
            
            # Send settings message
            target_context = self._get_target_context(context)
            await self.im_client.send_message_with_buttons(
                target_context,
                "⚙️ *Settings - Message Visibility*\n\nSelect which message types to hide from Claude output:",
                keyboard,
                parse_mode='markdown'
            )
            
        except Exception as e:
            logger.error(f"Error showing settings: {e}")
            target_context = self._get_target_context(context)
            await self.im_client.send_message(
                target_context,
                f"❌ Error showing settings: {str(e)}"
            )
    
    async def handle_callback_query(self, context: MessageContext, callback_data: str):
        """Handle inline keyboard callbacks"""
        try:
            # Handle command button clicks from /start message
            if callback_data.startswith("cmd_"):
                command = callback_data.replace("cmd_", "")
                logger.info(f"Executing command via button click: {command}")
                
                # Execute the corresponding command handler
                if command in self.command_handlers:
                    handler = self.command_handlers[command]
                    await handler(context, "")
                else:
                    await self.im_client.send_message(context, f"❌ Unknown command: {command}")
                return
            
            # Handle info button clicks from /start message
            elif callback_data.startswith("info_"):
                if callback_data == "info_how_it_works":
                    info_text = """📚 *How Claude Code Bot Works:*

🔄 *Message Processing:*
• Send any message to add it to your personal queue
• Messages are processed _automatically_ in order
• Each message is sent to Claude Code for execution

⚡ *Queue Management:*
• Only *one message per user* is processed at a time
• Use 🚀 Execute Queue to manually trigger processing
• Use 🗑️ Clear Queue to remove all pending messages

📁 *Directory Control:*
• Set working directory with `/set_cwd <path>`
• All Claude Code operations use your specified directory
• Default directory can be configured in settings

🎛️ *Personalization:*
• Use ⚙️ Settings to customize message visibility
• Hide `system messages`, `responses`, or `results` as needed
• Settings are saved _per user_"""
                    
                elif callback_data == "info_all_commands":
                    info_text = """📖 *All Available Commands:*

*📊 Status & Queue:*
• `/status` or 📊 - Show current queue status
• `/queue` or 📋 - Display all messages in queue  
• `/execute` or 🚀 - Manually process queue
• `/clear` or 🗑️ - Clear all queued messages

*📁 Directory Management:*
• `/cwd` or 📁 - Show current working directory
• `/set_cwd <path>` - Change working directory

*⚙️ Configuration:*
• `/settings` or ⚙️ - Open personalization settings
• `/start` - Show this welcome screen

*💬 Three Ways to Use:*
• *Direct commands*: Use slash commands like `/status`
• *Button clicks*: Click buttons in this interface
• *Natural messages*: Just type your request normally
• *Channel mentions*: Type `@BotName your message here`

_Tip: All commands work in DMs, channels, and threads!_"""
                
                await self.im_client.send_message(context, info_text, parse_mode='markdown')
                return
            
            # Handle settings toggle buttons (existing functionality)
            elif callback_data.startswith("toggle_msg_"):
                # Toggle message type visibility
                msg_type = callback_data.replace("toggle_msg_", "")
                is_hidden = self.settings_manager.toggle_hidden_message_type(context.user_id, msg_type)
                
                # Update the keyboard
                user_settings = self.settings_manager.get_user_settings(context.user_id)
                message_types = self.settings_manager.get_available_message_types()
                display_names = self.settings_manager.get_message_type_display_names()
                
                buttons = []
                
                for mt in message_types:
                    is_hidden_now = mt in user_settings.hidden_message_types
                    checkbox = "☑️" if is_hidden_now else "⬜"
                    display_name = display_names.get(mt, mt)
                    button = InlineButton(
                        text=f"{checkbox} Hide {display_name}",
                        callback_data=f"toggle_msg_{mt}"
                    )
                    buttons.append([button])
                
                buttons.append([InlineButton("ℹ️ About Message Types", callback_data="info_msg_types")])
                
                keyboard = InlineKeyboard(buttons=buttons)
                
                # Update message
                if context.message_id:
                    await self.im_client.edit_message(
                        context,
                        context.message_id,
                        keyboard=keyboard
                    )
                
                # Answer callback
                display_name = display_names.get(msg_type, msg_type)
                action = "hidden" if is_hidden else "shown"
                
                # Platform-specific callback answering
                if self.config.platform == "telegram":
                    # For Telegram, we need the actual callback query object
                    # This is a limitation we'll need to address
                    pass
                elif self.config.platform == "slack":
                    # For Slack, we might send an ephemeral message
                    await self.im_client.send_message(
                        context,
                        f"{display_name} messages are now {action}",
                        parse_mode='markdown'
                    )
                
            elif callback_data == "info_msg_types":
                # Show info about message types
                info_text = (
                    "📋 *Message Types Info:*\n\n"
                    "• *System* - System initialization and status messages\n"
                    "• *Response* - Tool execution responses and results\n"
                    "• *Assistant* - Claude's messages and explanations\n"
                    "• *Result* - Final execution results and summaries\n\n"
                    "Hidden messages won't be sent to your IM platform."
                )
                
                # Send as new message
                await self.im_client.send_message(context, info_text, parse_mode='markdown')
                
        except Exception as e:
            logger.error(f"Error handling callback query: {e}")
            await self.im_client.send_message(context, f"Error: {str(e)}")
    
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
        logger.info(f"Starting Claude Proxy Controller with {self.config.platform} platform...")
        
        # Start cleanup task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.cleanup_task = loop.create_task(self.periodic_cleanup())
        
        # Run the IM client
        self.im_client.run()