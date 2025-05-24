"""Data models for VCBot."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List
from enum import Enum


class BillType(Enum):
    """Enumeration of bill types."""
    HR = "hr"
    S = "s"
    HRES = "hres"
    SRES = "sres"
    HJRES = "hjres"
    SJRES = "sjres"
    HCONRES = "hconres"
    SCONRES = "sconres"
    
    @classmethod
    def from_string(cls, value: str) -> 'BillType':
        """Convert string to BillType."""
        value = value.lower().strip()
        for bill_type in cls:
            if bill_type.value == value:
                return bill_type
        raise ValueError(f"Unknown bill type: {value}")


@dataclass
class BillReference:
    """Represents a bill reference number."""
    bill_type: BillType
    reference_number: int
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary for serialization."""
        return {
            "bill_type": self.bill_type.value,
            "reference_number": self.reference_number,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, any]) -> 'BillReference':
        """Create from dictionary."""
        return cls(
            bill_type=BillType.from_string(data["bill_type"]),
            reference_number=data["reference_number"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"])
        )


@dataclass
class Query:
    """Represents a user query and AI response."""
    user_id: int
    user_name: str
    query: str
    response: str
    timestamp: datetime = field(default_factory=datetime.now)
    tokens_used: Dict[str, int] = field(default_factory=dict)
    channel_id: Optional[int] = None
    tool_calls: List[str] = field(default_factory=list)
    
    def to_csv_row(self) -> str:
        """Format as CSV row for legacy compatibility."""
        # Format: timestamp, user_id, user_name, query, response
        return f"{self.timestamp},{self.user_id},{self.user_name},{self.query},{self.response}\n"
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary for serialization."""
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "query": self.query,
            "response": self.response,
            "timestamp": self.timestamp.isoformat(),
            "tokens_used": self.tokens_used,
            "channel_id": self.channel_id,
            "tool_calls": self.tool_calls
        }


@dataclass
class Bill:
    """Represents a bill with all its metadata."""
    identifier: str  # e.g., "hr-123"
    title: str
    bill_type: BillType
    reference_number: int
    text_content: str
    pdf_path: Optional[str] = None
    sponsor: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, any] = field(default_factory=dict)
    
    @property
    def filename_base(self) -> str:
        """Get base filename for this bill."""
        return f"{self.bill_type.value}{self.reference_number}"
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary for serialization."""
        return {
            "identifier": self.identifier,
            "title": self.title,
            "bill_type": self.bill_type.value,
            "reference_number": self.reference_number,
            "text_content": self.text_content,
            "pdf_path": self.pdf_path,
            "sponsor": self.sponsor,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class VectorEmbedding:
    """Represents a vector embedding for a piece of text."""
    text: str
    embedding: List[float]
    source: str  # e.g., "bill:hr-123", "knowledge:constitution"
    metadata: Dict[str, any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary for serialization."""
        return {
            "text": self.text,
            "embedding": self.embedding,
            "source": self.source,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }