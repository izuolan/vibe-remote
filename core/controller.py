"""Core controller that coordinates between modules and handlers"""

import asyncio
import os
import logging
from typing import Optional, Dict, Any
from config.settings import AppConfig
from modules.im import BaseIMClient, MessageContext, IMFactory
from modules.im.formatters import TelegramFormatter, SlackFormatter
from modules.claude_client import ClaudeClient
from modules.session_manager import SessionManager
from modules.settings_manager import SettingsManager
from core.handlers import (
    CommandHandlers,
    SessionHandler,
    SettingsHandler,
    MessageHandler
)

logger = logging.getLogger(__name__)


class Controller:
    """Main controller that coordinates all bot operations"""
    
    def __init__(self, config: AppConfig):
        """Initialize controller with configuration"""
        self.config = config
        
        # Session tracking (must be initialized before handlers)
        self.claude_sessions: Dict[str, Any] = {}
        self.receiver_tasks: Dict[str, asyncio.Task] = {}
        self.stored_session_mappings: Dict[str, str] = {}
        
        # Initialize core modules
        self._init_modules()
        
        # Initialize handlers
        self._init_handlers()
        
        # Setup callbacks
        self._setup_callbacks()
        
        # Background task for cleanup
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # Restore session mappings on startup (after handlers are initialized)
        self.session_handler.restore_session_mappings()
    
    def _init_modules(self):
        """Initialize core modules"""
        # Create IM client with platform-specific formatter
        self.im_client: BaseIMClient = IMFactory.create_client(self.config)
        
        # Create platform-specific formatter
        if self.config.platform == "telegram":
            formatter = TelegramFormatter()
        elif self.config.platform == "slack":
            formatter = SlackFormatter()
        else:
            logger.warning(f"Unknown platform: {self.config.platform}, using Telegram formatter")
            formatter = TelegramFormatter()
        
        # Inject formatter into clients
        self.im_client.formatter = formatter
        self.claude_client = ClaudeClient(self.config.claude, formatter)
        
        # Initialize managers
        self.session_manager = SessionManager()
        self.settings_manager = SettingsManager()
    
    def _init_handlers(self):
        """Initialize all handlers with controller reference"""
        # Initialize session_handler first as other handlers depend on it
        self.session_handler = SessionHandler(self)
        self.command_handler = CommandHandlers(self)
        self.settings_handler = SettingsHandler(self)
        self.message_handler = MessageHandler(self)
        
        # Set cross-references between handlers
        self.message_handler.set_session_handler(self.session_handler)
    
    def _setup_callbacks(self):
        """Setup callback connections between modules"""
        # Create command handlers dict
        command_handlers = {
            'start': self.command_handler.handle_start,
            'clear': self.command_handler.handle_clear,
            'cwd': self.command_handler.handle_cwd,
            'set_cwd': self.command_handler.handle_set_cwd,
            'settings': self.settings_handler.handle_settings,
            'stop': self.command_handler.handle_stop
        }
        
        # Register callbacks with the IM client
        self.im_client.register_callbacks(
            on_message=self.message_handler.handle_user_message,
            on_command=command_handlers,
            on_callback_query=self.message_handler.handle_callback_query,
            on_settings_update=self.handle_settings_update,
            on_change_cwd=self.handle_change_cwd_submission
        )
    
    # Utility methods used by handlers
    
    def get_cwd(self, context: MessageContext) -> str:
        """Get working directory based on context (channel/chat)
        This is the SINGLE source of truth for CWD
        """
        # Get the settings key based on context
        settings_key = self._get_settings_key(context)
        
        # Get custom CWD from settings
        custom_cwd = self.settings_manager.get_custom_cwd(settings_key)
        
        # Use custom CWD if available, otherwise use default from .env
        if custom_cwd and os.path.exists(custom_cwd):
            return os.path.abspath(custom_cwd)
        elif custom_cwd:
            logger.warning(f"Custom CWD does not exist: {custom_cwd}, using default")
        
        # Fall back to default from .env
        default_cwd = self.config.claude.cwd
        if default_cwd:
            return os.path.abspath(os.path.expanduser(default_cwd))
        
        # Last resort: current directory
        return os.getcwd()
    
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
        if self.im_client.should_use_thread_for_reply() and context.thread_id:
            return MessageContext(
                user_id=context.user_id,
                channel_id=context.channel_id,
                thread_id=context.thread_id,
                message_id=context.message_id,
                platform_specific=context.platform_specific
            )
        return context
    
    # Settings update handler (for Slack modal)
    async def handle_settings_update(self, user_id: str, hidden_message_types: list, channel_id: str = None):
        """Handle settings update (typically from Slack modal)"""
        try:
            # Determine settings key - for Slack, always use channel_id
            if self.config.platform == "slack":
                settings_key = channel_id if channel_id else user_id  # fallback to user_id if no channel
            else:
                settings_key = channel_id if channel_id else user_id
            
            # Update settings
            user_settings = self.settings_manager.get_user_settings(settings_key)
            user_settings.hidden_message_types = hidden_message_types
            
            # Save settings - using the correct method name
            self.settings_manager.update_user_settings(settings_key, user_settings)
            
            logger.info(f"Updated settings for {settings_key}: hidden types = {hidden_message_types}")
            
            # Create context for sending confirmation (without 'message' field)
            context = MessageContext(
                user_id=user_id,
                channel_id=channel_id if channel_id else user_id,
                platform_specific={}
            )
            
            # Send confirmation
            await self.im_client.send_message(
                context,
                "✅ Settings updated successfully!"
            )
            
        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            # Create context for error message (without 'message' field)
            context = MessageContext(
                user_id=user_id,
                channel_id=channel_id if channel_id else user_id,
                platform_specific={}
            )
            await self.im_client.send_message(
                context,
                f"❌ Failed to update settings: {str(e)}"
            )
    
    # Working directory change handler (for Slack modal)
    async def handle_change_cwd_submission(self, user_id: str, new_cwd: str, channel_id: str = None):
        """Handle working directory change submission (from Slack modal) - reuse command handler logic"""
        try:
            # Create context for messages (without 'message' field which doesn't exist in MessageContext)
            context = MessageContext(
                user_id=user_id,
                channel_id=channel_id if channel_id else user_id,
                platform_specific={}
            )
            
            # Reuse the same logic from handle_set_cwd command handler
            await self.command_handler.handle_set_cwd(context, new_cwd.strip())
            
        except Exception as e:
            logger.error(f"Error changing working directory: {e}")
            # Create context for error message (without 'message' field)
            context = MessageContext(
                user_id=user_id,
                channel_id=channel_id if channel_id else user_id,
                platform_specific={}
            )
            await self.im_client.send_message(
                context,
                f"❌ Failed to change working directory: {str(e)}"
            )
    
    # Main run method
    def run(self):
        """Run the controller"""
        logger.info(f"Starting Claude Proxy Controller with {self.config.platform} platform...")
        
        # Start cleanup task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Start cleanup task
        self.cleanup_task = loop.create_task(self.periodic_cleanup())
        
        try:
            # Run the IM client (blocking)
            self.im_client.run()
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
        except Exception as e:
            logger.error(f"Error in main run loop: {e}", exc_info=True)
        finally:
            loop.run_until_complete(self.cleanup())
    
    async def periodic_cleanup(self):
        """Periodically clean up inactive sessions"""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                # Clean up completed receiver tasks
                completed_tasks = []
                for session_id, task in self.receiver_tasks.items():
                    if task.done():
                        completed_tasks.append(session_id)
                
                for session_id in completed_tasks:
                    del self.receiver_tasks[session_id]
                    logger.info(f"Cleaned up completed receiver task for session {session_id}")
                
                # Clean up inactive Claude sessions
                inactive_sessions = []
                current_time = asyncio.get_event_loop().time()
                
                for session_id, client in self.claude_sessions.items():
                    # Check if client has been inactive (customize as needed)
                    if hasattr(client, 'last_activity'):
                        if current_time - client.last_activity > 1800:  # 30 minutes
                            inactive_sessions.append(session_id)
                
                for session_id in inactive_sessions:
                    await self.session_handler.cleanup_session(session_id)
                    logger.info(f"Cleaned up inactive session {session_id}")
                
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up controller resources...")
        
        # Cancel cleanup task
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Cancel all receiver tasks
        for session_id, task in self.receiver_tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Cleanup all Claude sessions
        for session_id in list(self.claude_sessions.keys()):
            await self.session_handler.cleanup_session(session_id)
        
        # Stop IM client if it has a stop method
        if self.im_client and hasattr(self.im_client, 'stop'):
            await self.im_client.stop()
        
        logger.info("Controller cleanup complete")