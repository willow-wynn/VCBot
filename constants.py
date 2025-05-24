"""Constants and configuration values for VCBot."""

from typing import Final


class Limits:
    """Application limits and thresholds."""
    MAX_MESSAGES_HISTORY: Final[int] = 50
    MAX_RESPONSE_LENGTH: Final[int] = 30000
    GITHUB_CHECK_INTERVAL: Final[int] = 60
    MAX_TOOL_RESULTS: Final[int] = 10
    DEFAULT_CHUNK_SIZE: Final[int] = 1024
    DEFAULT_OVERLAP: Final[int] = 50
    DISCORD_MAX_MESSAGE_LENGTH: Final[int] = 2000
    DISCORD_MAX_EMBED_LENGTH: Final[int] = 4096
    MAX_QUERY_LOG_SIZE: Final[int] = 100000  # Max queries before rotation
    MAX_FILE_SIZE_MB: Final[int] = 25  # Discord file upload limit
    API_TIMEOUT_SECONDS: Final[int] = 30
    MAX_RETRIES: Final[int] = 3
    RATE_LIMIT_MESSAGES: Final[int] = 10
    RATE_LIMIT_SECONDS: Final[int] = 60


class Roles:
    """Discord role names."""
    ADMIN: Final[str] = "Admin"
    AI_ACCESS: Final[str] = "AI Access"
    REPRESENTATIVE: Final[str] = "Representative"
    SENATOR: Final[str] = "Senator"
    COMMITTEE_MEMBER: Final[str] = "Committee Member"
    WHIP: Final[str] = "Whip"
    VP: Final[str] = "VP"
    CLERK: Final[str] = "Clerk"
    HOUSE_CLERK: Final[str] = "House Clerk"
    SPEAKER: Final[str] = "Speaker"
    MEMBER_OF_CONGRESS: Final[str] = "Member of Congress"
    PROTEM: Final[str] = "ProTem"
    DRAFTSMAN: Final[str] = "Draftsman"
    MODERATOR: Final[str] = "Moderator"
    EVENTS_TEAM: Final[str] = "Events Team"


class FilePatterns:
    """File naming patterns and extensions."""
    BILL_TEXT_PATTERN: Final[str] = "{bill_type}{reference_number}.txt"
    BILL_PDF_PATTERN: Final[str] = "{bill_type}{reference_number}.pdf"
    LOG_FILE_PATTERN: Final[str] = "vcbot_{timestamp}.log"
    BACKUP_PATTERN: Final[str] = "{filename}_{timestamp}.bak"
    
    # File extensions
    TEXT_EXTENSION: Final[str] = ".txt"
    PDF_EXTENSION: Final[str] = ".pdf"
    JSON_EXTENSION: Final[str] = ".json"
    CSV_EXTENSION: Final[str] = ".csv"
    PICKLE_EXTENSION: Final[str] = ".pkl"


class Messages:
    """Standard messages and responses."""
    # Error messages
    PERMISSION_DENIED: Final[str] = "You don't have permission to use this command."
    PERMISSION_DENIED_AI_ACCESS: Final[str] = "You do not have permission to use this command. Get the AI Access role from the pins."
    CHANNEL_RESTRICTED: Final[str] = "This command can only be used in specific channels."
    COMMAND_FAILED: Final[str] = "Command failed. Please try again."
    FILE_NOT_FOUND: Final[str] = "File not found: {filename}"
    INVALID_BILL_TYPE: Final[str] = "Invalid bill type. Valid types are: hr, s, hres, sres, hjres, sjres, hconres, sconres"
    
    # Success messages
    BILL_ADDED: Final[str] = "Bill successfully added to database."
    REFERENCE_UPDATED: Final[str] = "Reference number updated successfully."
    QUERY_SAVED: Final[str] = "Query saved to log."
    
    # Info messages
    PROCESSING: Final[str] = "Processing your request..."
    LOADING: Final[str] = "Loading..."
    
    # Command descriptions
    HELPER_DESC: Final[str] = "AI assistant that can answer questions about Virtual Congress"
    ECON_IMPACT_DESC: Final[str] = "Generate economic impact report for a bill"
    REFERENCE_DESC: Final[str] = "Get current reference number for a bill type"
    ADD_BILL_DESC: Final[str] = "Add a bill to the database"


class Timeouts:
    """Timeout values in seconds."""
    DISCORD_INTERACTION: Final[int] = 3  # Discord requires response within 3 seconds
    AI_RESPONSE: Final[int] = 60  # Max time for AI to generate response
    FILE_OPERATION: Final[int] = 10  # Max time for file operations
    HTTP_REQUEST: Final[int] = 30  # Max time for HTTP requests
    DATABASE_OPERATION: Final[int] = 5  # Max time for database operations


class APIEndpoints:
    """External API endpoints."""
    GOOGLE_DOCS_BASE: Final[str] = "https://docs.google.com"
    GOOGLE_DOCS_EXPORT: Final[str] = "{doc_id}/export?format=txt"
    GITHUB_API_BASE: Final[str] = "https://api.github.com"


class Colors:
    """Discord embed colors (in decimal)."""
    SUCCESS: Final[int] = 0x00FF00  # Green
    ERROR: Final[int] = 0xFF0000  # Red
    WARNING: Final[int] = 0xFFFF00  # Yellow
    INFO: Final[int] = 0x0000FF  # Blue
    DEFAULT: Final[int] = 0x7289DA  # Discord blurple