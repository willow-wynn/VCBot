"""Tests for BillReferenceRepository."""

import pytest
import asyncio
import json
from pathlib import Path
from datetime import datetime
from repositories import BillReferenceRepository
from models import BillReference, BillType


class TestBillReferenceRepository:
    """Test cases for BillReferenceRepository."""
    
    @pytest.fixture
    def repository(self, temp_dir):
        """Create a BillReferenceRepository instance."""
        ref_file = temp_dir / "test_refs.json"
        return BillReferenceRepository(ref_file)
    
    @pytest.mark.asyncio
    async def test_save_and_find(self, repository):
        """Test saving and finding a bill reference."""
        # Create reference
        ref = BillReference(
            bill_type=BillType.HR,
            reference_number=123
        )
        
        # Save
        await repository.save(ref)
        
        # Find
        found = await repository.find_by_id("hr")
        assert found is not None
        assert found.bill_type == BillType.HR
        assert found.reference_number == 123
    
    @pytest.mark.asyncio
    async def test_find_all(self, repository):
        """Test finding all references."""
        # Save multiple references
        refs = [
            BillReference(bill_type=BillType.HR, reference_number=100),
            BillReference(bill_type=BillType.S, reference_number=50),
            BillReference(bill_type=BillType.HRES, reference_number=25)
        ]
        
        for ref in refs:
            await repository.save(ref)
        
        # Find all
        all_refs = await repository.find_all()
        assert len(all_refs) == 3
        assert "hr" in all_refs
        assert "s" in all_refs
        assert "hres" in all_refs
    
    @pytest.mark.asyncio
    async def test_get_next_reference(self, repository):
        """Test getting next reference number."""
        # First reference
        next_ref = await repository.get_next_reference(BillType.HR)
        assert next_ref == 1
        
        # Second reference
        next_ref = await repository.get_next_reference(BillType.HR)
        assert next_ref == 2
        
        # Different type starts at 1
        next_ref = await repository.get_next_reference(BillType.S)
        assert next_ref == 1
    
    @pytest.mark.asyncio
    async def test_delete(self, repository):
        """Test deleting a reference."""
        # Save
        ref = BillReference(bill_type=BillType.HR, reference_number=123)
        await repository.save(ref)
        
        # Delete
        deleted = await repository.delete("hr")
        assert deleted is True
        
        # Verify deleted
        found = await repository.find_by_id("hr")
        assert found is None
    
    @pytest.mark.asyncio
    async def test_exists(self, repository):
        """Test checking if reference exists."""
        # Initially doesn't exist
        exists = await repository.exists("hr")
        assert exists is False
        
        # Save
        ref = BillReference(bill_type=BillType.HR, reference_number=123)
        await repository.save(ref)
        
        # Now exists
        exists = await repository.exists("hr")
        assert exists is True
    
    def test_legacy_compatibility(self, repository):
        """Test backward compatibility with legacy format."""
        # Save using legacy methods
        repository.save_refs({"hr": 100, "s": 50})
        
        # Load using legacy method
        refs = repository.load_refs()
        assert refs == {"hr": 100, "s": 50}
    
    @pytest.mark.asyncio
    async def test_legacy_format_loading(self, repository, temp_dir):
        """Test loading legacy format (just numbers)."""
        # Create legacy format file
        ref_file = temp_dir / "test_refs.json"
        ref_file.write_text('{"hr": 100, "s": 50}')
        
        # Create new repository
        repo = BillReferenceRepository(ref_file)
        
        # Should load legacy format
        ref = await repo.find_by_id("hr")
        assert ref.reference_number == 100
        assert ref.bill_type == BillType.HR
    
    @pytest.mark.asyncio
    async def test_concurrent_updates(self, repository):
        """Test handling concurrent updates."""
        # Simulate concurrent get_next_reference calls
        tasks = []
        for i in range(10):
            task = repository.get_next_reference(BillType.HR)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # All results should be unique
        assert len(set(results)) == 10
        # Should be sequential
        assert sorted(results) == list(range(1, 11))
    
    @pytest.mark.asyncio
    async def test_case_insensitivity(self, repository):
        """Test that bill types are case insensitive."""
        # Save with lowercase
        ref = BillReference(bill_type=BillType.HR, reference_number=123)
        await repository.save(ref)
        
        # Find with uppercase
        found = await repository.find_by_id("HR")
        assert found is not None
        assert found.reference_number == 123
        
        # Find with mixed case
        found = await repository.find_by_id("Hr")
        assert found is not None
        assert found.reference_number == 123
    
    @pytest.mark.asyncio
    async def test_update_preserves_metadata(self, repository):
        """Test that updates preserve creation time."""
        # Create and save
        ref = BillReference(bill_type=BillType.HR, reference_number=100)
        original_created = ref.created_at
        await repository.save(ref)
        
        # Update
        await asyncio.sleep(0.1)  # Ensure time difference
        ref.reference_number = 200
        ref.updated_at = datetime.now()
        await repository.save(ref)
        
        # Load and verify
        loaded = await repository.find_by_id("hr")
        assert loaded.reference_number == 200
        assert loaded.created_at == original_created
        assert loaded.updated_at > original_created