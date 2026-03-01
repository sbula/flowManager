import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

# This test requires two helper scripts to be created on the fly
# 1. parent_process.py: Initializes ShellTool, runs a child, then sleeps.
# 2. child_process.py: Sleeps and touches a heartbeat file.

PARENT_SCRIPT = """
import sys
import time
import os
from flow.tools.shell import ShellTool
from flow.tools.base import ToolContext

def main():
    print(f"Parent PID: {os.getpid()}", flush=True)
    
    # 1. Setup Tool
    tool = ShellTool()
    context = ToolContext(
        service_root=os.getcwd(),
        isolation_level="STRICT",
        allowed_commands=[],
        access_token="",
        volume_id="vol-test",
        role="dev"
    )
    
    # 2. Run Child Process via Tool
    # We use a long-running command.
    # On Windows/Linux, python is safe.
    child_script = sys.argv[1]
    
    print("Starting child...", flush=True)
    # This runs synchronously, so we can't use it directly if we want to run in parallel?
    # Wait, ShellTool.run *blocks* until completion.
    # IF we want to test "Kill Parent while Child Running", we need the tool to be running.
    # So the Parent Script is effectively "Running the Tool".
    # The Tool runs the Child.
    
    try:
        tool.run({
            "operation": "run_command", # or run_test, assuming we mapped it
            # actually we mapped run_command to DEPRECATED in spec, but for valid ops...
            # The spec says "run_test" or "install_dependencies". 
            # Let's use "run_test" which calls run_command internally.
            # But run_test invokes pytest. 
            # We need a way to run an arbitrary script.
            # ShellTool has no generic "run_script" for Devs? 
            # SystemTool has system_ctl.
            # Wait, ShellTool has "run_lint" -> "flake8".
            # If we strictly follow spec, we can't run arbitrary python?
            # T1.09 says "run_command deprecated".
            
            # HACK: For this integration test, we might need to bypass the "Allow List" 
            # or rely on the Fact that we are testing the *Supervisor*, not the *Allow List*.
            # Let's assume we can modify the tool or use a backdoor or just use 'install_dependencies' with a custom command?
            # 'install_dependencies' -> 'npm ci' or 'poetry install'.
            # That's hard to control duration.
            
            # Let's look at ShellTool impl. 
            # If we are testing src.flow.tools.shell, we can import it and invoke _run_command directly?
            # No, we want to test IT as a unit.
            
            # Let's use `create_directory`? No process.
            # What spawns a process? `git_checkout`, `git_commit`, `run_test`, `install_dependencies`.
            # `run_test` runs `pytest`. 
            # If we create a dummy `pytest.ini` or `conftest.py` that sleeps?
            # Yes! `pytest` collects tests. If we have a test that sleeps 100s.
            "operation": "run_test",
            "target": "dummy_test.py"
        }, context)
    except Exception as e:
        print(f"Parent Exception: {e}", flush=True)

if __name__ == "__main__":
    main()
"""

CHILD_TEST = """
import time
import os

def test_sleep_forever():
    print(f"Child Test PID: {os.getpid()}", flush=True)
    with open("child.pid", "w") as f:
        f.write(str(os.getpid()))
    
    # Write heartbeat
    with open("heartbeat.txt", "w") as f:
        f.write("alive")
        
    time.sleep(60) # Sleep long enough to be killed
"""


@pytest.mark.integration
def test_fate_sharing_real(tmp_path):
    """
    T6.02/T6.07: Real Process Fate Sharing.
    1. Spawn Parent (simulating Engine).
    2. Parent runs ShellTool -> spawns 'pytest' (Child).
    3. Kill Parent.
    4. Verify Child 'pytest' process also dies.
    """
    # 1. Prepare Environment
    (tmp_path / "parent.py").write_text(PARENT_SCRIPT, encoding="utf-8")
    (tmp_path / "dummy_test.py").write_text(CHILD_TEST, encoding="utf-8")

    # We need to ensure src is in pythonpath for parent.py
    env = os.environ.copy()
    # c:\development\pitbula\flowManager\tests\integration\tools\test_lifecycle_real.py
    # ... \tests\integration\tools
    # ... \tests\integration
    # ... \tests
    # ... \flowManager

    repo_root = "c:/development/pitbula/flowManager"
    src_root = f"{repo_root}/src"
    env["PYTHONPATH"] = f"{src_root};{repo_root};{env.get('PYTHONPATH', '')}"

    # 2. Start Parent
    parent_proc = subprocess.Popen(
        [sys.executable, "parent.py", "dummy_test.py"],
        cwd=str(tmp_path),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        bufsize=1,
    )

    # 3. Wait for Child to start (check pid file)
    child_pid_file = tmp_path / "child.pid"
    child_pid = None

    # Wait up to 10 seconds for child to write PID
    for _ in range(20):
        if child_pid_file.exists():
            content = child_pid_file.read_text().strip()
            if content.isdigit():
                child_pid = int(content)
                break
        time.sleep(0.5)

    if child_pid is None:
        parent_proc.terminate()
        out, err = parent_proc.communicate()
        print("STDOUT:", out, file=sys.stderr)
        print("STDERR:", err, file=sys.stderr)
        assert False, "Child process did not start or write PID"

    # Verify Child is running
    import psutil

    assert psutil.pid_exists(child_pid), f"Child {child_pid} should be running"

    # 4. Kill Parent (Simulate Engine Crash)
    # We rely on Job Objects (Windows) or PDeathSig/Group (Linux)
    print(f"Killing Parent {parent_proc.pid}...", file=sys.stderr)
    parent_proc.terminate()
    # note: terminate() maps to TerminateProcess on Windows (Hard Kill-ish) or SIGTERM on Linux.
    # To simulate HARD crash, we might use kill() (SIGKILL).
    parent_proc.kill()
    parent_proc.wait()

    # 5. Verify Child Death
    # Wait a moment for OS to clean up
    time.sleep(2)

    is_alive = psutil.pid_exists(child_pid)

    # Debug info if failed
    if is_alive:
        try:
            p = psutil.Process(child_pid)
            print(f"Child Status: {p.status()}", file=sys.stderr)
        except:
            pass

    assert (
        not is_alive
    ), f"Child Process {child_pid} survived Parent Death! Fate sharing failed."
