"""
Reference service for managing bill reference numbers.
"""

import json
import os
import asyncio
from typing import Dict, Optional
from pathlib import Path

from models import BillType
from repositories import BillReferenceRepository


class ReferenceService:
    """Service for managing bill reference numbers."""
    
    def __init__(self, ref_file_path: str, file_manager=None, repository: Optional[BillReferenceRepository] = None):
        """Initialize reference service.
        
        Args:
            ref_file_path: Path to the reference JSON file
            file_manager: FileManager instance for file operations
            repository: Optional BillReferenceRepository for new data layer
        """
        self.ref_file_path = ref_file_path
        self.file_manager = file_manager
        self.repository = repository or BillReferenceRepository(Path(ref_file_path))
    
    def load_refs(self) -> Dict[str, int]:
        """Load references from file.
        
        Returns:
            Dictionary mapping bill types to current reference numbers
        """
        print(f"Loading references from {self.ref_file_path}")
        # Use repository's synchronous compatibility method
        return self.repository.load_refs()
    
    def save_refs(self, refs: Dict[str, int]) -> None:
        """Save references to file.
        
        Args:
            refs: Dictionary mapping bill types to reference numbers
        """
        print(f"Saving references: {refs} to {self.ref_file_path}")
        # Use repository's synchronous compatibility method
        self.repository.save_refs(refs)
    
    def get_next_reference(self, bill_type: str) -> int:
        """Get next reference number for bill type.
        
        Args:
            bill_type: Type of bill (hr, hres, etc.)
            
        Returns:
            Next available reference number
        """
        # Run async method synchronously for backward compatibility
        bill_type_enum = BillType.from_string(bill_type)
        
        # Check if there's already a running loop (e.g., in tests)
        try:
            loop = asyncio.get_running_loop()
            # We're already in an async context
            # Use run_coroutine_threadsafe to run in the existing loop from sync context
            return asyncio.run_coroutine_threadsafe(
                self.repository.get_next_reference(bill_type_enum), 
                loop
            ).result()
        except RuntimeError:
            # No running loop, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.repository.get_next_reference(bill_type_enum))
            finally:
                loop.close()
    
    async def get_next_reference_async(self, bill_type: str) -> int:
        """Async version of get_next_reference.
        
        Args:
            bill_type: Type of bill (hr, hres, etc.)
            
        Returns:
            Next available reference number
        """
        bill_type_enum = BillType.from_string(bill_type)
        return await self.repository.get_next_reference(bill_type_enum)
    
    def update_reference(self, bill_type: str, reference_number: int) -> int:
        """Update reference number for a bill type.
        
        Args:
            bill_type: Type of bill
            reference_number: New reference number
            
        Returns:
            The updated reference number
        """
        refs = self.load_refs()
        current = refs.get(bill_type.lower(), 0)
        # Don't go backward
        refs[bill_type.lower()] = max(current, reference_number)
        self.save_refs(refs)
        return refs[bill_type.lower()]
    
    def set_reference(self, bill_type: str, reference_number: int) -> None:
        """Set reference number for a bill type (admin function).
        
        Args:
            bill_type: Type of bill
            reference_number: Reference number to set
        """
        refs = self.load_refs()
        refs[bill_type.lower()] = reference_number
        self.save_refs(refs)