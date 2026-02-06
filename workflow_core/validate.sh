#!/bin/bash

# Copyright 2026 Steve Bula @ pitBula
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# validate.sh - Common Validation Wrapper
# Usage: ./validate.sh <service_path> --check <type>

set -e
export PATH="$HOME/.local/bin:$PATH"

usage() {
    echo "Usage: $0 <service_path> --check <lint|complexity|coverage|unit|integration|e2e>"
    exit 1
}

if [ "$#" -lt 3 ]; then
    usage
fi

SERVICE_PATH="$1"
shift
if [ "$1" != "--check" ]; then
    usage
fi
CHECK_TYPE="$2"

if [ ! -d "$SERVICE_PATH" ]; then
    echo "!! Error: Service directory '$SERVICE_PATH' not found."
    exit 1
fi

# Detect Standard Interface
TEST_SCRIPT="$SERVICE_PATH/test.sh"

if [ -f "$TEST_SCRIPT" ]; then
    echo ">> [validate.sh] Delegating to Standard Interface in $SERVICE_PATH..."
    
    # Change context to Service Directory
    cd "$SERVICE_PATH"

    if [ "$CHECK_TYPE" == "complexity" ]; then
        echo ">> [validate.sh] Running Complexity Analysis (Lizard)..."
        
        # Unified Multi-Language Scan (Python, Kotlin, etc.)
        # Thresholds: CCN > 10, Length > 1000
        if command -v poetry &> /dev/null && [ -f "pyproject.toml" ]; then
             poetry run lizard . -C 10 -L 1000 -w
        else
             # Fallback if not poetry project (or lizard installed globally)
             lizard . -C 10 -L 1000 -w
        fi
        
        # Always return 0 for reporting, unless lizard fails hard?
        # -w causes exit 1 on violations.
        # User wants "standard tests". Exit 1 is correct for Gates.
        
        exit $?
        
    else
        # Standard Delegation to test.sh (already inside service dir)
        # We call it as ./test.sh
        bash "./test.sh" "$CHECK_TYPE"
    fi
else
    # Fallback to language-specific standard commands?
    # User said "must be language specific but... calling specific tests".
    # User also said "They must be language specific but this can be done by a common shell script"
    # Which implies if test.sh is missing, we might assume defaults?
    # But enforcing test.sh is cleaner.
    
    echo "!! Error: Standard Interface 'test.sh' not found in $SERVICE_PATH."
    echo "!! Compliance Requirement: Every service must implement 'test.sh' to handle:"
    echo "!!   lint, complexity, unit, etc."
    exit 1
fi
