from telegram.helpers import escape_markdown
from .base_formatter import BaseMarkdownFormatter


class TelegramFormatter(BaseMarkdownFormatter):
    """Telegram MarkdownV2 formatter
    
    Telegram uses MarkdownV2 which requires extensive escaping of special characters.
    Reference: https://core.telegram.org/bots/api#markdownv2-style
    """
    
    def format_bold(self, text: str) -> str:
        """Format bold text using double asterisks"""
        # In MarkdownV2, text inside bold still needs escaping
        escaped_text = self.escape_special_chars(text)
        return f"*{escaped_text}*"
    
    def format_italic(self, text: str) -> str:
        """Format italic text using underscores"""
        # In MarkdownV2, text inside italic still needs escaping
        escaped_text = self.escape_special_chars(text)
        return f"_{escaped_text}_"
    
    def format_strikethrough(self, text: str) -> str:
        """Format strikethrough text using tildes"""
        # In MarkdownV2, text inside strikethrough still needs escaping
        escaped_text = self.escape_special_chars(text)
        return f"~{escaped_text}~"
    
    def format_link(self, text: str, url: str) -> str:
        """Format hyperlink in Telegram style"""
        escaped_text = self.escape_special_chars(text)
        # URL should not be escaped in links
        return f"[{escaped_text}]({url})"
    
    def escape_special_chars(self, text: str) -> str:
        """Escape Telegram MarkdownV2 special characters
        
        Telegram MarkdownV2 requires escaping these characters:
        '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!'
        """
        # Use Telegram's built-in escape function
        return escape_markdown(text, version=2)
    
    def format_code_inline(self, text: str) -> str:
        """Format inline code - override to handle escaping properly"""
        # Code content should not be escaped inside backticks
        return f"`{text}`"
    
    def format_code_block(self, code: str, language: str = "") -> str:
        """Format code block - override to handle escaping properly"""
        # Code content should not be escaped inside code blocks
        return f"```{language}\n{code}\n```"
    
    # Override some convenience methods to handle Telegram-specific formatting
    def format_tool_name(self, tool_name: str, emoji: str = "🔧") -> str:
        """Format tool name with emoji and styling"""
        # Don't escape tool_name here as format_code_inline handles it
        return f"{emoji} {self.format_bold('Tool')}: {self.format_code_inline(tool_name)}"
    
    def format_file_path(self, path: str, emoji: str = "📁") -> str:
        """Format file path with emoji"""
        # Don't escape path here as format_code_inline handles it
        return f"{emoji} File: {self.format_code_inline(path)}"
    
    def format_command(self, command: str) -> str:
        """Format shell command"""
        # For multi-line or long commands, use code block
        if "\n" in command or len(command) > 80:
            return f"💻 Command:\n{self.format_code_block(command, 'bash')}"
        else:
            # Don't escape command here as format_code_inline handles it
            return f"💻 Command: {self.format_code_inline(command)}"
    
    def format_section_header(self, title: str, emoji: str = "") -> str:
        """Format section header - Telegram specific"""
        if emoji:
            return f"{emoji} {self.format_bold(title)}"
        return self.format_bold(title)
    
    def format_definition_item(self, label: str, description: str) -> str:
        """Format a definition item with proper escaping for MarkdownV2
        
        The dash separator needs to be escaped in Telegram MarkdownV2
        """
        bold_label = self.format_bold(label)
        escaped_separator = " \\- "  # Escape the dash for MarkdownV2
        escaped_description = self.escape_special_chars(description)
        return f"• {bold_label}{escaped_separator}{escaped_description}"
    
    def format_key_value(self, key: str, value: str, inline: bool = True) -> str:
        """Format key-value pair"""
        # Key is bolded and escaped properly
        bold_key = self.format_bold(key)
        escaped_value = self.escape_special_chars(value)
        
        if inline:
            return f"{bold_key}: {escaped_value}"
        else:
            return f"{bold_key}:\n{escaped_value}"