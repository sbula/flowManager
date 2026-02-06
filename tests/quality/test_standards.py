import subprocess

import pytest


def run_command(command):
    """Runs a shell command and returns exit code."""
    # usage of shell=True for simple CLI wrappers
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"\n[FAIL] Command: {command}")
        print(f"Output:\n{result.stdout}")
        print(f"Error:\n{result.stderr}")
    return result.returncode


def test_complexity_compliance():
    """
    Enforces Cyclomatic Complexity Standards using Lizard.
    Thresholds: CCN <= 10, Length <= 1000 lines.
    """
    # -w: Warnings only (exit code 0)? No, -w means print warnings.
    # But usually we want to FAIL on violation.
    # Lizard exit codes:
    # 0: No violations
    # 1: Violations found (if configured?)
    # By default lizard returns 0 unless we use -w? No.
    # We used -w in validate.sh and checked exit code.
    # Actually, lizard returns 1 if thresholds exceeded.

    # Using 'src/' as target.
    exit_code = run_command("lizard src/ -C 10 -L 1000")
    assert exit_code == 0, "Code Complexity Violations Found. See output."


def test_formatting_compliance():
    """
    Enforces Black (The Uncompromising Code Formatter).
    """
    exit_code = run_command("poetry run black --check src/ tests/")
    assert (
        exit_code == 0
    ), "Black Formatting Checks Failed. Run 'poetry run black .' to fix."


def test_imports_compliance():
    """
    Enforces Isort (Import Sorting).
    """
    exit_code = run_command("poetry run isort --check-only src/ tests/")
    assert (
        exit_code == 0
    ), "Import Sorting Checks Failed. Run 'poetry run isort .' to fix."
