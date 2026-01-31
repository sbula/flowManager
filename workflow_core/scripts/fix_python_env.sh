#!/bin/bash
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
