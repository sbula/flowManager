#!/bin/bash
# Standard Test Interface for Workflow Core
# Usage: ./test.sh <check_type>

CHECK_TYPE="$1"

if [ "$CHECK_TYPE" == "lint" ]; then
    echo ">> [workflow_core] Running Configuration Linter..."
    python3 workflow_core/config_validator.py
    # Also lint python code? Maybe later.
    exit $?
elif [ "$CHECK_TYPE" == "unit" ]; then
    echo ">> [workflow_core] Running Unit Tests..."
    # python3 -m pytest tests/ # No tests yet
    echo ">> No unit tests defined yet."
    exit 0
else
    echo ">> Unknown check type: $CHECK_TYPE"
    exit 1
fi
