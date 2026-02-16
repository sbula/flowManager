import pytest
import time
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.flow.tools.file.loom.lock_manager import LockManager
from src.flow.tools.base import ToolError

@pytest.fixture
def lock_manager():
    return LockManager(timeout_seconds=1)

def test_acquire_release(lock_manager, tmp_path):
    target = tmp_path / "file.txt"
    # lock pattern
    lock_glob = ".lock.file.txt.*"
    
    with lock_manager.acquire(target):
        # Check if ANY lock file exists
        locks = list(tmp_path.glob(lock_glob))
        assert len(locks) == 1
        assert str(os.getpid()) in locks[0].name
    
    # After release, no locks
    locks = list(tmp_path.glob(lock_glob))
    assert len(locks) == 0

def test_resource_busy(lock_manager, tmp_path):
    target = tmp_path / "file.txt"
    # Create a fresh lock with a fake PID (but we need to mock liveness check if we use fake PID)
    # If we use a random PID, _process_exists might return False.
    # So we should mock _process_exists to return True (Alive)
    
    lock_file = tmp_path / ".lock.file.txt.99999"
    lock_file.touch()
    
    with patch.object(LockManager, "_process_exists", return_value=True):
        with pytest.raises(ToolError) as exc:
            with lock_manager.acquire(target):
                pass
            
    assert exc.value.code == "ResourceBusy"

def test_break_stale_lock(lock_manager, tmp_path):
    target = tmp_path / "file.txt"
    # Create a stale lock (old time)
    # PID doesn't matter if time > timeout?
    # Wait, in new logic:
    # 1. Parse PID.
    # 2. Check Liveness. If Dead -> Stale.
    # 3. If Alive -> Check Time.
    
    # So to test Time-based staleness, we need PID to be ALIVE (or unparseable/missing).
    # Let's use a lock with Alive PID but Old Time.
    
    lock_file = tmp_path / ".lock.file.txt.88888"
    lock_file.touch()
    
    # Mock Backdate
    os_utime_target = time.time() - 2
    os.utime(lock_file, (os_utime_target, os_utime_target))
    
    # Mock PID as Alive
    with patch.object(LockManager, "_process_exists", return_value=True):
         with lock_manager.acquire(target):
              # Should have broken the old lock and created new one
              assert not lock_file.exists()
              locks = list(tmp_path.glob(".lock.file.txt.*"))
              assert len(locks) == 1

