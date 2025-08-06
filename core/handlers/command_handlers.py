"""Command handlers for bot commands like /start, /clear, /cwd, etc."""

import os
import logging
from typing import Optional
from modules.im import MessageContext, InlineKeyboard, InlineButton

logger = logging.getLogger(__name__)


class CommandHandlers:
    """Handles all bot command operations"""

    def __init__(self, controller):
        """Initialize with reference to main controller"""
        self.controller = controller
        self.config = controller.config
        self.im_client = controller.im_client
        self.session_manager = controller.session_manager
        self.settings_manager = controller.settings_manager

    async def handle_start(self, context: MessageContext, args: str = ""):
        """Handle /start command with interactive buttons"""
        platform_name = self.config.platform.capitalize()

        # Get user and channel info
        try:
            user_info = await self.im_client.get_user_info(context.user_id)
        except Exception as e:
            logger.warning(f"Failed to get user info: {e}")
            user_info = {"id": context.user_id}

        try:
            channel_info = await self.im_client.get_channel_info(context.channel_id)
        except Exception as e:
            logger.warning(f"Failed to get channel info: {e}")
            channel_info = {
                "id": context.channel_id,
                "name": (
                    "Direct Message"
                    if context.channel_id.startswith("D")
                    else context.channel_id
                ),
            }

        # For non-Slack platforms, use traditional text message
        if self.config.platform != "slack":
            formatter = self.im_client.formatter

            # Build welcome message using formatter to handle escaping properly
            lines = [
                formatter.format_bold("Welcome to Claude Code Remote Control Bot!"),
                "",
                f"Platform: {formatter.format_text(platform_name)}",
                f"User ID: {formatter.format_code_inline(context.user_id)}",
                f"Channel/Chat ID: {formatter.format_code_inline(context.channel_id)}",
                "",
                formatter.format_bold("Commands:"),
                formatter.format_text("/start - Show this message"),
                formatter.format_text("/clear - Reset session and start fresh"),
                formatter.format_text("/cwd - Show current working directory"),
                formatter.format_text("/set_cwd <path> - Set working directory"),
                formatter.format_text("/settings - Personalization settings"),
                "",
                formatter.format_bold("How it works:"),
                formatter.format_text(
                    "• Send any message and it's immediately sent to Claude Code"
                ),
                formatter.format_text(
                    "• Each chat maintains its own conversation context"
                ),
                formatter.format_text("• Use /clear to reset the conversation"),
            ]

            message_text = formatter.format_message(*lines)
            await self.im_client.send_message(context, message_text)
            return

        # For Slack, create interactive buttons using Block Kit
        user_name = user_info.get("real_name") or user_info.get("name") or "User"

        # Create interactive buttons for commands
        buttons = [
            # Row 1: Directory management
            [
                InlineButton(text="📁 Current Dir", callback_data="cmd_cwd"),
                InlineButton(text="📂 Change Work Dir", callback_data="cmd_change_cwd"),
            ],
            # Row 2: Session and Settings
            [
                InlineButton(text="🔄 Reset Session", callback_data="cmd_clear"),
                InlineButton(text="⚙️ Settings", callback_data="cmd_settings"),
            ],
            # Row 3: Help
            [InlineButton(text="ℹ️ How it Works", callback_data="info_how_it_works")],
        ]

        keyboard = InlineKeyboard(buttons=buttons)

        welcome_text = f"""🎉 **Welcome to Claude Code Remote Control Bot!**

👋 Hello **{user_name}**!
🔧 Platform: **{platform_name}**
📍 Channel: **{channel_info.get('name', 'Unknown')}**

**Quick Actions:**
Use the buttons below to manage your Claude Code sessions, or simply type any message to start chatting with Claude!"""

        target_context = self.controller._get_target_context(context)
        await self.im_client.send_message_with_buttons(
            target_context, welcome_text, keyboard
        )

    async def handle_clear(self, context: MessageContext, args: str = ""):
        """Handle clear command - clears session and disconnects Claude client"""
        try:
            # Import SessionHandler to get base session ID
            from core.handlers.session_handler import SessionHandler

            # Create temporary handler to get base session ID
            temp_handler = SessionHandler(self.controller)
            base_session_id = temp_handler.get_base_session_id(context)

            # Clear all path mappings for this base session
            self.settings_manager.clear_session_mapping(
                context.user_id, base_session_id
            )

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
                await self.im_client.send_message(
                    context, f"❌ Error clearing session: {str(e)}"
                )
            except Exception as send_error:
                logger.error(
                    f"Failed to send error message: {send_error}", exc_info=True
                )

    async def handle_cwd(self, context: MessageContext, args: str = ""):
        """Handle cwd command - show current working directory"""
        try:
            # Simple: use the single global CWD
            current_cwd = self.config.claude.cwd
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

            status_lines.append("💡 This is where Claude Code will execute commands")

            # Combine all parts
            response_text = path_line + "\n" + "\n".join(status_lines)

            await self.im_client.send_message(context, response_text)
        except Exception as e:
            logger.error(f"Error getting cwd: {e}")
            await self.im_client.send_message(
                context, f"Error getting working directory: {str(e)}"
            )

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
                    await self.im_client.send_message(
                        context, f"❌ Cannot create directory: {str(e)}"
                    )
                    return

            if not os.path.isdir(absolute_path):
                formatter = self.im_client.formatter
                error_text = f"❌ Path exists but is not a directory: {formatter.format_code_inline(absolute_path)}"
                await self.im_client.send_message(context, error_text)
                return

            # Update the global config directly
            self.config.claude.cwd = absolute_path

            # Also save to user settings for persistence
            settings_key = self.controller._get_settings_key(context)
            settings = self.settings_manager.get_user_settings(settings_key)
            settings.custom_cwd = absolute_path
            self.settings_manager.update_user_settings(settings_key, settings)

            logger.info(f"User {context.user_id} changed cwd to: {absolute_path}")

            formatter = self.im_client.formatter
            response_text = (
                f"✅ Working directory changed to:\n"
                f"{formatter.format_code_inline(absolute_path)}"
            )
            await self.im_client.send_message(context, response_text)

        except Exception as e:
            logger.error(f"Error setting cwd: {e}")
            await self.im_client.send_message(
                context, f"❌ Error setting working directory: {str(e)}"
            )

    async def handle_change_cwd_modal(self, context: MessageContext):
        """Handle Change Work Dir button - open modal for Slack"""
        if self.config.platform != "slack":
            # For non-Slack platforms, just send instructions
            await self.im_client.send_message(
                context,
                "📂 To change working directory, use:\n`/set_cwd <path>`\n\nExample:\n`/set_cwd ~/projects/myapp`",
            )
            return

        # For Slack, open a modal dialog
        trigger_id = (
            context.platform_specific.get("trigger_id")
            if context.platform_specific
            else None
        )

        if trigger_id and hasattr(self.im_client, "open_change_cwd_modal"):
            try:
                # Get current CWD to show in modal
                current_cwd = self.config.claude.cwd

                await self.im_client.open_change_cwd_modal(
                    trigger_id, current_cwd, context.channel_id
                )
            except Exception as e:
                logger.error(f"Error opening change CWD modal: {e}")
                await self.im_client.send_message(
                    context,
                    "❌ Failed to open directory change dialog. Please try again.",
                )
        else:
            # No trigger_id, show instructions
            await self.im_client.send_message(
                context,
                "📂 Click the 'Change Work Dir' button in the /start menu to change working directory.",
            )
