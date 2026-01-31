#!/bin/bash
set -e

SCOPE=$1
if [ -z "$SCOPE" ]; then
    echo "Usage: $0 <scope>"
    exit 1
fi

PROJECT_ROOT=$(git rev-parse --show-toplevel)
SERVICES_DIR="$PROJECT_ROOT/services"

failed=0

for service in "$SERVICES_DIR"/*; do
    if [ -d "$service" ] && [ -f "$service/test.sh" ]; then
        service_name=$(basename "$service")
        echo ">>> Testing $service_name ($SCOPE)..."
        
        if ! bash "$service/test.sh" "$SCOPE"; then
            echo "!! FAILURE in $service_name"
            failed=1
        fi
    fi
done

if [ $failed -ne 0 ]; then
    echo "!! Global Test Failure."
    exit 1
else
    echo ">> Global Test Success."
    exit 0
fi
