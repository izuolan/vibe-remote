from abc import ABC, abstractmethod
from typing import Optional, List, Tuple


class BaseMarkdownFormatter(ABC):
    """Abstract base class for platform-specific markdown formatters"""
    
    # Common formatting methods that work across platforms
    def format_code_inline(self, text: str) -> str:
        """Format inline code - same for most platforms"""
        return f"`{text}`"
    
    def format_code_block(self, code: str, language: str = "") -> str:
        """Format code block - same for most platforms"""
        return f"```{language}\n{code}\n```"
    
    def format_emoji(self, emoji: str) -> str:
        """Format emoji - same for all platforms"""
        return emoji
    
    def format_quote(self, text: str) -> str:
        """Format quoted text - commonly using >"""
        lines = text.split('\n')
        return '\n'.join(f"> {line}" for line in lines)
    
    def format_list_item(self, text: str, level: int = 0) -> str:
        """Format list item with indentation"""
        indent = "  " * level
        return f"{indent}• {text}"
    
    def format_numbered_list_item(self, text: str, number: int, level: int = 0) -> str:
        """Format numbered list item"""
        indent = "  " * level
        return f"{indent}{number}. {text}"
    
    def format_horizontal_rule(self) -> str:
        """Format horizontal rule"""
        return "---"
    
    # Platform-specific abstract methods
    @abstractmethod
    def format_bold(self, text: str) -> str:
        """Format bold text - platform specific"""
        pass
    
    @abstractmethod
    def format_italic(self, text: str) -> str:
        """Format italic text - platform specific"""
        pass
    
    @abstractmethod
    def format_strikethrough(self, text: str) -> str:
        """Format strikethrough text - platform specific"""
        pass
    
    @abstractmethod
    def format_link(self, text: str, url: str) -> str:
        """Format hyperlink - platform specific"""
        pass
    
    @abstractmethod
    def escape_special_chars(self, text: str) -> str:
        """Escape platform-specific special characters"""
        pass
    
    # Convenience methods that combine formatting
    def format_tool_name(self, tool_name: str, emoji: str = "🔧") -> str:
        """Format tool name with emoji and styling"""
        escaped_name = self.escape_special_chars(tool_name)
        return f"{emoji} {self.format_bold('Tool')}: {self.format_code_inline(escaped_name)}"
    
    def format_file_path(self, path: str, emoji: str = "📁") -> str:
        """Format file path with emoji"""
        escaped_path = self.escape_special_chars(path)
        return f"{emoji} File: {self.format_code_inline(escaped_path)}"
    
    def format_command(self, command: str) -> str:
        """Format shell command"""
        # For multi-line or long commands, use code block
        if "\n" in command or len(command) > 80:
            return f"💻 Command:\n{self.format_code_block(command, 'bash')}"
        else:
            escaped_cmd = self.escape_special_chars(command)
            return f"💻 Command: {self.format_code_inline(escaped_cmd)}"
    
    def format_error(self, error_text: str) -> str:
        """Format error message"""
        return f"❌ {self.format_bold('Error')}: {self.escape_special_chars(error_text)}"
    
    def format_success(self, message: str) -> str:
        """Format success message"""
        return f"✅ {self.escape_special_chars(message)}"
    
    def format_warning(self, warning_text: str) -> str:
        """Format warning message"""
        return f"⚠️ {self.format_bold('Warning')}: {self.escape_special_chars(warning_text)}"
    
    def format_section_header(self, title: str, emoji: str = "") -> str:
        """Format section header"""
        if emoji:
            return f"{emoji} {self.format_bold(title)}"
        return self.format_bold(title)
    
    def format_key_value(self, key: str, value: str, inline: bool = True) -> str:
        """Format key-value pair"""
        escaped_key = self.escape_special_chars(key)
        escaped_value = self.escape_special_chars(value)
        
        if inline:
            return f"{self.format_bold(escaped_key)}: {escaped_value}"
        else:
            return f"{self.format_bold(escaped_key)}:\n{escaped_value}"
    
    def truncate_text(self, text: str, max_length: int = 50, suffix: str = "...") -> str:
        """Truncate text to specified length"""
        if len(text) <= max_length:
            return text
        return text[:max_length] + suffix