"""Base repository interface."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List, Dict, Any
from pathlib import Path

T = TypeVar('T')


class Repository(ABC, Generic[T]):
    """Abstract base class for repositories."""
    
    @abstractmethod
    async def save(self, entity: T) -> None:
        """Save an entity."""
        pass
    
    @abstractmethod
    async def find_by_id(self, entity_id: str) -> Optional[T]:
        """Find an entity by its ID."""
        pass
    
    @abstractmethod
    async def find_all(self) -> List[T]:
        """Find all entities."""
        pass
    
    @abstractmethod
    async def delete(self, entity_id: str) -> bool:
        """Delete an entity by its ID. Returns True if deleted."""
        pass
    
    @abstractmethod
    async def exists(self, entity_id: str) -> bool:
        """Check if an entity exists."""
        pass


class FileBasedRepository(Repository[T], ABC):
    """Base class for file-based repositories."""
    
    def __init__(self, base_path: Path):
        """Initialize with base path for storage."""
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_file_path(self, entity_id: str) -> Path:
        """Get the file path for an entity."""
        return self.base_path / f"{entity_id}.json"
    
    async def exists(self, entity_id: str) -> bool:
        """Check if an entity exists."""
        return self._get_file_path(entity_id).exists()


class InMemoryRepository(Repository[T]):
    """In-memory repository for testing."""
    
    def __init__(self):
        self._storage: Dict[str, T] = {}
    
    async def save(self, entity: T) -> None:
        """Save an entity."""
        entity_id = self._get_id(entity)
        self._storage[entity_id] = entity
    
    async def find_by_id(self, entity_id: str) -> Optional[T]:
        """Find an entity by its ID."""
        return self._storage.get(entity_id)
    
    async def find_all(self) -> List[T]:
        """Find all entities."""
        return list(self._storage.values())
    
    async def delete(self, entity_id: str) -> bool:
        """Delete an entity by its ID."""
        if entity_id in self._storage:
            del self._storage[entity_id]
            return True
        return False
    
    async def exists(self, entity_id: str) -> bool:
        """Check if an entity exists."""
        return entity_id in self._storage
    
    def _get_id(self, entity: T) -> str:
        """Extract ID from entity. Override in subclasses."""
        raise NotImplementedError("Subclass must implement _get_id")