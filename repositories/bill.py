"""Repository for managing bills."""

import json
import asyncio
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime

from models import Bill, BillType
from .base import FileBasedRepository


class BillRepository(FileBasedRepository[Bill]):
    """Repository for managing bills and their content."""
    
    def __init__(self, text_dir: Path, pdf_dir: Path, metadata_dir: Path):
        """Initialize with directories for bill storage."""
        self.text_dir = Path(text_dir)
        self.pdf_dir = Path(pdf_dir)
        self.metadata_dir = Path(metadata_dir)
        
        # Create directories if they don't exist
        self.text_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        
        self._lock = asyncio.Lock()
    
    async def save(self, entity: Bill) -> None:
        """Save a bill with all its components."""
        async with self._lock:
            # Save text content
            text_path = self.text_dir / f"{entity.filename_base}.txt"
            await self._save_text(text_path, entity.text_content)
            
            # Save metadata
            metadata_path = self.metadata_dir / f"{entity.filename_base}.json"
            metadata = entity.to_dict()
            metadata["text_path"] = str(text_path)
            await self._save_json(metadata_path, metadata)
    
    async def save_pdf(self, bill_identifier: str, pdf_content: bytes) -> str:
        """Save PDF content for a bill."""
        async with self._lock:
            pdf_path = self.pdf_dir / f"{bill_identifier}.pdf"
            await self._save_bytes(pdf_path, pdf_content)
            
            # Update metadata if bill exists
            bill = await self.find_by_id(bill_identifier)
            if bill:
                bill.pdf_path = str(pdf_path)
                bill.updated_at = datetime.now()
                await self.save(bill)
            
            return str(pdf_path)
    
    async def find_by_id(self, entity_id: str) -> Optional[Bill]:
        """Find a bill by its identifier."""
        metadata_path = self.metadata_dir / f"{entity_id}.json"
        
        if metadata_path.exists():
            metadata = await self._load_json(metadata_path)
            return self._dict_to_bill(metadata)
        
        # Try legacy format (just text file)
        text_path = self.text_dir / f"{entity_id}.txt"
        if text_path.exists():
            text_content = await self._load_text(text_path)
            
            # Parse bill type and number from identifier
            parts = entity_id.split('-')
            if len(parts) >= 2:
                try:
                    bill_type = BillType.from_string(parts[0])
                    reference_number = int(parts[1])
                    
                    return Bill(
                        identifier=entity_id,
                        title=f"Legacy Bill {entity_id}",
                        bill_type=bill_type,
                        reference_number=reference_number,
                        text_content=text_content,
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                except (ValueError, IndexError):
                    pass
        
        return None
    
    async def find_all(self) -> List[Bill]:
        """Find all bills."""
        bills = []
        
        # Load from metadata files
        for metadata_file in self.metadata_dir.glob("*.json"):
            metadata = await self._load_json(metadata_file)
            bills.append(self._dict_to_bill(metadata))
        
        # Check for legacy text files without metadata
        for text_file in self.text_dir.glob("*.txt"):
            identifier = text_file.stem
            metadata_path = self.metadata_dir / f"{identifier}.json"
            
            if not metadata_path.exists():
                # Try to load as legacy bill
                bill = await self.find_by_id(identifier)
                if bill:
                    bills.append(bill)
        
        return bills
    
    async def find_by_type(self, bill_type: BillType) -> List[Bill]:
        """Find all bills of a specific type."""
        all_bills = await self.find_all()
        return [b for b in all_bills if b.bill_type == bill_type]
    
    async def find_by_title_contains(self, search_term: str) -> List[Bill]:
        """Find bills whose title contains the search term."""
        all_bills = await self.find_all()
        search_lower = search_term.lower()
        return [b for b in all_bills if search_lower in b.title.lower()]
    
    async def delete(self, entity_id: str) -> bool:
        """Delete a bill and all its files."""
        async with self._lock:
            deleted = False
            
            # Delete text file
            text_path = self.text_dir / f"{entity_id}.txt"
            if text_path.exists():
                text_path.unlink()
                deleted = True
            
            # Delete PDF file
            pdf_path = self.pdf_dir / f"{entity_id}.pdf"
            if pdf_path.exists():
                pdf_path.unlink()
                deleted = True
            
            # Delete metadata file
            metadata_path = self.metadata_dir / f"{entity_id}.json"
            if metadata_path.exists():
                metadata_path.unlink()
                deleted = True
            
            return deleted
    
    async def exists(self, entity_id: str) -> bool:
        """Check if a bill exists."""
        metadata_path = self.metadata_dir / f"{entity_id}.json"
        text_path = self.text_dir / f"{entity_id}.txt"
        return metadata_path.exists() or text_path.exists()
    
    async def _save_text(self, path: Path, content: str) -> None:
        """Save text content to file."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._save_text_sync, path, content)
    
    def _save_text_sync(self, path: Path, content: str) -> None:
        """Synchronously save text to file."""
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    async def _load_text(self, path: Path) -> str:
        """Load text content from file."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._load_text_sync, path)
    
    def _load_text_sync(self, path: Path) -> str:
        """Synchronously load text from file."""
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    
    async def _save_bytes(self, path: Path, content: bytes) -> None:
        """Save binary content to file."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._save_bytes_sync, path, content)
    
    def _save_bytes_sync(self, path: Path, content: bytes) -> None:
        """Synchronously save bytes to file."""
        with open(path, 'wb') as f:
            f.write(content)
    
    async def _save_json(self, path: Path, data: dict) -> None:
        """Save JSON data to file."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._save_json_sync, path, data)
    
    def _save_json_sync(self, path: Path, data: dict) -> None:
        """Synchronously save JSON to file."""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    async def _load_json(self, path: Path) -> dict:
        """Load JSON data from file."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._load_json_sync, path)
    
    def _load_json_sync(self, path: Path) -> dict:
        """Synchronously load JSON from file."""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _dict_to_bill(self, data: dict) -> Bill:
        """Convert dictionary to Bill object."""
        return Bill(
            identifier=data["identifier"],
            title=data["title"],
            bill_type=BillType.from_string(data["bill_type"]),
            reference_number=data["reference_number"],
            text_content=data["text_content"],
            pdf_path=data.get("pdf_path"),
            sponsor=data.get("sponsor"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {})
        )