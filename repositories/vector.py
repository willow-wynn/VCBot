"""Repository for managing vector embeddings."""

import pickle
import json
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from datetime import datetime
import numpy as np

from models import VectorEmbedding
from .base import FileBasedRepository


class VectorRepository(FileBasedRepository[VectorEmbedding]):
    """Repository for managing vector embeddings."""
    
    def __init__(self, pickle_path: Path, metadata_path: Optional[Path] = None):
        """Initialize with paths for vector storage."""
        self.pickle_path = Path(pickle_path)
        self.metadata_path = metadata_path or self.pickle_path.with_suffix('.meta.json')
        
        # Ensure parent directories exist
        self.pickle_path.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._lock = asyncio.Lock()
        self._cache = None  # Cache loaded vectors
        self._cache_dirty = True
    
    async def save(self, entity: VectorEmbedding) -> None:
        """Save a vector embedding."""
        async with self._lock:
            # Load existing data
            vectors, metadata = await self._load_all()
            
            # Add new embedding
            vectors.append(entity.embedding)
            metadata.append({
                "text": entity.text,
                "source": entity.source,
                "metadata": entity.metadata,
                "created_at": entity.created_at.isoformat()
            })
            
            # Save updated data
            await self._save_all(vectors, metadata)
            self._cache_dirty = True
    
    async def save_batch(self, entities: List[VectorEmbedding]) -> None:
        """Save multiple vector embeddings efficiently."""
        async with self._lock:
            # Load existing data
            vectors, metadata = await self._load_all()
            
            # Add new embeddings
            for entity in entities:
                vectors.append(entity.embedding)
                metadata.append({
                    "text": entity.text,
                    "source": entity.source,
                    "metadata": entity.metadata,
                    "created_at": entity.created_at.isoformat()
                })
            
            # Save updated data
            await self._save_all(vectors, metadata)
            self._cache_dirty = True
    
    async def find_by_id(self, entity_id: str) -> Optional[VectorEmbedding]:
        """Find a vector by source ID."""
        _, metadata = await self._load_all()
        
        for i, meta in enumerate(metadata):
            if meta["source"] == entity_id:
                vectors, _ = await self._load_all()
                return VectorEmbedding(
                    text=meta["text"],
                    embedding=vectors[i],
                    source=meta["source"],
                    metadata=meta.get("metadata", {}),
                    created_at=datetime.fromisoformat(meta["created_at"])
                )
        return None
    
    async def find_all(self) -> List[VectorEmbedding]:
        """Find all vector embeddings."""
        vectors, metadata = await self._load_all()
        
        result = []
        for i, meta in enumerate(metadata):
            result.append(VectorEmbedding(
                text=meta["text"],
                embedding=vectors[i],
                source=meta["source"],
                metadata=meta.get("metadata", {}),
                created_at=datetime.fromisoformat(meta["created_at"])
            ))
        return result
    
    async def find_by_source_prefix(self, prefix: str) -> List[VectorEmbedding]:
        """Find all embeddings with source starting with prefix."""
        all_embeddings = await self.find_all()
        return [e for e in all_embeddings if e.source.startswith(prefix)]
    
    async def search_similar(self, query_embedding: List[float], top_k: int = 10) -> List[Tuple[VectorEmbedding, float]]:
        """Search for similar vectors using cosine similarity."""
        vectors, metadata = await self._load_all()
        
        if not vectors:
            return []
        
        # Convert to numpy arrays for efficient computation
        query_vec = np.array(query_embedding)
        doc_vecs = np.array(vectors)
        
        # Compute cosine similarities
        similarities = np.dot(doc_vecs, query_vec) / (
            np.linalg.norm(doc_vecs, axis=1) * np.linalg.norm(query_vec)
        )
        
        # Get top k indices
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        # Build results
        results = []
        for idx in top_indices:
            embedding = VectorEmbedding(
                text=metadata[idx]["text"],
                embedding=vectors[idx],
                source=metadata[idx]["source"],
                metadata=metadata[idx].get("metadata", {}),
                created_at=datetime.fromisoformat(metadata[idx]["created_at"])
            )
            results.append((embedding, float(similarities[idx])))
        
        return results
    
    async def delete(self, entity_id: str) -> bool:
        """Delete a vector by source ID."""
        async with self._lock:
            vectors, metadata = await self._load_all()
            
            # Find and remove the embedding
            for i, meta in enumerate(metadata):
                if meta["source"] == entity_id:
                    vectors.pop(i)
                    metadata.pop(i)
                    await self._save_all(vectors, metadata)
                    self._cache_dirty = True
                    return True
        return False
    
    async def delete_by_source_prefix(self, prefix: str) -> int:
        """Delete all embeddings with source starting with prefix."""
        async with self._lock:
            vectors, metadata = await self._load_all()
            
            # Find indices to delete
            indices_to_delete = []
            for i, meta in enumerate(metadata):
                if meta["source"].startswith(prefix):
                    indices_to_delete.append(i)
            
            # Delete in reverse order to maintain indices
            for i in reversed(indices_to_delete):
                vectors.pop(i)
                metadata.pop(i)
            
            if indices_to_delete:
                await self._save_all(vectors, metadata)
                self._cache_dirty = True
            
            return len(indices_to_delete)
    
    async def exists(self, entity_id: str) -> bool:
        """Check if a vector exists by source ID."""
        _, metadata = await self._load_all()
        return any(meta["source"] == entity_id for meta in metadata)
    
    async def _load_all(self) -> Tuple[List[List[float]], List[dict]]:
        """Load all vectors and metadata."""
        if self._cache is not None and not self._cache_dirty:
            return self._cache
        
        vectors = await self._load_vectors()
        metadata = await self._load_metadata()
        
        # Ensure consistency
        if len(vectors) != len(metadata):
            # Handle mismatch - prefer metadata length
            if len(vectors) > len(metadata):
                vectors = vectors[:len(metadata)]
            else:
                # Pad metadata with empty entries
                while len(metadata) < len(vectors):
                    metadata.append({
                        "text": "",
                        "source": f"unknown-{len(metadata)}",
                        "metadata": {},
                        "created_at": datetime.now().isoformat()
                    })
        
        self._cache = (vectors, metadata)
        self._cache_dirty = False
        return vectors, metadata
    
    async def _save_all(self, vectors: List[List[float]], metadata: List[dict]) -> None:
        """Save all vectors and metadata."""
        await self._save_vectors(vectors)
        await self._save_metadata(metadata)
    
    async def _load_vectors(self) -> List[List[float]]:
        """Load vectors from pickle file."""
        if self.pickle_path.exists():
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._load_vectors_sync)
        return []
    
    def _load_vectors_sync(self) -> List[List[float]]:
        """Synchronously load vectors from pickle."""
        with open(self.pickle_path, 'rb') as f:
            data = pickle.load(f)
            
            # Handle different formats
            if isinstance(data, dict):
                # Assume it's a dict with 'embeddings' key
                if 'embeddings' in data:
                    return data['embeddings']
                # Or it might be indexed by integers
                return [data[i] for i in sorted(data.keys()) if isinstance(i, int)]
            elif isinstance(data, list):
                return data
            else:
                return []
    
    async def _save_vectors(self, vectors: List[List[float]]) -> None:
        """Save vectors to pickle file."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._save_vectors_sync, vectors)
    
    def _save_vectors_sync(self, vectors: List[List[float]]) -> None:
        """Synchronously save vectors to pickle."""
        with open(self.pickle_path, 'wb') as f:
            pickle.dump(vectors, f)
    
    async def _load_metadata(self) -> List[dict]:
        """Load metadata from JSON file."""
        if self.metadata_path.exists():
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._load_metadata_sync)
        return []
    
    def _load_metadata_sync(self) -> List[dict]:
        """Synchronously load metadata from JSON."""
        with open(self.metadata_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    async def _save_metadata(self, metadata: List[dict]) -> None:
        """Save metadata to JSON file."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._save_metadata_sync, metadata)
    
    def _save_metadata_sync(self, metadata: List[dict]) -> None:
        """Synchronously save metadata to JSON."""
        with open(self.metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)