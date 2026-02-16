import pytest
import subprocess
import sys
import time
import os
import psutil
from src.flow.tools.shell.win32_job import WindowsJobObject

@pytest.mark.skipif(os.name != 'nt', reason="Windows Job Objects only on NT")
def test_job_object_kills_child_on_close():
    """T6.02: Verify child process is killed when Job Object is closed."""
    # 1. Start a long-running process (sleep 30)
    # Use python executable to be safe and portable
    cmd = [sys.executable, "-c", "import time; time.sleep(30)"]
    proc = subprocess.Popen(cmd)
    
    try:
        pid = proc.pid
        assert psutil.pid_exists(pid)
        
        # 2. Create Job and Assign
        job = WindowsJobObject()
        job.assign_process(proc._handle)
        
        # 3. Close Job (Simulate Parent Death/Cleanup)
        # We explicitly close the handle.
        # implementation of WindowsJobObject sets JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        job.close()
        
        # 4. Verify Child Death
        # It might take a few milliseconds
        gone, alive = psutil.wait_procs([psutil.Process(pid)], timeout=2.0)
        
        # If gone, it worked. If alive, it failed.
        assert not alive, f"Process {pid} should be dead"
        assert not psutil.pid_exists(pid)
        
    finally:
        # Cleanup if test failed
        if proc.poll() is None:
            proc.kill()

def test_job_object_lifecycle():
    """T6.03: Verify Job Object creation and assignment API."""
    if os.name != 'nt':
        return

    job = WindowsJobObject()
    assert job._job_handle is not None
    
    # Start dummy
    cmd = [sys.executable, "-c", "print('hello')"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    proc.wait()
    
    # Assigning a dead process might fail or succeed depending on Windows version/timing,
    # but the API call should at least attempt it.
    # Actually, assigning a dead process handle usually fails if the handle is closed,
    # but proc._handle is kept open by Popen object.
    
    # Let's assign a live one to be sure of API correctness
    cmd2 = [sys.executable, "-c", "import time; time.sleep(1)"]
    proc2 = subprocess.Popen(cmd2)
    try:
        job.assign_process(proc2._handle)
        # Should not raise
    finally:
        proc2.kill()
        job.close()
