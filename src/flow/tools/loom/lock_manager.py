import os
import time
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, Generator

from ..base import ToolError

logger = logging.getLogger(__name__)

class LockManager:
    """
    Manages file locks to prevent concurrent edits.
    Uses .lock.{filename}.{pid} strategy with stale lock detection.
    """
    def __init__(self, timeout_seconds: int = 30):
        self.timeout = timeout_seconds

    @contextmanager
    def acquire(self, target_path: Path) -> Generator[None, None, None]:
        """
        Acquires a lock for the generic target_path.
        Yields control when lock is acquired.
        Releases lock on exit.
        """
        # Format: .lock.filename.PID
        pid = os.getpid()
        lock_file = target_path.parent / f".lock.{target_path.name}.{pid}"
        
        # Pattern to find existing locks: .lock.filename.*
        lock_glob = f".lock.{target_path.name}.*"
        
        try:
            self._try_lock(lock_file, target_path.parent, lock_glob)
            yield
        finally:
            if lock_file.exists():
                try:
                    lock_file.unlink()
                except OSError as e:
                    logger.warning(f"Failed to release lock {lock_file}: {e}")

    def _try_lock(self, my_lock: Path, directory: Path, pattern: str):
        # 1. Check for existing locks
        existing = list(directory.glob(pattern))
        
        for lock in existing:
            if lock == my_lock:
                continue # scanning myself? unlikely but safe
                
            if self._is_stale(lock):
                logger.warning(f"Breaking stale/dead lock: {lock}")
                try:
                    lock.unlink()
                except OSError:
                    pass # Race condition
            else:
                raise ToolError(
                    f"Resource busy. Locked by {lock.name}",
                    code="ResourceBusy"
                )

        # 2. Atomic Create
        try:
            my_lock.touch(exist_ok=False)
        except OSError as e:
            raise ToolError(f"Lock creation failed: {e}", code="LockError")

    def _is_stale(self, lock_file: Path) -> bool:
        """
        Checks if lock is stale based on:
        1. Process Liveness (PID check) - Zero-wait recovery
        2. Timeout (Backup)
        """
        try:
            # Parse PID from filename: .lock.name.PID
            parts = lock_file.name.split('.')
            if len(parts) < 4:
                 # Malformed lock? Fallback to time
                 return self._check_time(lock_file)
            
            try:
                pid = int(parts[-1])
            except ValueError:
                return self._check_time(lock_file)

            if not self._process_exists(pid):
                return True # Dead process = Stale immediately
            
            return self._check_time(lock_file)

        except FileNotFoundError:
            return False # Gone

    def _check_time(self, lock_file: Path) -> bool:
        stat = lock_file.stat()
        age = time.time() - stat.st_mtime
        return age > self.timeout

    def _process_exists(self, pid: int) -> bool:
        if os.name == 'nt':
            import ctypes
            kernel32 = ctypes.windll.kernel32
            SYNCHRONIZE = 0x00100000
            PROCESS_QUERY_INFORMATION = 0x0400
            wait_result = 0 
            
            # OpenProcess returns 0 on failure
            process = kernel32.OpenProcess(SYNCHRONIZE | PROCESS_QUERY_INFORMATION, False, pid)
            if not process:
                return False
            
            # GetExitCodeProcess? Or just ability to open implies existence?
            # Actually, if we can open it, it exists OR is a zombie.
            # Only reliable way is to check exit code.
            exit_code = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code)):
                kernel32.CloseHandle(process)
                return exit_code.value == 259 # STILL_ACTIVE
            
            kernel32.CloseHandle(process)
            return False
        else:
            try:
                os.kill(pid, 0)
                return True
            except ProcessLookupError:
                return False
            except PermissionError:
                return True # Exists but owned by other user

