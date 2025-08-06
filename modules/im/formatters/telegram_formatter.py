from .base_formatter import BaseMarkdownFormatter


class TelegramFormatter(BaseMarkdownFormatter):
    """Telegram formatter that outputs standard markdown
    
    This formatter outputs clean markdown that will be converted to HTML
    before sending to Telegram, avoiding MarkdownV2 escaping issues entirely.
    """
    
    # Tool output emoji prefixes that indicate pre-formatted content
    TOOL_EMOJI_PREFIXES = ("🔧", "💻", "🔍", "📖", "✏️", "📝", "📄", "📓", "🌐", "✅", "❌", "🤖", "📂", "🔎", "🚪")
    
    # ============================================================================
    # Core abstract method implementations - Standard Markdown
    # ============================================================================
    
    def format_bold(self, text: str) -> str:
        """Format bold text in standard markdown"""
        return f"**{text}**"
    
    def format_italic(self, text: str) -> str:
        """Format italic text in standard markdown"""
        return f"*{text}*"
    
    def format_strikethrough(self, text: str) -> str:
        """Format strikethrough text in standard markdown"""
        return f"~~{text}~~"
    
    def format_link(self, text: str, url: str) -> str:
        """Format hyperlink in standard markdown"""
        return f"[{text}]({url})"
    
    def escape_special_chars(self, text: str) -> str:
        """No escaping needed for HTML conversion - return text as-is"""
        return text
    
    # ============================================================================
    # Override message formatting methods to handle Claude content appropriately
    # ============================================================================
    
    def format_assistant_message(self, content_parts: list[str]) -> str:
        """Format assistant message with clean markdown"""
        header = self.format_section_header("Assistant", "🤖")
        
        # For HTML conversion, we don't need to escape tool output differently
        # Just join all parts cleanly
        parts = [header] + content_parts
        return "\n\n".join(parts)
    
    def _is_tool_output(self, text: str) -> bool:
        """Check if text is already formatted tool output"""
        return text.startswith(self.TOOL_EMOJI_PREFIXES)