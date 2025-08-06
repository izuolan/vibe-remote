import asyncio
import logging
import os
from typing import Optional, Union
from config.settings import AppConfig
from modules.im import BaseIMClient, MessageContext, InlineKeyboard, InlineButton, IMFactory
from modules.im.formatters import TelegramFormatter, SlackFormatter
from modules.claude_client import ClaudeClient
from modules.session_manager import SessionManager, UserSession
from modules.settings_manager import SettingsManager
from claude_code_sdk import ClaudeSDKClient, ClaudeCodeOptions


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
            'clear': self.handle_clear,
            'cwd': self.handle_cwd,
            'set_cwd': self.handle_set_cwd,
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
/clear - Reset session and start fresh
/cwd - Show current working directory
/set_cwd <path> - Set working directory
/settings - Personalization settings

How it works:
• Send any message and it's immediately sent to Claude Code
• Each chat maintains its own conversation context
• Use /clear to reset the conversation"""
            
            await self.im_client.send_message(context, message_text)
            return
        
        # For Slack, create interactive buttons using Block Kit
        user_name = user_info.get('real_name') or user_info.get('name') or 'User'
        
        # Create interactive buttons for commands
        buttons = [
            # Row 1: Directory management
            [
                InlineButton(text="📁 Current Dir", callback_data="cmd_cwd"),
                InlineButton(text="📂 Change Work Dir", callback_data="cmd_change_cwd")
            ],
            # Row 2: Session and Settings
            [
                InlineButton(text="🔄 Reset Session", callback_data="cmd_clear"),
                InlineButton(text="⚙️ Settings", callback_data="cmd_settings")
            ],
            # Row 3: Help
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
Use the buttons below to manage your Claude Code sessions, or simply type any message to start chatting with Claude!"""

        target_context = self._get_target_context(context)
        # For Telegram, send with MarkdownV2 parse mode
        # For Slack, use markdown
        parse_mode = 'MarkdownV2' if self.config.platform == "telegram" else 'markdown'
        await self.im_client.send_message_with_buttons(
            target_context,
            welcome_text,
            keyboard,
            parse_mode=parse_mode
        )
    
    async def handle_user_message(self, context: MessageContext, message: str):
        """Handle incoming user message"""
        try:
            # Get user's message timestamp for Slack threading
            user_message_ts = context.message_id if self.config.platform == "slack" else None
            
            # Determine session ID based on platform
            if self.config.platform == "telegram":
                # For Telegram, use chat_id as session ID
                session_id = f"telegram_{context.channel_id}"
                thread_id = None
            elif self.config.platform == "slack":
                # For Slack, determine if this is a thread reply or new message
                if context.thread_id:
                    # This is a reply in an existing thread - use thread root as session ID
                    thread_id = context.thread_id
                    session_id = f"slack_{thread_id}"
                else:
                    # This is a new message in channel - use message timestamp as thread/session ID
                    thread_id = user_message_ts
                    session_id = f"slack_{thread_id}"
            else:
                # Fallback to user-based session
                session_id = f"{self.config.platform}_{context.user_id}"
                thread_id = None
            
            # Get or create session
            session = await self.session_manager.get_or_create_session(context.user_id, context.channel_id)
            
            # Check if this is a new session or if the session is ready for new input
            is_new_session = session_id not in session.claude_clients
            is_session_active = session.session_active.get(session_id, False)
            
            # Only send confirmation for new sessions or if session is not active
            if is_new_session or not is_session_active:
                target_context = self._get_target_context(context)
                
                if self.config.platform == "slack":
                    # For Slack, send to the thread
                    if user_message_ts:
                        target_context.thread_id = user_message_ts
                    
                    confirmation_text = f"⏳ Processing..."
                    await self.im_client.send_message(
                        target_context,
                        confirmation_text,
                        parse_mode='markdown',
                        reply_to=user_message_ts
                    )
                else:
                    # For non-Slack platforms
                    formatter = self.im_client.formatter
                    confirmation_text = f"⏳ {formatter.format_text('Processing...')}"
                    await self.im_client.send_message(
                        target_context,
                        confirmation_text,
                        parse_mode='MarkdownV2'
                    )
            
            # Check if we have a client for this session
            if session_id not in session.claude_clients:
                # Check if we have a saved Claude session_id to resume
                claude_session_id = self.settings_manager.get_claude_session_id(context.user_id, session_id)
                
                # Get user's custom CWD from settings if available
                settings_key = self._get_settings_key(context)
                custom_cwd = self.settings_manager.get_custom_cwd(settings_key)
                working_directory = custom_cwd if custom_cwd else self.config.claude.cwd
                
                # Create new Claude SDK client with resume if available
                options = ClaudeCodeOptions(
                    permission_mode=self.config.claude.permission_mode,
                    cwd=working_directory,
                    system_prompt=self.config.claude.system_prompt,
                    # Use resume instead of continue_conversation
                    resume=claude_session_id if claude_session_id else None
                )
                
                client = ClaudeSDKClient(options=options)
                await client.connect()
                session.claude_clients[session_id] = client
                
                if claude_session_id:
                    logger.info(f"Resumed Claude session {claude_session_id} for {session_id}")
                else:
                    logger.info(f"Created new Claude SDK client for session {session_id}")
                
                # Start persistent receiver for this session
                receiver_task = asyncio.create_task(
                    self._session_message_receiver(session_id, client, context, thread_id)
                )
                session.receiver_tasks[session_id] = receiver_task
            
            # Check if session is active (waiting for result)
            if is_session_active:
                # Session is active, just send the message without confirmation
                await self.process_message_immediately(context, message, session_id, thread_id, skip_confirmation=True)
            else:
                # Session is not active or new, send with normal flow
                await self.process_message_immediately(context, message, session_id, thread_id)
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            # Format error message using formatter
            formatter = self.im_client.formatter
            error_msg = formatter.format_error("Error processing message")
            await self.im_client.send_message(context, error_msg)
    
    async def _session_message_receiver(self, session_id: str, client: ClaudeSDKClient, context: MessageContext, thread_id: Optional[str]):
        """Persistent message receiver for a session"""
        try:
            logger.info(f"Starting message receiver for session {session_id}")
            target_context = self._get_target_context(context)
            if thread_id:
                target_context.thread_id = thread_id
            
            async for message in client.receive_messages():
                # First check for SystemMessage init to capture session_id
                if hasattr(message, "__class__") and message.__class__.__name__ == "SystemMessage":
                    if hasattr(message, 'subtype') and message.subtype == 'init':
                        if hasattr(message, 'data') and 'session_id' in message.data:
                            claude_session_id = message.data['session_id']
                            # Store the mapping
                            self.settings_manager.set_session_mapping(
                                context.user_id, 
                                session_id,  # Our internal session ID (e.g., telegram_12345)
                                claude_session_id  # Claude's actual session ID
                            )
                            logger.info(f"Captured Claude session_id: {claude_session_id} for {session_id}")
                
                if self.claude_client._is_skip_message(message):
                    continue
                
                # Determine message type
                message_type = None
                if hasattr(message, "__class__"):
                    class_name = message.__class__.__name__
                    if class_name == "SystemMessage":
                        message_type = "system"
                    elif class_name == "UserMessage":
                        message_type = "user"
                    elif class_name == "AssistantMessage":
                        message_type = "assistant"
                    elif class_name == "ResultMessage":
                        message_type = "result"
                
                # Check if this message type should be hidden
                settings_key = self._get_settings_key(context)
                if message_type and self.settings_manager.is_message_type_hidden(settings_key, message_type):
                    logger.info(f"Skipping {message_type} message for settings key {settings_key} (hidden in settings)")
                    continue
                
                # Format and send message
                formatted_message = self.claude_client.format_message(message)
                if formatted_message and formatted_message.strip():
                    parse_mode = 'markdown' if self.config.platform == "slack" else 'MarkdownV2'
                    await self.im_client.send_message(
                        target_context,
                        formatted_message,
                        parse_mode=parse_mode,
                        reply_to=thread_id if self.config.platform == "slack" else None
                    )
                
                # Check if this was a ResultMessage (query complete)
                if message_type == "result":
                    # Mark session as not active
                    session = await self.session_manager.get_or_create_session(context.user_id, context.channel_id)
                    if session:
                        session.session_active[session_id] = False
                    
                    # Format ready message using formatter
                    formatter = self.im_client.formatter
                    ready_msg = formatter.format_success("Ready for next message!")
                    await self.im_client.send_message(
                        target_context,
                        ready_msg,
                        reply_to=thread_id if self.config.platform == "slack" else None
                    )
                    
        except asyncio.CancelledError:
            logger.info(f"Message receiver for session {session_id} was cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in message receiver for session {session_id}: {e}")
            # Notify user of error
            try:
                formatter = self.im_client.formatter
                error_text = formatter.format_text(f"Session error: {str(e)}")
                instruction = formatter.format_text("Please use /clear to reset.")
                error_msg = f"❌ {error_text}\n{instruction}"
                    
                await self.im_client.send_message(
                    target_context,
                    error_msg,
                    reply_to=thread_id if self.config.platform == "slack" else None
                )
            except:
                pass
    
    async def process_message_immediately(self, context: MessageContext, message: str, session_id: str, thread_id: Optional[str], skip_confirmation: bool = False):
        """Send message to Claude immediately"""
        try:
            # Get session
            session = await self.session_manager.get_or_create_session(context.user_id, context.channel_id)
            
            # Get the client for this session
            client = session.claude_clients[session_id]
            
            # Send the message to Claude
            try:
                # Mark session as active
                session.session_active[session_id] = True
                
                await client.query(message, session_id=session_id)
                logger.info(f"Sent message to Claude for session {session_id}")
            except Exception as e:
                logger.error(f"Error sending message to Claude: {e}")
                
                # Clean up broken session
                await self._cleanup_session(session, session_id)
                
                # Notify user
                target_context = self._get_target_context(context)
                formatter = self.im_client.formatter
                error_text = formatter.format_text(f"Error: {str(e)}")
                instruction = formatter.format_text("Please try again or use /clear to reset.")
                error_msg = f"❌ {error_text}\n{instruction}"
                    
                await self.im_client.send_message(
                    target_context,
                    error_msg,
                    reply_to=thread_id if self.config.platform == "slack" else None
                )
                
        except Exception as e:
            logger.error(f"Error in process_message_immediately: {e}")
            target_context = self._get_target_context(context)
            formatter = self.im_client.formatter
            error_msg = formatter.format_error(f"Unexpected error: {str(e)}")
                
            await self.im_client.send_message(
                target_context,
                error_msg
            )
    
    async def _cleanup_session(self, session: UserSession, session_id: str) -> None:
        """Clean up a broken Claude session"""
        # Cancel receiver task if exists
        if session_id in session.receiver_tasks:
            session.receiver_tasks[session_id].cancel()
            del session.receiver_tasks[session_id]
            
        # Disconnect and remove Claude client if exists
        if session_id in session.claude_clients:
            try:
                await session.claude_clients[session_id].disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting Claude client: {e}")
            del session.claude_clients[session_id]
            
        # Remove session active status
        if session_id in session.session_active:
            del session.session_active[session_id]
            
        logger.info(f"Cleaned up session {session_id}")
    
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
    
    
    async def handle_clear(self, context: MessageContext, args: str = ""):
        """Handle clear command - now clears session and disconnects Claude client"""
        try:
            # Determine session ID to clear mapping
            if self.config.platform == "telegram":
                session_id = f"telegram_{context.channel_id}"
            elif self.config.platform == "slack" and context.thread_id:
                session_id = f"slack_{context.thread_id}"
            else:
                session_id = f"{self.config.platform}_{context.user_id}"
            
            # Clear all session mappings for Slack (since we clear all sessions)
            if self.config.platform == "slack":
                user_settings = self.settings_manager.get_user_settings(context.user_id)
                for mapping_id in list(user_settings.session_mappings.keys()):
                    self.settings_manager.clear_session_mapping(context.user_id, mapping_id)
            else:
                # For other platforms, clear specific session mapping
                self.settings_manager.clear_session_mapping(context.user_id, session_id)
            
            # Clear session and disconnect clients
            response = await self.session_manager.clear_session(context.user_id)
            logger.info(f"User {context.user_id} cleared session")
            
            # Add reset message
            full_response = f"{response}\n🔄 Claude session has been reset."
            
            # Send the complete response
            await self.im_client.send_message(context, full_response)
            logger.info(f"Sent clear response to user {context.user_id}")
            
        except Exception as e:
            logger.error(f"Error clearing session: {e}", exc_info=True)
            try:
                await self.im_client.send_message(context, f"❌ Error clearing session: {str(e)}")
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}", exc_info=True)
    
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
            
            parse_mode = 'MarkdownV2' if self.config.platform == "telegram" else 'markdown'
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
                parse_mode = 'MarkdownV2' if self.config.platform == "telegram" else 'markdown'
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
            parse_mode = 'MarkdownV2' if self.config.platform == "telegram" else 'markdown'
            await self.im_client.send_message(context, response_text, parse_mode=parse_mode)
            
        except Exception as e:
            logger.error(f"Error setting cwd: {e}")
            await self.im_client.send_message(context, f"❌ Error setting working directory: {str(e)}")
    
    
    
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
            parse_mode='MarkdownV2' if self.config.platform == "telegram" else 'markdown'
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
                parse_mode='MarkdownV2' if self.config.platform == "telegram" else 'markdown'
            )
    
    async def handle_callback_query(self, context: MessageContext, callback_data: str):
        """Handle inline keyboard callbacks"""
        logger.info(f"handle_callback_query called with data: {callback_data} for user {context.user_id}")
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
                if command == "change_cwd":
                    # Open modal for changing work directory
                    await self.handle_change_cwd_modal(context)
                elif command in self.command_handlers:
                    # Execute the standard command handler
                    handler = self.command_handlers[command]
                    await handler(context, "")
                else:
                    await self.im_client.send_message(context, f"❌ Unknown command: {command}")
                return
            
            # Handle info button clicks from /start message (but not info_msg_types)
            elif callback_data.startswith("info_") and callback_data != "info_msg_types":
                if callback_data == "info_how_it_works":
                    info_text = """📚 *How Claude Code Bot Works:*

🔄 *Message Processing:*
• Send any message and it's immediately processed by Claude Code
• Conversations maintain context within the same chat/thread
• Each message is sent to Claude Code for execution

⚡ *Real-time Interaction:*
• Messages are processed immediately as you send them
• Claude Code maintains persistent sessions for continuous conversation
• You can send multiple messages without waiting

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

*📁 Directory Management:*
• `/cwd` or 📁 - Show current working directory
• `/set_cwd <path>` - Change working directory

*⚙️ Configuration:*
• `/settings` or ⚙️ - Open personalization settings
• `/start` - Show this welcome screen

*💬 Three Ways to Use:*
• *Direct commands*: Use slash commands like `/cwd`
• *Button clicks*: Click buttons in this interface
• *Natural messages*: Just type your request normally
• *Channel mentions*: Type `@BotName your message here`

_Tip: All commands work in DMs, channels, and threads!_"""
                
                # Send the info message for either info button
                parse_mode = 'MarkdownV2' if self.config.platform == "telegram" else 'markdown'
                await self.im_client.send_message(context, info_text, parse_mode=parse_mode)
                return
            
            # Handle settings toggle buttons (existing functionality)
            if callback_data.startswith("toggle_msg_"):
                # Toggle message type visibility
                msg_type = callback_data.replace("toggle_msg_", "")
                settings_key = self._get_settings_key(context)
                is_hidden = self.settings_manager.toggle_hidden_message_type(settings_key, msg_type)
                
                # Update the keyboard
                user_settings = self.settings_manager.get_user_settings(settings_key)
                message_types = self.settings_manager.get_available_message_types()
                display_names = self.settings_manager.get_message_type_display_names()
                
                buttons = []
                row = []
                
                for i, mt in enumerate(message_types):
                    is_hidden_now = mt in user_settings.hidden_message_types
                    checkbox = "☑️" if is_hidden_now else "⬜"
                    display_name = display_names.get(mt, mt)
                    button = InlineButton(
                        text=f"{checkbox} Hide {display_name}",
                        callback_data=f"toggle_msg_{mt}"
                    )
                    row.append(button)
                    
                    # Create 2x2 layout
                    if len(row) == 2 or i == len(message_types) - 1:
                        buttons.append(row)
                        row = []
                
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
                        parse_mode='MarkdownV2' if self.config.platform == "telegram" else 'markdown'
                    )
                
            elif callback_data == "info_msg_types":
                # Show info about message types
                logger.info(f"Handling info_msg_types callback for user {context.user_id}")
                
                try:
                    formatter = self.im_client.formatter
                    
                    # Use the new format_info_message method for clean, platform-agnostic formatting
                    info_text = formatter.format_info_message(
                        title="Message Types Info:",
                        emoji="📋",
                        items=[
                            ("System", "System initialization and status messages"),
                            ("Response", "Tool execution responses and results"),
                            ("Assistant", "Claude's messages and explanations"),
                            ("Result", "Final execution results and summaries")
                        ],
                        footer="Hidden messages won't be sent to your IM platform."
                    )
                    
                    # Send as new message
                    parse_mode = 'MarkdownV2' if self.config.platform == "telegram" else 'markdown'
                    await self.im_client.send_message(context, info_text, parse_mode=parse_mode)
                    logger.info(f"Sent info_msg_types message to user {context.user_id}")
                    
                except Exception as e:
                    logger.error(f"Error in info_msg_types handler: {e}", exc_info=True)
                    await self.im_client.send_message(context, "❌ Error showing message types info")
                
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
    
    async def _initialize_sessions(self):
        """Initialize and restore session mappings on startup"""
        logger.info("Initializing session mappings from saved settings...")
        
        # The settings are already loaded by SettingsManager on init
        # Log the loaded session mappings for debugging
        restored_count = 0
        
        for user_id, user_settings in self.settings_manager.settings.items():
            if user_settings.session_mappings:
                logger.info(f"Found {len(user_settings.session_mappings)} session mappings for user {user_id}")
                # Log each mapping for debugging
                for im_session_id, claude_session_id in user_settings.session_mappings.items():
                    logger.info(f"  - {im_session_id} -> {claude_session_id}")
                    restored_count += 1
        
        logger.info(f"Session restoration complete. Restored {restored_count} session mappings.")
    
    def run(self):
        """Run the controller"""
        logger.info(f"Starting Claude Proxy Controller with {self.config.platform} platform...")
        
        # Start cleanup task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Initialize sessions before starting
        loop.run_until_complete(self._initialize_sessions())
        
        self.cleanup_task = loop.create_task(self.periodic_cleanup())
        
        # Run the IM client
        self.im_client.run()