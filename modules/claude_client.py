import logging
from typing import Callable
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
from telegram.helpers import escape_markdown
from config import ClaudeConfig


logger = logging.getLogger(__name__)


class ClaudeClient:
    def __init__(self, config: ClaudeConfig):
        self.config = config
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
                return escape_markdown(
                    f"🤔 Unknown message type: {type(message)}", version=2
                )
        except Exception as e:
            logger.error(f"Error formatting message: {e}")
            return escape_markdown(f"❌ Error formatting message: {str(e)}", version=2)

    def _process_content_blocks(self, content_blocks) -> list:
        """Process content blocks (TextBlock, ToolUseBlock) and return formatted parts"""
        formatted_parts = []

        for block in content_blocks:
            if isinstance(block, TextBlock):
                # Escape text content for MarkdownV2
                escaped_text = escape_markdown(block.text, version=2)
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
        escaped_name = escape_markdown(block.name, version=2)

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
            tool_info = f"{emoji} *MCP Tool*: `{escaped_name}`"
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
            tool_info = f"{emoji} *Tool*: `{escaped_name}`"

        # Add specific input info based on tool type
        input_info = []

        # File operations
        if "file_path" in block.input and block.input["file_path"]:
            relative_path = self._get_relative_path(block.input["file_path"])
            escaped_path = escape_markdown(relative_path, version=2)
            input_info.append(f"📁 File: `{escaped_path}`")

        # Path operations (for LS, Glob, etc.)
        if "path" in block.input and block.input["path"]:
            relative_path = self._get_relative_path(block.input["path"])
            escaped_path = escape_markdown(relative_path, version=2)
            input_info.append(f"📂 Path: `{escaped_path}`")

        # Command operations
        if "command" in block.input and block.input["command"]:
            cmd = block.input["command"]
            # For multi-line commands, use code block
            if "\n" in cmd or len(cmd) > 80:
                input_info.append(f"💻 Command:\n```bash\n{cmd}\n```")
            else:
                escaped_cmd = escape_markdown(cmd, version=2)
                input_info.append(f"💻 Command: `{escaped_cmd}`")

        # Description (for Bash tool)
        if "description" in block.input and block.input["description"]:
            desc = block.input["description"]
            input_info.append(f"📝 Description: `{escape_markdown(desc, version=2)}`")

        # Pattern/Query operations
        if "pattern" in block.input and block.input["pattern"]:
            escaped_pattern = escape_markdown(block.input["pattern"], version=2)
            input_info.append(f"🔍 Pattern: `{escaped_pattern}`")

        if "query" in block.input and block.input["query"]:
            query_str = str(block.input["query"])
            if len(query_str) > 50:
                escaped_query = escape_markdown(query_str[:50], version=2) + "\\.\\.\\."
            else:
                escaped_query = escape_markdown(query_str, version=2)
            input_info.append(f"🔍 Query: `{escaped_query}`")

        # WebFetch specific parameters
        if "url" in block.input and block.input["url"]:
            url_str = str(block.input["url"])
            escaped_url = escape_markdown(url_str, version=2)
            input_info.append(f"🌐 URL: `{escaped_url}`")

        if "prompt" in block.input and block.input["prompt"]:
            prompt_str = str(block.input["prompt"])
            if len(prompt_str) > 100:
                escaped_prompt = (
                    escape_markdown(prompt_str[:100], version=2) + "\\.\\.\\."
                )
            else:
                escaped_prompt = escape_markdown(prompt_str, version=2)
            input_info.append(f"📝 Prompt: {escaped_prompt}")

        # Edit/MultiEdit specific parameters
        if "old_string" in block.input and block.input["old_string"]:
            old_str = str(block.input["old_string"])
            if len(old_str) > 50:
                escaped_old = escape_markdown(old_str[:50], version=2) + "\\.\\.\\."
            else:
                escaped_old = escape_markdown(old_str, version=2)
            input_info.append(f"🔍 Old: `{escaped_old}`")

        if "new_string" in block.input and block.input["new_string"]:
            new_str = str(block.input["new_string"])
            if len(new_str) > 50:
                escaped_new = escape_markdown(new_str[:50], version=2) + "\\.\\.\\."
            else:
                escaped_new = escape_markdown(new_str, version=2)
            input_info.append(f"✏️ New: `{escaped_new}`")

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
            escaped_agent = escape_markdown(
                str(block.input["subagent_type"]), version=2
            )
            input_info.append(f"🤖 Agent: `{escaped_agent}`")

        if "plan" in block.input and block.input["plan"]:
            plan_str = str(block.input["plan"])
            if len(plan_str) > 100:
                escaped_plan = escape_markdown(plan_str[:100], version=2) + "\\.\\.\\."
            else:
                escaped_plan = escape_markdown(plan_str, version=2)
            input_info.append(f"📋 Plan: {escaped_plan}")

        # NotebookEdit parameters
        if "cell_id" in block.input and block.input["cell_id"]:
            escaped_cell_id = escape_markdown(str(block.input["cell_id"]), version=2)
            input_info.append(f"📊 Cell ID: `{escaped_cell_id}`")

        if "cell_type" in block.input and block.input["cell_type"]:
            escaped_cell_type = escape_markdown(
                str(block.input["cell_type"]), version=2
            )
            input_info.append(f"📝 Cell Type: `{escaped_cell_type}`")

        # WebSearch parameters
        if "allowed_domains" in block.input and block.input["allowed_domains"]:
            domains_count = len(block.input["allowed_domains"])
            input_info.append(f"✅ Allowed domains: {domains_count}")

        if "blocked_domains" in block.input and block.input["blocked_domains"]:
            domains_count = len(block.input["blocked_domains"])
            input_info.append(f"🚫 Blocked domains: {domains_count}")

        # Grep parameters
        if "glob" in block.input and block.input["glob"]:
            escaped_glob = escape_markdown(str(block.input["glob"]), version=2)
            input_info.append(f"🎯 Glob: `{escaped_glob}`")

        if "type" in block.input and block.input["type"]:
            escaped_type = escape_markdown(str(block.input["type"]), version=2)
            input_info.append(f"📄 Type: `{escaped_type}`")

        if "output_mode" in block.input and block.input["output_mode"]:
            escaped_mode = escape_markdown(str(block.input["output_mode"]), version=2)
            input_info.append(f"📊 Output mode: `{escaped_mode}`")

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

                    # Add strikethrough for completed items using MarkdownV2 format
                    if status == "completed":
                        # Use MarkdownV2 strikethrough format: ~text~
                        escaped_content = f"~{escape_markdown(content, version=2)}~"
                        tool_info += (
                            f"\n• {status_emoji} {priority_emoji} {escaped_content}"
                        )
                    else:
                        escaped_content = escape_markdown(content, version=2)
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
            tool_info += f"\n```\n{content}\n```"
        elif show_json and block.input and len(str(block.input)) < 200:
            # Show short input as JSON for tools that need it
            import json

            try:
                input_json = json.dumps(block.input, indent=2, ensure_ascii=False)
                tool_info += f"\n```json\n{input_json}\n```"
            except:
                # Fallback for non-serializable input
                tool_info += f"\n```\n{str(block.input)}\n```"

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
        escaped_tool_id = escape_markdown(tool_id, version=2)

        result_info = f"{emoji} *Tool Result*"

        # Format content in code block
        if block.content:
            content = str(block.content)
            if len(content) > 500:
                # Truncate very long content
                content = content[:500] + "..."
            result_info += f"\n```\n{content}\n```"

        return result_info

    def _format_system_message(self, message: SystemMessage) -> str:
        """Format SystemMessage"""
        cwd = message.data.get("cwd", "Unknown")
        escaped_cwd = escape_markdown(cwd, version=2)
        escaped_subtype = escape_markdown(message.subtype, version=2)
        return f"🔧 *System {escaped_subtype}*\n📁 Working directory: `{escaped_cwd}`\n✨ Ready to work\\!"

    def _format_assistant_message(self, message: AssistantMessage) -> str:
        """Format AssistantMessage"""
        formatted_parts = ["🤖 *Assistant*"]
        content_parts = self._process_content_blocks(message.content)
        formatted_parts.extend(content_parts)
        return "\n\n".join(formatted_parts)

    def _format_user_message(self, message: UserMessage) -> str:
        """Format UserMessage"""
        formatted_parts = ["👤 *Response*"]
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

        # Don't escape for Result messages - they will be handled by smart formatting
        result_text = f"📊 **Result ({message.subtype})**\n"
        result_text += f"⏱️ Duration: {duration_str}\n"

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
