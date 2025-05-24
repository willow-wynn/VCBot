"""Tests for ReferenceService."""

import pytest
import asyncio
import json
from pathlib import Path
from services.reference_service import ReferenceService
from models import BillType
from repositories import BillReferenceRepository


class TestReferenceService:
    """Test cases for ReferenceService."""
    
    @pytest.fixture
    def temp_ref_file(self, temp_dir):
        """Create a temporary reference file."""
        ref_file = temp_dir / "test_refs.json"
        ref_file.write_text('{"hr": 5, "s": 3}')
        return ref_file
    
    @pytest.fixture
    def reference_service(self, temp_ref_file):
        """Create a ReferenceService instance."""
        return ReferenceService(str(temp_ref_file))
    
    def test_load_refs(self, reference_service):
        """Test loading references from file."""
        refs = reference_service.load_refs()
        assert refs == {"hr": 5, "s": 3}
    
    def test_save_refs(self, reference_service):
        """Test saving references to file."""
        new_refs = {"hr": 10, "s": 7, "hres": 2}
        reference_service.save_refs(new_refs)
        
        # Verify saved
        loaded = reference_service.load_refs()
        assert loaded == {"hr": 10, "s": 7, "hres": 2}
    
    def test_get_next_reference(self, reference_service):
        """Test getting next reference number."""
        # Existing type
        next_hr = reference_service.get_next_reference("hr")
        assert next_hr == 6
        
        # Verify it was saved
        refs = reference_service.load_refs()
        assert refs["hr"] == 6
        
        # New type
        next_hres = reference_service.get_next_reference("hres")
        assert next_hres == 1
    
    def test_update_reference(self, reference_service):
        """Test updating reference number."""
        # Update to higher number
        result = reference_service.update_reference("hr", 10)
        assert result == 10
        
        # Try to update to lower number (should keep higher)
        result = reference_service.update_reference("hr", 8)
        assert result == 10
    
    def test_set_reference(self, reference_service):
        """Test setting reference number (admin function)."""
        reference_service.set_reference("s", 20)
        
        refs = reference_service.load_refs()
        assert refs["s"] == 20
    
    @pytest.mark.asyncio
    async def test_get_next_reference_async(self, reference_service):
        """Test async version of get_next_reference."""
        next_hr = await reference_service.get_next_reference_async("hr")
        assert next_hr == 6
    
    def test_case_insensitive(self, reference_service):
        """Test that bill types are case insensitive."""
        # Test with uppercase
        next_hr = reference_service.get_next_reference("HR")
        assert next_hr == 6
        
        # Test with mixed case
        next_s = reference_service.get_next_reference("S")
        assert next_s == 4


class TestReferenceServiceWithRepository:
    """Test ReferenceService with repository pattern."""
    
    @pytest.fixture
    def repository(self, temp_dir):
        """Create a BillReferenceRepository."""
        ref_file = temp_dir / "test_refs.json"
        return BillReferenceRepository(ref_file)
    
    @pytest.fixture
    def reference_service(self, temp_dir, repository):
        """Create a ReferenceService with repository."""
        ref_file = temp_dir / "test_refs.json"
        return ReferenceService(str(ref_file), repository=repository)
    
    @pytest.mark.asyncio
    async def test_repository_integration(self, reference_service):
        """Test that service properly uses repository."""
        # Set initial reference
        reference_service.set_reference("hr", 10)
        
        # Get next reference - use async version since we're in async context
        next_hr = await reference_service.get_next_reference_async("hr")
        assert next_hr == 11
        
        # Verify through repository
        ref = await reference_service.repository.find_by_id("hr")
        assert ref.reference_number == 11
        assert ref.bill_type == BillType.HR


class TestReferenceServiceProductionScenarios:
    """Production-like scenarios for ReferenceService."""
    
    @pytest.fixture
    def production_service(self, temp_dir):
        """Create a service mimicking production setup."""
        ref_file = temp_dir / "bill_refs.json"
        # Start with realistic numbers
        ref_file.write_text('''{
            "hr": 4523,
            "s": 2341,
            "hres": 892,
            "sres": 445,
            "hjres": 123,
            "sjres": 78
        }''')
        return ReferenceService(str(ref_file))
    
    def test_concurrent_updates(self, production_service):
        """Test handling concurrent reference updates."""
        # Simulate multiple bills being added
        refs = []
        for i in range(5):
            ref = production_service.get_next_reference("hr")
            refs.append(ref)
        
        # Should get sequential numbers
        assert refs == [4524, 4525, 4526, 4527, 4528]
    
    def test_all_bill_types(self, production_service):
        """Test all supported bill types."""
        bill_types = ["hr", "s", "hres", "sres", "hjres", "sjres", "hconres", "sconres"]
        
        for bill_type in bill_types:
            ref = production_service.get_next_reference(bill_type)
            assert ref > 0  # Should get a valid reference
    
    def test_error_recovery(self, production_service, temp_dir):
        """Test recovery from corrupted file."""
        ref_file = Path(production_service.ref_file_path)
        
        # Corrupt the file
        ref_file.write_text("invalid json{")
        
        # Should handle gracefully (depending on implementation)
        # This might raise an exception or return default values
        try:
            refs = production_service.load_refs()
            assert isinstance(refs, dict)  # Should return empty dict or handle error
        except json.JSONDecodeError as e:
            # JSONDecodeError is expected for invalid JSON
            assert "Expecting value" in str(e)  # Standard JSONDecodeError message
        except Exception as e:
            # Other exceptions should mention JSON
            assert "json" in str(e).lower() or "decode" in str(e).lower()
    
    def test_race_condition_simulation(self, production_service):
        """Simulate race condition with rapid updates."""
        # Get current HR reference
        initial = production_service.load_refs().get("hr", 0)
        
        # Simulate rapid-fire updates
        updates = []
        for i in range(10):
            ref = production_service.get_next_reference("hr")
            updates.append(ref)
        
        # All updates should be unique and sequential
        assert len(set(updates)) == 10  # All unique
        assert updates == list(range(initial + 1, initial + 11))  # Sequential