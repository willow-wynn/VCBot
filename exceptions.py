"""Custom exceptions for VCBot"""

from typing import Optional, Any, Dict


class VCBotError(Exception):
    """Base exception for all bot errors"""
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.context = context or {}


class ConfigurationError(VCBotError):
    """Configuration-related errors"""
    pass


class BillProcessingError(VCBotError):
    """Errors during bill processing"""
    pass


class AIServiceError(VCBotError):
    """AI service errors"""
    pass


class PermissionError(VCBotError):
    """Permission-related errors"""
    pass


class ToolExecutionError(VCBotError):
    """Errors during tool execution"""
    pass


class DiscordAPIError(VCBotError):
    """Discord API related errors"""
    pass


class RateLimitError(VCBotError):
    """Rate limiting errors"""
    pass


class ParseError(VCBotError):
    """Errors during parsing responses"""
    pass


class NetworkError(VCBotError):
    """Network-related errors (transient)"""
    pass


class TimeoutError(VCBotError):
    """Operation timeout errors"""
    pass