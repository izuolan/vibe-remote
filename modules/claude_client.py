import logging
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
        import os

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
        """Format ToolUseBlock with specific adaptations for different tools"""
        escaped_name = self.formatter.escape_special_chars(block.name)

        # Get tool emoji and format based on tool type
        if block.name.startswith("mcp__"):
            # MCP tools - unified handling
            tool_category = block.name.split("__")[1] if "__" in block.name else "mcp"
            emoji_map = {
                "devmcp": "🔧",
                "db": "🗃️",
                "log": "📊",
                "ops": "⚡",
                "human": "👤",
            }
            emoji = emoji_map.get(tool_category, "🔧")
            tool_info = f"{emoji} {self.formatter.format_bold('MCP Tool')}: {self.formatter.format_code_inline(block.name)}"
        else:
            # System tools - specific handling
            tool_emoji_map = {
                "Task": "🤖",
                "Bash": "💻",
                "Glob": "🔍",
                "Grep": "🔎",
                "LS": "📂",
                "Read": "📖",
                "Edit": "✏️",
                "MultiEdit": "📝",
                "Write": "📄",
                "NotebookRead": "📓",
                "NotebookEdit": "📓",
                "WebFetch": "🌐",
                "WebSearch": "🔍",
                "TodoWrite": "✅",
                "ExitPlanMode": "🚪",
            }
            emoji = tool_emoji_map.get(block.name, "🔧")
            tool_info = f"{emoji} {self.formatter.format_bold('Tool')}: {self.formatter.format_code_inline(block.name)}"

        # Add specific input info based on tool type
        input_info = []

        # File operations
        if "file_path" in block.input and block.input["file_path"]:
            relative_path = self._get_relative_path(block.input["file_path"])
            input_info.append(self.formatter.format_file_path(relative_path))

        # Path operations (for LS, Glob, etc.)
        if "path" in block.input and block.input["path"]:
            relative_path = self._get_relative_path(block.input["path"])
            input_info.append(self.formatter.format_file_path(relative_path, emoji="📂"))

        # Command operations
        if "command" in block.input and block.input["command"]:
            cmd = block.input["command"]
            input_info.append(self.formatter.format_command(cmd))

        # Description (for Bash tool)
        if "description" in block.input and block.input["description"]:
            desc = block.input["description"]
            input_info.append(f"📝 Description: {self.formatter.format_code_inline(desc)}")

        # Pattern/Query operations
        if "pattern" in block.input and block.input["pattern"]:
            input_info.append(f"🔍 Pattern: {self.formatter.format_code_inline(block.input['pattern'])}")

        if "query" in block.input and block.input["query"]:
            query_str = str(block.input["query"])
            truncated_query = self.formatter.truncate_text(query_str, 50)
            input_info.append(f"🔍 Query: {self.formatter.format_code_inline(truncated_query)}")

        # WebFetch specific parameters
        if "url" in block.input and block.input["url"]:
            url_str = str(block.input["url"])
            input_info.append(f"🌐 URL: {self.formatter.format_code_inline(url_str)}")

        if "prompt" in block.input and block.input["prompt"]:
            prompt_str = str(block.input["prompt"])
            truncated_prompt = self.formatter.truncate_text(prompt_str, 100)
            escaped_prompt = self.formatter.escape_special_chars(truncated_prompt)
            input_info.append(f"📝 Prompt: {escaped_prompt}")

        # Edit/MultiEdit specific parameters
        if "old_string" in block.input and block.input["old_string"]:
            old_str = str(block.input["old_string"])
            truncated_old = self.formatter.truncate_text(old_str, 50)
            input_info.append(f"🔍 Old: {self.formatter.format_code_inline(truncated_old)}")

        if "new_string" in block.input and block.input["new_string"]:
            new_str = str(block.input["new_string"])
            truncated_new = self.formatter.truncate_text(new_str, 50)
            input_info.append(f"✏️ New: {self.formatter.format_code_inline(truncated_new)}")

        # MultiEdit edits array
        if "edits" in block.input and block.input["edits"]:
            edits_count = len(block.input["edits"])
            input_info.append(f"📝 Edits: {edits_count} changes")

        # Other tool-specific parameters
        if "limit" in block.input and block.input["limit"]:
            input_info.append(f"🔢 Limit: {block.input['limit']}")

        if "offset" in block.input and block.input["offset"]:
            input_info.append(f"📍 Offset: {block.input['offset']}")

        # Task tool parameters
        if "subagent_type" in block.input and block.input["subagent_type"]:
            agent_type = str(block.input["subagent_type"])
            input_info.append(f"🤖 Agent: {self.formatter.format_code_inline(agent_type)}")

        if "plan" in block.input and block.input["plan"]:
            plan_str = str(block.input["plan"])
            truncated_plan = self.formatter.truncate_text(plan_str, 100)
            escaped_plan = self.formatter.escape_special_chars(truncated_plan)
            input_info.append(f"📋 Plan: {escaped_plan}")

        # NotebookEdit parameters
        if "cell_id" in block.input and block.input["cell_id"]:
            cell_id = str(block.input["cell_id"])
            input_info.append(f"📊 Cell ID: {self.formatter.format_code_inline(cell_id)}")

        if "cell_type" in block.input and block.input["cell_type"]:
            cell_type = str(block.input["cell_type"])
            input_info.append(f"📝 Cell Type: {self.formatter.format_code_inline(cell_type)}")

        # WebSearch parameters
        if "allowed_domains" in block.input and block.input["allowed_domains"]:
            domains_count = len(block.input["allowed_domains"])
            input_info.append(f"✅ Allowed domains: {domains_count}")

        if "blocked_domains" in block.input and block.input["blocked_domains"]:
            domains_count = len(block.input["blocked_domains"])
            input_info.append(f"🚫 Blocked domains: {domains_count}")

        # Grep parameters
        if "glob" in block.input and block.input["glob"]:
            glob_pattern = str(block.input["glob"])
            input_info.append(f"🎯 Glob: {self.formatter.format_code_inline(glob_pattern)}")

        if "type" in block.input and block.input["type"]:
            type_str = str(block.input["type"])
            input_info.append(f"📄 Type: {self.formatter.format_code_inline(type_str)}")

        if "output_mode" in block.input and block.input["output_mode"]:
            mode = str(block.input["output_mode"])
            input_info.append(f"📊 Output mode: {self.formatter.format_code_inline(mode)}")

        if input_info:
            tool_info += "\n" + "\n".join(input_info)

        # Handle content specifically based on tool type
        # Tools that already show all their parameters don't need JSON
        show_json = True
        no_json_tools = [
            "Bash",
            "Read",
            "Write",
            "Edit",
            "MultiEdit",
            "LS",
            "Glob",
            "Grep",
            "WebFetch",
            "WebSearch",
        ]

        if block.name in no_json_tools:
            show_json = False

        if block.name == "TodoWrite":
            # TodoWrite has complex todos array - show as markdown list
            if "todos" in block.input and block.input["todos"]:
                todos = block.input["todos"]
                todos_count = len(todos)
                tool_info += f"\n📋 {todos_count} todo items:"

                for todo in todos:  # Show all todos, don't limit to 5
                    status = todo.get("status", "pending")
                    status_emoji = {
                        "pending": "⏳",
                        "in_progress": "🔄",
                        "completed": "✅",
                    }.get(status, "⏳")
                    priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                        todo.get("priority", "medium"), "🟡"
                    )
                    content = todo.get("content", "No content")[
                        :50
                    ]  # Truncate long content
                    if len(todo.get("content", "")) > 50:
                        content += "..."

                    # Add strikethrough for completed items
                    if status == "completed":
                        # Use formatter's strikethrough method
                        formatted_content = self.formatter.format_strikethrough(content)
                        tool_info += (
                            f"\n• {status_emoji} {priority_emoji} {formatted_content}"
                        )
                    else:
                        escaped_content = self.formatter.escape_special_chars(content)
                        tool_info += (
                            f"\n• {status_emoji} {priority_emoji} {escaped_content}"
                        )
        elif (
            "content" in block.input
            and block.input["content"]
            and block.name in ["Write", "Edit", "MultiEdit"]
        ):
            # Show content in code block for file write operations
            content = str(block.input["content"])
            if len(content) > 300:
                content = content[:300] + "..."
            tool_info += f"\n{self.formatter.format_code_block(content)}"
        elif show_json and block.input and len(str(block.input)) < 200:
            # Show short input as JSON for tools that need it
            import json

            try:
                input_json = json.dumps(block.input, indent=2, ensure_ascii=False)
                tool_info += f"\n{self.formatter.format_code_block(input_json, 'json')}"
            except:
                # Fallback for non-serializable input
                tool_info += f"\n{self.formatter.format_code_block(str(block.input))}"

        return tool_info

    def _format_tool_result_block(self, block: ToolResultBlock) -> str:
        """Format ToolResultBlock"""
        if block.is_error:
            emoji = "❌"
            status = "Error"
        else:
            emoji = "✅"
            status = "Success"

        # Get tool use ID (shortened)
        tool_id = (
            block.tool_use_id[:8] + "..."
            if len(block.tool_use_id) > 8
            else block.tool_use_id
        )
        result_info = f"{emoji} {self.formatter.format_bold('Tool Result')}"

        # Format content in code block
        if block.content:
            content = str(block.content)
            if len(content) > 500:
                # Truncate very long content
                content = content[:500] + "..."
            result_info += f"\n{self.formatter.format_code_block(content)}"

        return result_info

    def _format_system_message(self, message: SystemMessage) -> str:
        """Format SystemMessage"""
        cwd = message.data.get("cwd", "Unknown")
        subtype = message.subtype
        
        header = self.formatter.format_section_header(f"System {subtype}", "🔧")
        cwd_line = self.formatter.format_file_path(cwd, emoji="📁").replace("File:", "Working directory:")
        ready_line = f"✨ {self.formatter.escape_special_chars('Ready to work!')}"
        
        return f"{header}\n{cwd_line}\n{ready_line}"

    def _format_assistant_message(self, message: AssistantMessage) -> str:
        """Format AssistantMessage"""
        header = self.formatter.format_section_header("Assistant", "🤖")
        formatted_parts = [header]
        content_parts = self._process_content_blocks(message.content)
        formatted_parts.extend(content_parts)
        return "\n\n".join(formatted_parts)

    def _format_user_message(self, message: UserMessage) -> str:
        """Format UserMessage"""
        header = self.formatter.format_section_header("Response", "👤")
        formatted_parts = [header]
        content_parts = self._process_content_blocks(message.content)
        formatted_parts.extend(content_parts)
        return "\n\n".join(formatted_parts)

    def _format_result_message(self, message: ResultMessage) -> str:
        """Format ResultMessage"""
        # Use total duration (duration_ms includes API time)
        total_seconds = message.duration_ms / 1000
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)

        if minutes > 0:
            duration_str = f"{minutes}m {seconds}s"
        else:
            duration_str = f"{seconds}s"

        # Format result header
        header = self.formatter.format_section_header(f"Result ({message.subtype})", "📊")
        duration_line = self.formatter.format_key_value("⏱️ Duration", duration_str)
        
        result_text = f"{header}\n{duration_line}\n"

        if message.result:
            result_text += f"\n{message.result}\n"

        return result_text

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
                # Format message according to type

                print(message)
                print()

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
