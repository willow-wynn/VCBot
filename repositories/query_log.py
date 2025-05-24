"""Repository for managing query logs."""

import json
import asyncio
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from models import Query
from .base import FileBasedRepository


class QueryLogRepository(FileBasedRepository[Query]):
    """Repository for managing user query logs."""
    
    def __init__(self, csv_path: Path, json_path: Optional[Path] = None):
        """Initialize with file paths for query storage."""
        self.csv_path = Path(csv_path)
        self.json_path = Path(json_path) if json_path else self.csv_path.with_suffix('.json')
        
        # Ensure parent directories exist
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._lock = asyncio.Lock()
        
        # Initialize files if they don't exist
        if not self.csv_path.exists():
            self.csv_path.touch()
        if not self.json_path.exists():
            self._save_json_sync([])
    
    async def save(self, entity: Query) -> None:
        """Save a query to both CSV and JSON."""
        async with self._lock:
            # Append to CSV for legacy compatibility
            await self._append_csv(entity)
            
            # Save to JSON for structured access
            queries = await self._load_json()
            queries.append(entity.to_dict())
            await self._save_json(queries)
    
    async def find_by_id(self, entity_id: str) -> Optional[Query]:
        """Find a query by timestamp ID."""
        queries = await self._load_json()
        for query_dict in queries:
            if query_dict["timestamp"] == entity_id:
                return self._dict_to_query(query_dict)
        return None
    
    async def find_all(self) -> List[Query]:
        """Find all queries."""
        queries = await self._load_json()
        return [self._dict_to_query(q) for q in queries]
    
    async def find_by_user(self, user_id: int) -> List[Query]:
        """Find all queries by a specific user."""
        all_queries = await self.find_all()
        return [q for q in all_queries if q.user_id == user_id]
    
    async def find_recent(self, limit: int = 10) -> List[Query]:
        """Find the most recent queries."""
        all_queries = await self.find_all()
        # Sort by timestamp descending
        all_queries.sort(key=lambda q: q.timestamp, reverse=True)
        return all_queries[:limit]
    
    async def delete(self, entity_id: str) -> bool:
        """Delete a query by timestamp ID."""
        async with self._lock:
            queries = await self._load_json()
            original_count = len(queries)
            queries = [q for q in queries if q["timestamp"] != entity_id]
            
            if len(queries) < original_count:
                await self._save_json(queries)
                # Note: CSV is append-only, so we don't delete from it
                return True
        return False
    
    async def exists(self, entity_id: str) -> bool:
        """Check if a query exists."""
        queries = await self._load_json()
        return any(q["timestamp"] == entity_id for q in queries)
    
    async def _append_csv(self, query: Query) -> None:
        """Append query to CSV file."""
        loop = asyncio.get_event_loop()
        csv_row = query.to_csv_row()
        await loop.run_in_executor(None, self._append_csv_sync, csv_row)
    
    def _append_csv_sync(self, csv_row: str) -> None:
        """Synchronously append to CSV file."""
        with open(self.csv_path, 'a', encoding='utf-8') as f:
            f.write(csv_row)
    
    async def _load_json(self) -> List[dict]:
        """Load queries from JSON file."""
        if self.json_path.exists():
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._load_json_sync)
        return []
    
    def _load_json_sync(self) -> List[dict]:
        """Synchronously load from JSON file."""
        with open(self.json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    async def _save_json(self, queries: List[dict]) -> None:
        """Save queries to JSON file."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._save_json_sync, queries)
    
    def _save_json_sync(self, queries: List[dict]) -> None:
        """Synchronously save to JSON file."""
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(queries, f, indent=2)
    
    def _dict_to_query(self, data: dict) -> Query:
        """Convert dictionary to Query object."""
        return Query(
            user_id=data["user_id"],
            user_name=data["user_name"],
            query=data["query"],
            response=data["response"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            tokens_used=data.get("tokens_used", {}),
            channel_id=data.get("channel_id"),
            tool_calls=data.get("tool_calls", [])
        )
    
    # Legacy compatibility method
    def append_query(self, timestamp: datetime, user_id: int, user_name: str, 
                    query: str, response: str) -> None:
        """Legacy synchronous append method for backward compatibility."""
        query_obj = Query(
            user_id=user_id,
            user_name=user_name,
            query=query,
            response=response,
            timestamp=timestamp
        )
        csv_row = query_obj.to_csv_row()
        self._append_csv_sync(csv_row)