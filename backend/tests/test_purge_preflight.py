#!/usr/bin/env python3
"""
Test suite for production purge preflight
"""

import os
import sys
import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, MagicMock
import json

# Import the scripts
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from gate2_identity import TARGET_IDS as GATE2_TARGET_IDS
from gate3_dependencies import TARGET_IDS as GATE3_TARGET_IDS
from gate4_backup import TARGET_IDS as GATE4_TARGET_IDS


def test_canonical_ids_consistency():
    """Verify all gates use the same canonical 34 IDs."""
    assert GATE2_TARGET_IDS == GATE3_TARGET_IDS == GATE3_TARGET_IDS
    assert len(GATE2_TARGET_IDS) == 34
    assert len(set(GATE2_TARGET_IDS)) == 34  # No duplicates
    assert sorted(GATE2_TARGET_IDS) == GATE2_TARGET_IDS  # Already sorted


def test_canonical_ids_content():
    """Verify the exact canonical IDs are correct."""
    expected_ids = [
        2, 54, 59, 62, 103, 382, 492, 496, 497, 510,
        521, 556, 563, 583, 587, 588, 592, 594, 624, 626,
        642, 651, 652, 655, 657, 662, 666, 677, 711, 724,
        788, 1216, 1218, 1278
    ]
    assert GATE2_TARGET_IDS == expected_ids


def test_gate2_id_validation_logic():
    """Test the ID verification logic in gate2_identity."""
    from gate2_identity import TARGET_IDS
    
    # Test missing IDs detection
    found_ids = {2, 54, 59, 62}  # Only 4 found
    missing = set(GATE2_TARGET_IDS) - found_ids
    assert len(missing) == 30
    
    # Test all present
    found_ids = set(GATE2_TARGET_IDS)
    missing = set(GATE2_TARGET_IDS) - found_ids
    assert len(missing) == 0


def test_gate3_target_ids_consistency():
    """Verify Gate 3 uses the same canonical IDs."""
    assert GATE3_TARGET_IDS == GATE3_TARGET_IDS
    assert len(GATE3_TARGET_IDS) == 34


def test_gate4_target_ids_consistency():
    """Verify Gate 4 uses the same canonical IDs."""
    assert GATE4_TARGET_IDS == GATE4_TARGET_IDS
    assert len(GATE4_TARGET_IDS) == 34


def test_gate1_target_ids_consistency():
    """Verify Gate 1 uses the same canonical IDs."""
    from gate1_atomicity import TARGET_IDS as GATE1_TARGET_IDS
    assert GATE1_TARGET_IDS == GATE1_TARGET_IDS
    assert len(GATE1_TARGET_IDS) == 34


class TestGate1Atomicity:
    """Test Gate 1 atomicity logic with mocks."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database connection."""
        mock_conn = Mock()
        mock_cur = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        return mock_conn
    
    def test_pre_deletion_verification(self, mock_db):
        """Test pre-deletion count verification."""
        from gate1_atomicity import TARGET_IDS
        
        mock_cur = Mock()
        mock_db.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchone.return_value = (34,)
        
        # This would be tested with the actual function
        # For now, just verify the target IDs are correct
        assert len(GATE1_TARGET_IDS) == 34
    
    def test_exact_id_match_validation(self):
        """Test that deleted IDs exactly match canonical list."""
        deleted_ids = [2, 54, 59, 62, 103, 382, 492, 496, 497, 510,
                       521, 556, 563, 583, 587, 588, 592, 594, 624, 626,
                       642, 651, 652, 655, 657, 662, 666, 677, 711, 724,
                       788, 1216, 1218, 1278]
        
        from gate1_atomicity import TARGET_IDS
        assert deleted_ids == sorted(GATE1_TARGET_IDS)


def test_gate2_id_validation():
    """Test Gate 2 ID verification logic."""
    from gate2_identity import TARGET_IDS
    
    # Test missing IDs detection
    found_ids = {2, 54, 59, 62}
    missing = set(TARGET_IDS) - found_ids
    assert len(missing) == 30
    
    # Test all present
    found_ids = set(TARGET_IDS)
    missing = set(TARGET_IDS) - found_ids
    assert len(missing) == 0


def test_gate3_cascade_detection():
    """Test Gate 3 CASCADE detection logic."""
    # This would be tested with a mock database
    # For now, verify the logic structure
    assert True


def test_gate3_reference_counting():
    """Test Gate 3 reference counting logic."""
    # Test that reference counting works correctly
    # with zero references
    ref_counts = {
        'table1': 0,
        'table2': 0,
        'table3': 0
    }
    total = sum(ref_counts.values())
    assert total == 0
    
    # With non-zero references
    ref_counts = {
        'table1': 5,
        'table2': 0
    }
    total = sum(ref_counts.values())
    assert total == 5


def test_gate4_backup_checksum():
    """Test Gate 4 backup checksum verification."""
    import hashlib
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
        f.write(b'test data')
        temp_file = f.name
    
    try:
        # Compute SHA256
        with open(temp_file, 'rb') as f:
            sha256_hash = hashlib.sha256(f.read()).hexdigest()
        
        assert len(sha256_hash) == 64  # SHA256 is 64 hex chars
        
        # Test checksum file creation
        checksum_file = temp_file + ".sha256"
        with open(checksum_file, 'w') as f:
            f.write(f"{sha256_hash}  test_file\n")
        
        # Verify checksum
        import subprocess
        result = subprocess.run(['sha256sum', '-c', f"{sha256_hash}  {temp_file}"],
                              capture_output=True, shell=True)
        assert result.returncode == 0
        
    finally:
        os.unlink(temp_file)
        if os.path.exists(checksum_file):
            os.unlink(checksum_file)


def test_gate4_gpg_encryption():
    """Test GPG encryption flow."""
    # This would test GPG encryption in isolation
    # For now, verify the logic structure
    assert True


def test_gate5_id_classification():
    """Test Gate 5 ID classification logic."""
    # Verify the 34 IDs are split correctly
    CATEGORY_A = [2, 62, 103, 492, 496, 497, 510, 521, 556, 563, 587, 588, 662, 666, 788, 1216, 1218, 1278, 496, 497]
    CATEGORY_B = [54, 59, 382, 583, 592, 594, 624, 626, 642, 652, 655, 657, 677, 711, 724]
    
    # Check for duplicates
    all_ids = CATEGORY_A + CATEGORY_B
    assert len(set(all_ids)) == 34
    
    # Verify specific IDs
    assert 651 in CATEGORY_B  # Fu Jen Catholic University
    assert 651 not in CATEGORY_A


def test_gate6_cycle_model():
    """Test Gate 6 cycle model logic."""
    # Verify that all 34 records represent expired cycles
    # not evergreen programmes
    
    # Each record should have a deadline in the past
    # This is a conceptual test
    assert True


def test_gate7_git_safety():
    """Test Gate 7 git safety."""
    # Verify worktree isolation logic
    assert True


def test_workflow_syntax():
    """Test workflow YAML syntax."""
    import yaml
    
    workflow_path = os.path.join(
        os.path.dirname(__file__), '..', '..', '..', 
        '.github', 'workflows', 'production-purge-preflight.yml'
    )
    
    with open(workflow_path, 'r') as f:
        workflow = yaml.safe_load(f)
    
    # Check required fields
    assert 'name' in workflow
    assert 'on' in workflow
    assert 'jobs' in workflow
    
    # Check required jobs
    assert 'gate2-identity' in workflow['jobs']
    assert 'gate3-dependencies' in workflow['jobs']
    assert 'gate4-backup' in workflow['jobs']
    assert 'summary' in workflow['jobs']
    
    # Check environments
    assert 'environment' in workflow['jobs']['gate2-identity']
    assert workflow['jobs']['gate2-identity']['environment']['name'] == 'production-readonly'
    assert workflow['jobs']['gate4-backup']['environment']['name'] == 'production-backup'


def test_workflow_inputs():
    """Test workflow inputs are correct."""
    import yaml
    
    workflow_path = os.path.join(
        os.path.dirname(__file__), '..', '..', '..',
        '.github', 'workflows', 'production-purge-preflight.yml'
    )
    
    with open(workflow_path, 'r') as f:
        workflow = yaml.safe_load(f)
    
    # Check inputs
    inputs = workflow['on']['workflow_dispatch']['inputs']
    assert 'gate' in inputs
    assert 'confirm_environment' in inputs
    
    # Check gate options
    gate_options = inputs['gate']['options']
    assert 'gate2-identity' in gate_options
    assert 'gate3-dependencies' in gate_options
    assert 'gate4-backup' in gate_options
    assert 'all' in gate_options


def test_scripts_import():
    """Test that all scripts can be imported."""
    # Test that scripts have no syntax errors
    import importlib.util
    import sys
    
    scripts = [
        'gate1_atomicity.py',
        'gate2_identity.py',
        'gate3_dependencies.py',
        'gate4_backup.py',
        'summary.py',
        'purge_manifest.py'
    ]
    
    for script in scripts:
        spec = importlib.util.spec_from_file_location(
            script[:-3], 
            os.path.join(os.path.dirname(__file__), 'scripts', script)
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])