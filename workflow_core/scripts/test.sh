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
