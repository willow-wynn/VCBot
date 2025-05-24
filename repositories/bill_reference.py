"""Repository for managing bill references."""

import json
import asyncio
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from models import BillReference, BillType
from .base import FileBasedRepository


class BillReferenceRepository(FileBasedRepository[BillReference]):
    """Repository for managing bill reference numbers."""
    
    def __init__(self, file_path: Path):
        """Initialize with file path for references."""
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        
        # Initialize file if it doesn't exist
        if not self.file_path.exists():
            self._save_refs_sync({})
    
    async def save(self, entity: BillReference) -> None:
        """Save a bill reference."""
        async with self._lock:
            refs = await self._load_refs()
            refs[entity.bill_type.value] = {
                "reference_number": entity.reference_number,
                "created_at": entity.created_at.isoformat(),
                "updated_at": entity.updated_at.isoformat()
            }
            await self._save_refs(refs)
    
    async def find_by_id(self, entity_id: str) -> Optional[BillReference]:
        """Find a bill reference by bill type."""
        refs = await self._load_refs()
        ref_data = refs.get(entity_id.lower())
        
        if ref_data:
            # Handle legacy format (just a number)
            if isinstance(ref_data, int):
                return BillReference(
                    bill_type=BillType.from_string(entity_id),
                    reference_number=ref_data,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
            # Handle new format (dict with metadata)
            else:
                return BillReference(
                    bill_type=BillType.from_string(entity_id),
                    reference_number=ref_data["reference_number"],
                    created_at=datetime.fromisoformat(ref_data["created_at"]),
                    updated_at=datetime.fromisoformat(ref_data["updated_at"])
                )
        return None
    
    async def find_all(self) -> Dict[str, BillReference]:
        """Find all bill references."""
        refs = await self._load_refs()
        result = {}
        
        for bill_type_str, ref_data in refs.items():
            try:
                bill_type = BillType.from_string(bill_type_str)
                if isinstance(ref_data, int):
                    result[bill_type_str] = BillReference(
                        bill_type=bill_type,
                        reference_number=ref_data,
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                else:
                    result[bill_type_str] = BillReference(
                        bill_type=bill_type,
                        reference_number=ref_data["reference_number"],
                        created_at=datetime.fromisoformat(ref_data["created_at"]),
                        updated_at=datetime.fromisoformat(ref_data["updated_at"])
                    )
            except ValueError:
                # Skip unknown bill types
                continue
                
        return result
    
    async def delete(self, entity_id: str) -> bool:
        """Delete a bill reference by bill type."""
        async with self._lock:
            refs = await self._load_refs()
            if entity_id.lower() in refs:
                del refs[entity_id.lower()]
                await self._save_refs(refs)
                return True
        return False
    
    async def exists(self, entity_id: str) -> bool:
        """Check if a bill reference exists."""
        refs = await self._load_refs()
        return entity_id.lower() in refs
    
    async def get_next_reference(self, bill_type: BillType) -> int:
        """Get the next reference number for a bill type."""
        async with self._lock:
            refs = await self._load_refs()
            current_ref = refs.get(bill_type.value)
            
            if current_ref is None:
                next_ref = 1
            elif isinstance(current_ref, int):
                next_ref = current_ref + 1
            else:
                next_ref = current_ref["reference_number"] + 1
            
            # Save the new reference directly without calling save()
            # to avoid deadlock (we already hold the lock)
            refs[bill_type.value] = {
                "reference_number": next_ref,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            await self._save_refs(refs)
            
            return next_ref
    
    async def _load_refs(self) -> Dict[str, any]:
        """Load references from file."""
        if self.file_path.exists():
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._load_refs_sync)
        return {}
    
    def _load_refs_sync(self) -> Dict[str, any]:
        """Synchronously load references from file."""
        with open(self.file_path, 'r') as f:
            return json.load(f)
    
    async def _save_refs(self, refs: Dict[str, any]) -> None:
        """Save references to file."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._save_refs_sync, refs)
    
    def _save_refs_sync(self, refs: Dict[str, any]) -> None:
        """Synchronously save references to file."""
        with open(self.file_path, 'w') as f:
            json.dump(refs, f, indent=2)
    
    # Legacy compatibility methods
    def load_refs(self) -> Dict[str, int]:
        """Legacy synchronous load method for backward compatibility."""
        refs = self._load_refs_sync()
        # Convert to legacy format (just numbers)
        legacy_refs = {}
        for bill_type, ref_data in refs.items():
            if isinstance(ref_data, int):
                legacy_refs[bill_type] = ref_data
            else:
                legacy_refs[bill_type] = ref_data["reference_number"]
        return legacy_refs
    
    def save_refs(self, refs: Dict[str, int]) -> None:
        """Legacy synchronous save method for backward compatibility."""
        # Convert from legacy format to new format
        new_refs = {}
        for bill_type, ref_num in refs.items():
            new_refs[bill_type] = {
                "reference_number": ref_num,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        self._save_refs_sync(new_refs)