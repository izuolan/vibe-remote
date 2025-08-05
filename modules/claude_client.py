import logging
import os
from typing import Callable, Optional
from claude_code_sdk import (
    query,
    ClaudeCodeOptions,
    SystemMessage,
    AssistantMessage,
    UserMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
)
from config import ClaudeConfig
from modules.im.formatters import BaseMarkdownFormatter, TelegramFormatter


logger = logging.getLogger(__name__)


class ClaudeClient:
    def __init__(self, config: ClaudeConfig, formatter: Optional[BaseMarkdownFormatter] = None):
        self.config = config
        self.formatter = formatter or TelegramFormatter()  # Default to Telegram for backward compatibility
        self.options = ClaudeCodeOptions(
            permission_mode=config.permission_mode,
            cwd=config.cwd,
            continue_conversation=config.continue_conversation,
            system_prompt=config.system_prompt,
        )

    def format_message(self, message) -> str:
        """Format different types of messages according to specified rules"""
        try:
            if isinstance(message, SystemMessage):
                return self._format_system_message(message)
            elif isinstance(message, AssistantMessage):
                return self._format_assistant_message(message)
            elif isinstance(message, UserMessage):
                return self._format_user_message(message)
            elif isinstance(message, ResultMessage):
                return self._format_result_message(message)
            else:
                return self.formatter.format_warning(
                    f"Unknown message type: {type(message)}"
                )
        except Exception as e:
            logger.error(f"Error formatting message: {e}")
            return self.formatter.format_error(f"Error formatting message: {str(e)}")

    def _process_content_blocks(self, content_blocks) -> list:
        """Process content blocks (TextBlock, ToolUseBlock) and return formatted parts"""
        formatted_parts = []

        for block in content_blocks:
            if isinstance(block, TextBlock):
                # Escape text content using formatter
                escaped_text = self.formatter.escape_special_chars(block.text)
                formatted_parts.append(escaped_text)
            elif isinstance(block, ToolUseBlock):
                tool_info = self._format_tool_use_block(block)
                formatted_parts.append(tool_info)
            elif isinstance(block, ToolResultBlock):
                result_info = self._format_tool_result_block(block)
                formatted_parts.append(result_info)

        return formatted_parts

    def _get_relative_path(self, full_path: str) -> str:
        """Convert absolute path to relative path based on ClaudeCode cwd"""
        # Get ClaudeCode's current working directory
        cwd = self.options.cwd or os.getcwd()

        # Normalize paths for consistent comparison
        cwd = os.path.normpath(cwd)
        full_path = os.path.normpath(full_path)

        try:
            # If the path starts with cwd, make it relative
            if full_path.startswith(cwd + os.sep) or full_path == cwd:
                relative = os.path.relpath(full_path, cwd)
                # Use "./" prefix for current directory files
                if not relative.startswith(".") and relative != ".":
                    relative = "./" + relative
                return relative
            else:
                # If not under cwd, just return the path as is
                return full_path
        except:
            # Fallback to original path if any error
            return full_path

    def _format_tool_use_block(self, block: ToolUseBlock) -> str:
        """Format ToolUseBlock using formatter"""
        # Use formatter's format_tool_use method
        return self.formatter.format_tool_use(
            block.name, 
            block.input,
            get_relative_path=self._get_relative_path
        )

    def _format_tool_result_block(self, block: ToolResultBlock) -> str:
        """Format ToolResultBlock using formatter"""
        return self.formatter.format_tool_result(block.is_error, block.content)

    def _format_system_message(self, message: SystemMessage) -> str:
        """Format SystemMessage using formatter"""
        cwd = message.data.get("cwd", "Unknown")
        return self.formatter.format_system_message(cwd, message.subtype)

    def _format_assistant_message(self, message: AssistantMessage) -> str:
        """Format AssistantMessage using formatter"""
        content_parts = self._process_content_blocks(message.content)
        return self.formatter.format_assistant_message(content_parts)

    def _format_user_message(self, message: UserMessage) -> str:
        """Format UserMessage using formatter"""
        content_parts = self._process_content_blocks(message.content)
        return self.formatter.format_user_message(content_parts)

    def _format_result_message(self, message: ResultMessage) -> str:
        """Format ResultMessage using formatter"""
        return self.formatter.format_result_message(
            message.subtype,
            message.duration_ms,
            message.result
        )

    def _is_skip_message(self, message) -> bool:
        """Check if the message should be skipped"""
        if isinstance(message, AssistantMessage):
            if not message.content:
                return True
        elif isinstance(message, UserMessage):
            if not message.content:
                return True
        return False

    async def stream_execute(
        self, prompt: str, on_message: Callable, user_id: int = None
    ):
        """Execute query with streaming output"""
        try:
            async for message in query(prompt=prompt, options=self.options):
                if self._is_skip_message(message):
                    continue

                # Determine message type for filtering (simplified to main categories)
                message_type = None
                if hasattr(message, "__class__"):
                    class_name = message.__class__.__name__
                    if class_name == "SystemMessage":
                        message_type = "system"
                    elif class_name == "UserMessage":
                        message_type = "user"  # This shows tool responses
                    elif class_name == "AssistantMessage":
                        message_type = "assistant"
                    elif class_name == "ResultMessage":
                        message_type = "result"

                formatted_message = self.format_message(message)
                if formatted_message and formatted_message.strip():
                    await on_message(formatted_message, message_type)
        except Exception as e:
            logger.error(f"Error in streaming execution: {e}")
            await on_message(
                f"❌ Error: {str(e)}", "system"
            )  # Error messages go to system category
            raise
