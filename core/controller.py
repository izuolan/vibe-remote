import asyncio
import logging
import os
from typing import Optional, Union
from config.settings import AppConfig
from modules.im import BaseIMClient, MessageContext, InlineKeyboard, InlineButton, IMFactory
from modules.im.formatters import TelegramFormatter, SlackFormatter
from modules.claude_client import ClaudeClient
from modules.session_manager import SessionManager
from modules.settings_manager import SettingsManager


logger = logging.getLogger(__name__)


class Controller:
    def __init__(self, config: AppConfig):
        self.config = config
        self.im_client: BaseIMClient = IMFactory.create_client(config)
        
        # Create platform-specific formatter
        if config.platform == "telegram":
            formatter = TelegramFormatter()
        elif config.platform == "slack":
            formatter = SlackFormatter()
        else:
            # Default to Telegram formatter for unknown platforms
            logger.warning(f"Unknown platform: {config.platform}, using Telegram formatter")
            formatter = TelegramFormatter()
        
        # Inject formatter into ClaudeClient
        self.claude_client = ClaudeClient(config.claude, formatter)
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
            on_callback_query=self.handle_callback_query,
            on_settings_update=self.handle_settings_update,
            on_change_cwd=self.handle_change_cwd_submission
        )
    
    async def handle_start(self, context: MessageContext, args: str = ""):
        """Handle /start command with interactive buttons"""
        platform_name = self.config.platform.capitalize()
        
        # Get user and channel info
        try:
            user_info = await self.im_client.get_user_info(context.user_id)
        except Exception as e:
            logger.warning(f"Failed to get user info: {e}")
            user_info = {'id': context.user_id}
        
        try:
            channel_info = await self.im_client.get_channel_info(context.channel_id)
        except Exception as e:
            logger.warning(f"Failed to get channel info: {e}")
            channel_info = {'id': context.channel_id, 'name': 'Direct Message' if context.channel_id.startswith('D') else context.channel_id}
        
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
            # Row 1: Queue operations
            [
                InlineButton(text="📊 Queue Status", callback_data="cmd_queue_status"),
                InlineButton(text="🚀 Execute Queue", callback_data="cmd_execute")
            ],
            # Row 2: Queue management & Directory
            [
                InlineButton(text="🗑️ Clear Queue", callback_data="cmd_clear"),
                InlineButton(text="📁 Current Dir", callback_data="cmd_cwd")
            ],
            # Row 3: Configuration
            [
                InlineButton(text="📂 Change Work Dir", callback_data="cmd_change_cwd"),
                InlineButton(text="⚙️ Settings", callback_data="cmd_settings")
            ],
            # Row 4: Help
            [
                InlineButton(text="ℹ️ How it Works", callback_data="info_how_it_works")
            ]
        ]
        
        keyboard = InlineKeyboard(buttons=buttons)
        
        welcome_text = f"""🎉 **Welcome to Claude Code Remote Control Bot!**

👋 Hello **{user_name}**!
🔧 Platform: **{platform_name}**
📍 Channel: **{channel_info.get('name', 'Unknown')}**

**Quick Actions:**
Use the buttons below to manage your Claude Code sessions, or simply type any message to add it to the processing queue."""

        target_context = self._get_target_context(context)
        # For Telegram, send with Markdown parse mode (not MarkdownV2)
        # For Slack, use markdown
        parse_mode = 'Markdown' if self.config.platform == "telegram" else 'markdown'
        await self.im_client.send_message_with_buttons(
            target_context,
            welcome_text,
            keyboard,
            parse_mode=parse_mode
        )
    
    async def handle_user_message(self, context: MessageContext, message: str):
        """Handle incoming user message"""
        try:
            # Send confirmation reply immediately
            target_context = self._get_target_context(context)
            
            # For Slack, use the user's message timestamp as thread
            confirmation_msg = None
            if self.config.platform == "slack":
                # Use the user's message timestamp as the thread ID
                user_message_ts = context.message_id  # This is the timestamp of the user's message
                if user_message_ts:
                    target_context.thread_id = user_message_ts
                
                # Send confirmation as reply in the thread
                confirmation_text = f"📝 *Received*\n⏳ *Processing...*"
                parse_mode = 'Markdown' if self.config.platform == "telegram" else 'markdown'
                confirmation_msg = await self.im_client.send_message(
                    target_context,
                    confirmation_text,
                    parse_mode=parse_mode,
                    reply_to=user_message_ts  # Reply to the user's message
                )
            else:
                # For non-Slack platforms, just send confirmation
                confirmation_text = f"📝 *Received*\n⏳ *Processing...*"
                parse_mode = 'Markdown' if self.config.platform == "telegram" else 'markdown'
                confirmation_msg = await self.im_client.send_message(
                    target_context,
                    confirmation_text,
                    parse_mode=parse_mode
                )
            
            # Store thread context with the message (use user's message timestamp for Slack)
            thread_id = user_message_ts if self.config.platform == "slack" and user_message_ts else None
            await self.session_manager.add_message_with_context(
                context.user_id, 
                context.channel_id, 
                message,
                thread_id=thread_id
            )
            logger.info(f"User {context.user_id} added message to queue with thread_id: {thread_id}")
            
            # Check if not already executing, then start processing
            if not await self.session_manager.is_executing(context.user_id):
                asyncio.create_task(self.process_user_queue(context))
            
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
                # Get next message with context
                message_data = await self.session_manager.get_next_message_with_context(context.user_id)
                if not message_data:
                    break
                
                message = message_data['message']
                thread_id = message_data.get('thread_id')
                
                # Get user's CWD from settings if available
                settings_key = self._get_settings_key(context)
                custom_cwd = self.settings_manager.get_custom_cwd(settings_key)
                original_cwd = self.claude_client.options.cwd
                
                # Use custom CWD if set, otherwise fall back to config default
                if custom_cwd:
                    self.claude_client.options.cwd = custom_cwd
                else:
                    # Reset to config default in case it was changed before
                    self.claude_client.options.cwd = self.config.claude.cwd
                
                # Execute with Claude
                async def on_claude_message(claude_msg: str, message_type: str = None):
                    # Check if this message type should be hidden
                    settings_key = self._get_settings_key(context)
                    if message_type and self.settings_manager.is_message_type_hidden(settings_key, message_type):
                        logger.info(f"Skipping {message_type} message for settings key {settings_key} (hidden in settings)")
                        return
                    
                    # Send Claude's formatted output
                    # Use stored thread context if available
                    if thread_id:
                        target_context.thread_id = thread_id
                    
                    # Don't escape Claude messages - they already contain proper markdown
                    # Use appropriate parse_mode for each platform
                    parse_mode = 'markdown' if self.config.platform == "slack" else 'Markdown'
                    await self.im_client.send_message(
                        target_context, 
                        claude_msg, 
                        parse_mode=parse_mode,
                        reply_to=thread_id if self.config.platform == "slack" else None
                    )
                
                try:
                    await self.claude_client.stream_execute(message, on_claude_message, context.user_id)
                    
                    # Always restore original CWD
                    self.claude_client.options.cwd = original_cwd
                    
                    # Check if there are more messages
                    remaining = await self.session_manager.has_messages(context.user_id)
                    if remaining:
                        await self.im_client.send_message(
                            target_context,
                            "✅ Completed. Processing next message...",
                            reply_to=thread_id if self.config.platform == "slack" else None
                        )
                    else:
                        await self.im_client.send_message(
                            target_context,
                            "✅ All messages processed!",
                            reply_to=thread_id if self.config.platform == "slack" else None
                        )
                        
                except Exception as e:
                    logger.error(f"Error during Claude execution: {e}")
                    # Always restore original CWD
                    self.claude_client.options.cwd = original_cwd
                    await self.im_client.send_message(
                        target_context,
                        f"❌ Error processing message: {str(e)}\nStopping queue processing.",
                        reply_to=thread_id if self.config.platform == "slack" else None
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
        
        # Override channel_id if target is configured (only for single target scenarios)
        if self.config.platform == "telegram" and self.config.telegram:
            target_chat_id = self.config.telegram.target_chat_id
            # Only override if it's a single ID (not a list)
            if target_chat_id and not isinstance(target_chat_id, list):
                target_context.channel_id = str(target_chat_id)
        elif self.config.platform == "slack" and self.config.slack:
            target_channel = self.config.slack.target_channel
            # Only override if it's a single ID (not a list)
            if target_channel and not isinstance(target_channel, list):
                target_context.channel_id = target_channel
        
        return target_context
    
    def _get_settings_key(self, context: MessageContext) -> Union[str, int]:
        """Get the appropriate settings key based on platform"""
        if self.config.platform == "slack":
            # For Slack, use channel_id as the key
            return context.channel_id
        else:
            # For Telegram, use chat_id/channel_id (convert to int)
            # Note: In Telegram, we use channel_id which is actually the chat_id
            try:
                return int(context.channel_id) if context.channel_id else context.channel_id
            except (ValueError, TypeError):
                # Fallback to user_id for backward compatibility
                return int(context.user_id) if context.user_id else context.user_id
    
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
            settings_key = self._get_settings_key(context)
            custom_cwd = self.settings_manager.get_custom_cwd(settings_key)
            current_cwd = custom_cwd if custom_cwd else self.config.claude.cwd
            absolute_path = os.path.abspath(current_cwd)
            
            # Build response using formatter to avoid escaping issues
            formatter = self.im_client.formatter
            
            # Format path properly with code block
            path_line = f"📁 Current Working Directory:\n{formatter.format_code_inline(absolute_path)}"
            
            # Build status lines
            status_lines = []
            if os.path.exists(absolute_path):
                status_lines.append("✅ Directory exists")
            else:
                status_lines.append("⚠️ Directory does not exist")
            
            if custom_cwd:
                status_lines.append("💡 \\(User custom setting\\)")
            else:
                status_lines.append("💡 \\(Default from \\.env\\)")
            
            # Combine all parts
            response_text = path_line + "\n" + "\n".join(status_lines)
            
            parse_mode = 'Markdown' if self.config.platform == "telegram" else 'markdown'
            await self.im_client.send_message(context, response_text, parse_mode=parse_mode)
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
                formatter = self.im_client.formatter
                error_text = f"❌ Path exists but is not a directory: {formatter.format_code_inline(absolute_path)}"
                parse_mode = 'Markdown' if self.config.platform == "telegram" else 'markdown'
                await self.im_client.send_message(context, error_text, parse_mode=parse_mode)
                return
            
            # Save to user settings
            settings_key = self._get_settings_key(context)
            self.settings_manager.set_custom_cwd(settings_key, absolute_path)
            
            logger.info(f"User {context.user_id} changed cwd to: {absolute_path}")
            
            formatter = self.im_client.formatter
            response_text = (
                f"✅ Working directory changed to:\n"
                f"{formatter.format_code_inline(absolute_path)}\n\n"
                f"This setting has been saved for your user."
            )
            parse_mode = 'Markdown' if self.config.platform == "telegram" else 'markdown'
            await self.im_client.send_message(context, response_text, parse_mode=parse_mode)
            
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
    
    async def handle_queue_status(self, context: MessageContext):
        """Handle combined queue status - merges status and queue details"""
        try:
            # Get both status and queue details
            status = await self.session_manager.get_status(context.user_id)
            queue_details = await self.session_manager.get_queue_details(context.user_id)
            
            # Combine the information
            combined_info = f"{status}\n\n{queue_details}"
            
            await self.im_client.send_message(context, combined_info)
        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            await self.im_client.send_message(context, f"Error getting queue status: {str(e)}")
    
    async def handle_change_cwd_modal(self, context: MessageContext):
        """Handle Change Work Dir button - open modal for Slack"""
        if self.config.platform != "slack":
            # For non-Slack platforms, just send instructions
            await self.im_client.send_message(
                context,
                "📂 To change working directory, use:\n`/set_cwd <path>`\n\nExample:\n`/set_cwd ~/projects/myapp`"
            )
            return
        
        # For Slack, open a modal dialog
        trigger_id = context.platform_specific.get('trigger_id') if context.platform_specific else None
        
        if trigger_id and hasattr(self.im_client, 'open_change_cwd_modal'):
            try:
                # Get current CWD to show in modal
                settings_key = self._get_settings_key(context)
                custom_cwd = self.settings_manager.get_custom_cwd(settings_key)
                current_cwd = custom_cwd if custom_cwd else self.config.claude.cwd
                
                await self.im_client.open_change_cwd_modal(trigger_id, current_cwd, context.channel_id)
            except Exception as e:
                logger.error(f"Error opening change CWD modal: {e}")
                await self.im_client.send_message(context, "❌ Failed to open directory change dialog. Please try again.")
        else:
            # No trigger_id, show instructions
            await self.im_client.send_message(
                context,
                "📂 Click the 'Change Work Dir' button in the /start menu to change working directory."
            )
    
    async def handle_settings(self, context: MessageContext, args: str = ""):
        """Handle settings command - show settings menu"""
        try:
            # For Slack, use modal dialog
            if self.config.platform == "slack":
                await self._handle_settings_slack(context)
            else:
                # For other platforms, use inline keyboard
                await self._handle_settings_traditional(context)
                
        except Exception as e:
            logger.error(f"Error showing settings: {e}")
            target_context = self._get_target_context(context)
            await self.im_client.send_message(
                target_context,
                f"❌ Error showing settings: {str(e)}"
            )
    
    async def _handle_settings_traditional(self, context: MessageContext):
        """Handle settings for non-Slack platforms (Telegram, etc)"""
        # Get current settings
        settings_key = self._get_settings_key(context)
        user_settings = self.settings_manager.get_user_settings(settings_key)
        
        # Get available message types and display names
        message_types = self.settings_manager.get_available_message_types()
        display_names = self.settings_manager.get_message_type_display_names()
        
        # Create inline keyboard buttons in 2x2 layout
        buttons = []
        row = []
        
        for i, msg_type in enumerate(message_types):
            is_hidden = msg_type in user_settings.hidden_message_types
            checkbox = "☑️" if is_hidden else "⬜"
            display_name = display_names.get(msg_type, msg_type)
            button = InlineButton(
                text=f"{checkbox} Hide {display_name}",
                callback_data=f"toggle_msg_{msg_type}"
            )
            row.append(button)
            
            # Create 2x2 layout
            if len(row) == 2 or i == len(message_types) - 1:
                buttons.append(row)
                row = []
        
        # Add info button on its own row
        buttons.append([InlineButton("ℹ️ About Message Types", callback_data="info_msg_types")])
        
        keyboard = InlineKeyboard(buttons=buttons)
        
        # Send settings message with escaped dash
        target_context = self._get_target_context(context)
        await self.im_client.send_message_with_buttons(
            target_context,
            "⚙️ *Settings \\- Message Visibility*\n\nSelect which message types to hide from Claude output:",
            keyboard,
            parse_mode='Markdown' if self.config.platform == "telegram" else 'markdown'
        )
    
    async def _handle_settings_slack(self, context: MessageContext):
        """Handle settings for Slack using modal dialog"""
        # For slash commands or direct triggers, we might have trigger_id
        trigger_id = context.platform_specific.get('trigger_id') if context.platform_specific else None
        
        if trigger_id and hasattr(self.im_client, 'open_settings_modal'):
            # We have trigger_id, open modal directly
            settings_key = self._get_settings_key(context)
            user_settings = self.settings_manager.get_user_settings(settings_key)
            message_types = self.settings_manager.get_available_message_types()
            display_names = self.settings_manager.get_message_type_display_names()
            
            try:
                await self.im_client.open_settings_modal(trigger_id, user_settings, message_types, display_names, context.channel_id)
            except Exception as e:
                logger.error(f"Error opening settings modal: {e}")
                await self.im_client.send_message(context, "❌ Failed to open settings. Please try again.")
        else:
            # No trigger_id, show button to open modal
            buttons = [[
                InlineButton(
                    text="🛠️ Open Settings",
                    callback_data="open_settings_modal"
                )
            ]]
            
            keyboard = InlineKeyboard(buttons=buttons)
            
            target_context = self._get_target_context(context)
            await self.im_client.send_message_with_buttons(
                target_context,
                "⚙️ *Personalization Settings*\n\nConfigure how Claude Code messages appear in your Slack workspace.",
                keyboard,
                parse_mode='Markdown' if self.config.platform == "telegram" else 'markdown'
            )
    
    async def handle_callback_query(self, context: MessageContext, callback_data: str):
        """Handle inline keyboard callbacks"""
        try:
            # Handle settings modal open request (Slack)
            if callback_data == "open_settings_modal" and self.config.platform == "slack":
                trigger_id = context.platform_specific.get('trigger_id') if context.platform_specific else None
                if trigger_id and hasattr(self.im_client, 'open_settings_modal'):
                    settings_key = self._get_settings_key(context)
                    user_settings = self.settings_manager.get_user_settings(settings_key)
                    message_types = self.settings_manager.get_available_message_types()
                    display_names = self.settings_manager.get_message_type_display_names()
                    
                    try:
                        await self.im_client.open_settings_modal(trigger_id, user_settings, message_types, display_names, context.channel_id)
                    except Exception as e:
                        logger.error(f"Error opening settings modal: {e}")
                        await self.im_client.send_message(context, "❌ Failed to open settings. Please try again.")
                else:
                    await self.im_client.send_message(context, "❌ Unable to open settings. Please try using the /settings command.")
                return
            
            # Handle command button clicks from /start message
            elif callback_data.startswith("cmd_"):
                command = callback_data.replace("cmd_", "")
                logger.info(f"Executing command via button click: {command}")
                
                # Handle special commands
                if command == "queue_status":
                    # Merge queue and status info
                    await self.handle_queue_status(context)
                elif command == "change_cwd":
                    # Open modal for changing work directory
                    await self.handle_change_cwd_modal(context)
                elif command in self.command_handlers:
                    # Execute the standard command handler
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
• Use 📂 Change Work Dir button to set working directory
• All Claude Code operations use your specified directory
• Each channel can have its own working directory

🎛️ *Personalization:*
• Use ⚙️ Settings to customize message visibility
• Hide `system messages`, `responses`, or `results` as needed
• Settings are saved _per channel_ for Slack"""
                    
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
                
                parse_mode = 'Markdown' if self.config.platform == "telegram" else 'markdown'
                await self.im_client.send_message(context, info_text, parse_mode=parse_mode)
                return
            
            # Handle settings toggle buttons (existing functionality)
            elif callback_data.startswith("toggle_msg_"):
                # Toggle message type visibility
                msg_type = callback_data.replace("toggle_msg_", "")
                settings_key = self._get_settings_key(context)
                is_hidden = self.settings_manager.toggle_hidden_message_type(settings_key, msg_type)
                
                # Update the keyboard
                user_settings = self.settings_manager.get_user_settings(settings_key)
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
                        parse_mode='Markdown' if self.config.platform == "telegram" else 'markdown'
                    )
                
            elif callback_data == "info_msg_types":
                # Show info about message types
                formatter = self.im_client.formatter
                
                # Build info text using formatter to handle escaping properly
                lines = [
                    f"📋 {formatter.format_bold('Message Types Info:')}",
                    "",
                    f"• {formatter.format_bold('System')} - System initialization and status messages",
                    f"• {formatter.format_bold('Response')} - Tool execution responses and results",
                    f"• {formatter.format_bold('Assistant')} - Claude's messages and explanations",
                    f"• {formatter.format_bold('Result')} - Final execution results and summaries",
                    "",
                    "Hidden messages won't be sent to your IM platform."
                ]
                
                info_text = "\n".join(lines)
                
                # Send as new message
                parse_mode = 'Markdown' if self.config.platform == "telegram" else 'markdown'
                await self.im_client.send_message(context, info_text, parse_mode=parse_mode)
                
        except Exception as e:
            logger.error(f"Error handling callback query: {e}")
            await self.im_client.send_message(context, f"Error: {str(e)}")
    
    async def handle_settings_update(self, user_id: str, hidden_message_types: list, channel_id: str = None):
        """Handle settings update from modal submission (Slack)"""
        try:
            # For Slack, we need to use channel_id as the key
            # The channel_id should be passed from the modal submission context
            settings_key = channel_id if self.config.platform == "slack" and channel_id else user_id
            
            # Get current settings
            user_settings = self.settings_manager.get_user_settings(settings_key)
            
            # Update hidden message types
            user_settings.hidden_message_types = hidden_message_types
            
            # Save settings
            self.settings_manager.save_user_settings(settings_key, user_settings)
            
            logger.info(f"Updated settings for key {settings_key}: hidden types = {hidden_message_types}")
            
            # Send confirmation message (if we have a way to reach the user)
            # Note: In Slack modals, we don't have direct context to send messages
            # The modal will close automatically indicating success
            
        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            # In modal context, errors are handled differently
            raise
    
    async def handle_change_cwd_submission(self, user_id: str, new_cwd: str, channel_id: str = None):
        """Handle CWD change from modal submission (Slack)"""
        try:
            # Expand user path and get absolute path
            expanded_path = os.path.expanduser(new_cwd.strip())
            absolute_path = os.path.abspath(expanded_path)
            
            # Check if directory exists
            if not os.path.exists(absolute_path):
                # Try to create it
                try:
                    os.makedirs(absolute_path, exist_ok=True)
                    logger.info(f"Created directory: {absolute_path}")
                except Exception as e:
                    logger.error(f"Cannot create directory: {str(e)}")
                    # In modal context, we can't send error messages directly
                    # The modal will close, but we log the error
                    return
            
            if not os.path.isdir(absolute_path):
                logger.error(f"Path exists but is not a directory: {absolute_path}")
                return
            
            # For Slack, use channel_id as the settings key
            settings_key = channel_id if self.config.platform == "slack" and channel_id else user_id
            
            # Save to settings
            self.settings_manager.set_custom_cwd(settings_key, absolute_path)
            
            logger.info(f"Updated CWD for key {settings_key}: {absolute_path}")
            
            # Note: In Slack modal context, we can't send a confirmation message directly
            # The modal will close automatically, indicating success
            
        except Exception as e:
            logger.error(f"Error updating CWD: {e}")
            # In modal context, errors are handled differently
            raise
    
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