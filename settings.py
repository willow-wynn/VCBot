"""Centralized configuration management using Pydantic."""

import os
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
try:
    from pydantic_settings import BaseSettings
except ImportError:
    # Fallback for older pydantic versions
    from pydantic import BaseSettings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get the base directory of the project
BASE_DIR = Path(__file__).parent


class KnowledgeFiles(BaseModel):
    """Configuration for knowledge file paths."""
    rules: Path
    constitution: Path
    server_information: Path
    house_rules: Path
    senate_rules: Path

    @field_validator('*', mode='before')
    def resolve_path(cls, v):
        """Convert string paths to Path objects and resolve them."""
        if isinstance(v, str):
            path = Path(v)
            if not path.is_absolute():
                path = BASE_DIR / path
            return path
        return v


class BillDirectories(BaseModel):
    """Configuration for bill storage directories."""
    bills: Path
    billpdfs: Path

    @field_validator('*', mode='before')
    def resolve_path(cls, v):
        """Convert string paths to Path objects and resolve them."""
        if isinstance(v, str):
            path = Path(v)
            if not path.is_absolute():
                path = BASE_DIR / path
            return path
        return v


class DiscordChannels(BaseModel):
    """Discord channel IDs configuration."""
    records_channel: int = Field(description="Channel for bill records")
    news_channel: int = Field(description="Channel for news updates")
    sign_channel: int = Field(description="Channel for bill signing")
    clerk_channel: int = Field(description="Channel for clerk operations")
    main_chat: int = Field(default=654467992272371712, description="Main chat channel")
    bot_helper_channel: int = Field(default=1327483297202176080, description="Bot helper channel")
    
    # Additional hardcoded channel IDs found in the code
    clerk_announce_channel: int = Field(default=1037456401708105780, description="Clerk announcement channel")


class RolePermissions(BaseModel):
    """Role permission configuration."""
    house_committee_roles: List[str] = Field(default_factory=lambda: [
        "House Ethics and Oversight Committee",
        "House Rules Committee",
        "House Judiciary Committee",
        "House Education and Youth Welfare Committee",
        "House General Legislation Committee"
    ])
    
    senate_committee_roles: List[str] = Field(default_factory=lambda: [
        "Senate General Welfare Committee",
        "Senate Judiciary Committee",
        "Senate Relations Committee"
    ])
    
    cabinet_roles: List[str] = Field(default_factory=lambda: [
        "Attorney General", "Cabinet Member", "US Attorney", "Sub-Cabinet",
        "UN Ambassador", "IPTO Sec. Gen.", "White House Staff",
        "Chief of Staff", "Deputy Chief of Staff", "National Security Council"
    ])
    
    allowed_roles_for_roles: Dict[str, List[str]] = Field(default_factory=dict)
    
    def __init__(self, **data):
        super().__init__(**data)
        # Build the allowed_roles_for_roles mapping
        self.allowed_roles_for_roles = {
            "Speaker of the House": [
                "House Presiding Officer", "House Clerk", "Speaker Pro Tempore",
                "House Majority Leader", "House Minority Leader", "House Hearing Attendee",
                *self.house_committee_roles
            ],
            "President": self.cabinet_roles,
            "Attorney General": ["US Attorney"],
            "Senate President Pro Tempore": [
                *self.senate_committee_roles, "Senate Secretary",
                "Senate Presiding Officer", "Senate Hearing Attendee"
            ],
            "Vice President": [
                *self.senate_committee_roles, "Senate Secretary",
                "Senate Presiding Officer", "Senate Hearing Attendee",
                "Senate Minority Leader"  # Fixed duplicate
            ],
            "Speaker Pro Tempore": [
                *self.house_committee_roles, "House Presiding Officer", "House Hearing Attendee"
            ],
            "House Majority Leader": self.house_committee_roles,
            "House Minority Leader": self.house_committee_roles,
            "Committee Chair": ["House Hearing Attendee", "Senate Hearing Attendee"],
            "Committee Ranking Member": ["House Hearing Attendee", "Senate Hearing Attendee"]
        }


class FileStorage(BaseModel):
    """File storage configuration."""
    bill_ref_file: Path
    news_file: Path
    queries_file: Path
    model_path: Path
    vector_pkl: Path

    @field_validator('*', mode='before')
    def resolve_path(cls, v):
        """Convert string paths to Path objects and resolve them."""
        if isinstance(v, str):
            path = Path(v)
            if not path.is_absolute():
                path = BASE_DIR / path
            return path
        return v


class Settings(BaseSettings):
    """Main settings class that combines all configuration."""
    
    # Discord configuration
    bot_id: int = Field(..., env="BOT_ID")
    discord_token: str = Field(..., env="DISCORD_TOKEN")
    gemini_api_key: str = Field(..., env="GEMINI_API_KEY")
    guild_id: Optional[int] = Field(None, env="GUILD")
    
    # Channel configuration
    channels: DiscordChannels
    
    # File paths configuration
    knowledge_files: KnowledgeFiles
    bill_directories: BillDirectories
    file_storage: FileStorage
    
    # Role permissions
    role_permissions: RolePermissions = Field(default_factory=RolePermissions)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"  # Allow extra fields during initialization
    
    def __init__(self, **values):
        # Initialize channels from environment variables
        channels = DiscordChannels(
            records_channel=int(os.getenv("RECORDS_CHANNEL", "0")),
            news_channel=int(os.getenv("NEWS_CHANNEL", "0")),
            sign_channel=int(os.getenv("SIGN_CHANNEL", "0")),
            clerk_channel=int(os.getenv("CLERK_CHANNEL", "0"))
        )
        
        # Initialize knowledge files with resolved paths
        knowledge_files = KnowledgeFiles(
            rules="Knowledge/rules.txt",
            constitution="Knowledge/constitution.txt",
            server_information="Knowledge/rules.txt",  # Note: duplicate of rules
            house_rules="Knowledge/houserules.txt",
            senate_rules="Knowledge/senaterules.txt"
        )
        
        # Initialize bill directories
        bill_directories = BillDirectories(
            bills="every-vc-bill/txts",
            billpdfs="every-vc-bill/pdfs"
        )
        
        # Initialize file storage
        file_storage = FileStorage(
            bill_ref_file=os.getenv("BILL_REF_FILE", "bill_refs.json"),
            news_file=os.getenv("NEWS_FILE", "news.txt"),
            queries_file=os.getenv("QUERIES_FILE", "queries.csv"),
            model_path="final_model",
            vector_pkl="vectors.pkl"
        )
        
        # Ensure environment variables are loaded for core settings
        if "bot_id" not in values and os.getenv("BOT_ID"):
            values["bot_id"] = int(os.getenv("BOT_ID"))
        if "discord_token" not in values and os.getenv("DISCORD_TOKEN"):
            values["discord_token"] = os.getenv("DISCORD_TOKEN")
        if "gemini_api_key" not in values and os.getenv("GEMINI_API_KEY"):
            values["gemini_api_key"] = os.getenv("GEMINI_API_KEY")
        if "guild_id" not in values and os.getenv("GUILD"):
            values["guild_id"] = int(os.getenv("GUILD"))
        
        values.update({
            "channels": channels,
            "knowledge_files": knowledge_files,
            "bill_directories": bill_directories,
            "file_storage": file_storage
        })
        
        super().__init__(**values)
    
    @property
    def knowledge_files_dict(self) -> Dict[str, str]:
        """Get knowledge files as a dictionary with string paths for backward compatibility."""
        return {
            "rules": str(self.knowledge_files.rules),
            "constitution": str(self.knowledge_files.constitution),
            "server_information": str(self.knowledge_files.server_information),
            "house_rules": str(self.knowledge_files.house_rules),
            "senate_rules": str(self.knowledge_files.senate_rules)
        }
    
    @property
    def bill_directories_dict(self) -> Dict[str, str]:
        """Get bill directories as a dictionary with string paths for backward compatibility."""
        return {
            "bills": str(self.bill_directories.bills),
            "billpdfs": str(self.bill_directories.billpdfs)
        }


# Create a singleton instance
settings = Settings()

# Backward compatibility exports
KNOWLEDGE_FILES = settings.knowledge_files_dict
BILL_DIRECTORIES = settings.bill_directories_dict
MODEL_PATH = str(settings.file_storage.model_path)
VECTOR_PKL = str(settings.file_storage.vector_pkl)
ALLOWED_ROLES_FOR_ROLES = settings.role_permissions.allowed_roles_for_roles