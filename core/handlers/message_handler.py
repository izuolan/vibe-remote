"""Message routing and Claude communication handlers"""

import asyncio
import logging
import os
from typing import Optional, Dict, Any, List
from modules.im import MessageContext
logger = logging.getLogger(__name__)


class MessageHandler:
    """Handles message routing and Claude communication"""
    
    def __init__(self, controller):
        """Initialize with reference to main controller"""
        self.controller = controller
        self.config = controller.config
        self.im_client = controller.im_client
        self.session_manager = controller.session_manager
        self.settings_manager = controller.settings_manager
        self.formatter = controller.im_client.formatter
        self.session_handler = None  # Will be set after creation
        self.receiver_tasks = controller.receiver_tasks
    
    def set_session_handler(self, session_handler):
        """Set reference to session handler"""
        self.session_handler = session_handler
    
    def _get_settings_key(self, context: MessageContext) -> str:
        """Get settings key based on context"""
        if self.config.platform == "slack":
            # For Slack, always use channel_id as the key
            return context.channel_id
        elif self.config.platform == "telegram":
            # For Telegram groups, use channel_id; for DMs use user_id
            if context.channel_id != context.user_id:
                return context.channel_id
            return context.user_id
        return context.user_id
    
    def _get_target_context(self, context: MessageContext) -> MessageContext:
        """Get target context for sending messages"""
        # For Slack, use thread for replies if enabled
        if self.im_client.should_use_thread_for_reply() and context.thread_id:
            return MessageContext(
                user_id=context.user_id,
                channel_id=context.channel_id,
                thread_id=context.thread_id,
                message=context.message,
                platform_specific=context.platform_specific
            )
        return context
    
    def get_relative_path(self, abs_path: str) -> str:
        """Convert absolute path to relative path from working directory"""
        try:
            # Always use config.claude.cwd as the single source of truth
            cwd = self.config.claude.cwd
            cwd = os.path.abspath(os.path.expanduser(cwd))
            
            # Convert input path to absolute
            abs_path = os.path.abspath(os.path.expanduser(abs_path))
            
            # Try to get relative path
            rel_path = os.path.relpath(abs_path, cwd)
            
            # If relative path goes up too many directories, use absolute
            if rel_path.startswith("../.."):
                return abs_path
            
            return rel_path
        except Exception:
            # If any error, return original path
            return abs_path
    
    async def handle_user_message(self, context: MessageContext, message: str):
        """Process regular user messages and send to Claude"""
        try:
            # Get or create Claude session
            base_session_id, working_path, composite_key = self.session_handler.get_session_info(context)
            client = await self.session_handler.get_or_create_claude_session(context)
            
            # Send immediate acknowledgment for better UX
            ack_message = await self.im_client.send_message(
                context,
                "📨 Message received, processing..."
            )
            
            # Send message to Claude
            await client.query(message, session_id=composite_key)
            logger.info(f"Sent message to Claude for session {composite_key}")
            
            # Delete acknowledgment message
            if ack_message and hasattr(self.im_client, 'delete_message'):
                try:
                    await self.im_client.delete_message(context.channel_id, ack_message)
                except Exception as e:
                    logger.debug(f"Could not delete ack message: {e}")
            
            # Start receiver if not already running
            if composite_key not in self.receiver_tasks or self.receiver_tasks[composite_key].done():
                logger.info(f"Starting message receiver for session {composite_key}")
                self.receiver_tasks[composite_key] = asyncio.create_task(
                    self._receive_messages(client, base_session_id, working_path, context)
                )
            
        except Exception as e:
            logger.error(f"Error processing user message: {e}", exc_info=True)
            _, _, composite_key = self.session_handler.get_session_info(context)
            await self.session_handler.handle_session_error(composite_key, context, e)
    
    async def _receive_messages(self, client, base_session_id: str, working_path: str, context: MessageContext):
        """Receive messages from Claude SDK client"""
        try:
            settings_key = self._get_settings_key(context)
            settings = self.settings_manager.get_user_settings(settings_key)
            target_context = self._get_target_context(context)
            
            async for message in client.receive_messages():
                try:
                    # Check for SystemMessage init to capture session_id
                    if hasattr(message, "__class__") and message.__class__.__name__ == "SystemMessage":
                        if hasattr(message, 'subtype') and message.subtype == 'init':
                            if hasattr(message, 'data') and 'session_id' in message.data:
                                claude_session_id = message.data['session_id']
                                # Get correct settings key based on platform
                                settings_key = self._get_settings_key(context)
                                self.session_handler.capture_session_id(
                                    base_session_id,
                                    working_path, 
                                    claude_session_id,
                                    settings_key
                                )
                    
                    # Skip certain messages
                    if hasattr(self.controller, 'claude_client') and self.controller.claude_client._is_skip_message(message):
                        continue
                    
                    # Determine message type by class name
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
                    if message_type and self.settings_manager.is_message_type_hidden(settings_key, message_type):
                        logger.info(f"Skipping {message_type} message for settings key {settings_key} (hidden in settings)")
                        continue
                    
                    # Format and send message using claude_client
                    if hasattr(self.controller, 'claude_client'):
                        formatted_message = self.controller.claude_client.format_message(message)
                        if formatted_message and formatted_message.strip():
                            await self.im_client.send_message(
                                target_context,
                                formatted_message
                            )
                    
                    # Check if this was a ResultMessage (query complete)
                    if message_type == "result":
                        # Mark session as not active
                        session = await self.controller.session_manager.get_or_create_session(
                            context.user_id, 
                            context.channel_id
                        )
                        if session:
                            composite_key = f"{base_session_id}:{working_path}"
                            session.session_active[composite_key] = False
                    
                except Exception as e:
                    logger.error(f"Error processing message from Claude: {e}", exc_info=True)
                    # Continue processing other messages
                    continue
            
        except Exception as e:
            composite_key = f"{base_session_id}:{working_path}"
            logger.error(f"Error in message receiver for session {composite_key}: {e}", exc_info=True)
            await self.session_handler.handle_session_error(composite_key, context, e)
    
    async def handle_callback_query(self, context: MessageContext, callback_data: str):
        """Route callback queries to appropriate handlers"""
        try:
            logger.info(f"handle_callback_query called with data: {callback_data} for user {context.user_id}")
            
            # Import handlers to avoid circular dependency
            from .settings_handler import SettingsHandler
            from .command_handlers import CommandHandlers
            
            settings_handler = SettingsHandler(self.controller)
            command_handlers = CommandHandlers(self.controller)
            
            # Route based on callback data
            if callback_data.startswith("toggle_msg_"):
                # Toggle message type visibility
                msg_type = callback_data.replace("toggle_msg_", "")
                await settings_handler.handle_toggle_message_type(context, msg_type)
            elif callback_data.startswith("toggle_"):
                # Legacy toggle handler (if any)
                setting_type = callback_data.replace("toggle_", "")
                if hasattr(settings_handler, 'handle_toggle_setting'):
                    await settings_handler.handle_toggle_setting(context, setting_type)
            
            elif callback_data == "info_msg_types":
                logger.info(f"Handling info_msg_types callback for user {context.user_id}")
                await settings_handler.handle_info_message_types(context)
            
            elif callback_data == "info_how_it_works":
                await settings_handler.handle_info_how_it_works(context)
            
            elif callback_data == "cmd_cwd":
                await command_handlers.handle_cwd(context)
            
            elif callback_data == "cmd_change_cwd":
                await command_handlers.handle_change_cwd_modal(context)
            
            elif callback_data == "cmd_clear":
                await command_handlers.handle_clear(context)
            
            elif callback_data == "cmd_settings":
                await settings_handler.handle_settings(context)
            
            elif callback_data.startswith("info_") and callback_data != "info_msg_types":
                # Generic info handler
                info_type = callback_data.replace("info_", "")
                info_text = self.formatter.format_info_message(
                    title=f"Info: {info_type}",
                    emoji="ℹ️",
                    footer="This feature is coming soon!"
                )
                await self.im_client.send_message(context, info_text)
            
            else:
                logger.warning(f"Unknown callback data: {callback_data}")
                await self.im_client.send_message(
                    context,
                    self.formatter.format_warning(f"Unknown action: {callback_data}")
                )
                
        except Exception as e:
            logger.error(f"Error handling callback query: {e}", exc_info=True)
            await self.im_client.send_message(
                context,
                self.formatter.format_error(f"Error processing action: {str(e)}")
            )