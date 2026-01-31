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
set -e

# List of directories containing pyproject.toml
DIRS=(
    "."
    "shared/schemas"
    "services/api-gateway"
    "services/asset-management-service"
    "services/backtesting-service"
    "services/execution-service"
    "services/instrument-analysis-service"
    "services/market-price-service"
    "services/news-intelligence-service"
    "services/portfolio-service"
    "services/position-sizing-service"
    "services/risk-management-service"
    "services/tenant-configuration-service"
    "services/trading-signal-service"
    "services/user-management-service"
    "services/web-ui"
)

echo "=== Enforcing Python 3.13 Environment ==="

for d in "${DIRS[@]}"; do
    if [ -d "$d" ]; then
        echo ">> Processing: $d"
        cd "$d"
        
        if [ -f "pyproject.toml" ]; then
             # Check if poetry env exists, maybe info?
             # Just force use
             poetry env use 3.13
        else
             echo "!! No pyproject.toml in $d"
        fi
        
        # Return to root
        cd - > /dev/null
    else
        echo "!! Directory not found: $d"
    fi
done

echo "=== Done ==="
