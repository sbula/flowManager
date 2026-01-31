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

# Security Audit Script
# Wraps Maven Dependency Check and Python pip-audit

set -e

echo ">> [SECURITY] Starting Security Audit..."

# Java Services
echo ">> [SECURITY] Scanning Java Services (Market Price Service)..."
cd services/market-price-service
# SKIPPED: NVD Download too slow without API Key
# mvn org.owasp:dependency-check-maven:check -Dformat=MARKDOWN
echo ">> [INFO] NVD Download skipped. Dumping dependency tree for manual review..."
mvn dependency:tree > dependency_tree.txt
cd ../..

# Python Services
echo ">> [SECURITY] Scanning Python Services (Market Price Adapter YFinance)..."
if [ -d "services/market-price-adapter-yfinance" ]; then
    cd services/market-price-adapter-yfinance
    if command -v pip-audit &> /dev/null; then
        pip-audit -r requirements.txt --format markdown > dependency-check-report.md || echo ">> [WARN] pip-audit failed/found issues"
    else
        echo ">> [WARN] pip-audit not found. Skipping Python scan."
    fi
    cd ../..
else
    echo ">> [WARN] Python service directory not found."
fi

# Secret Scan
echo ">> [SECURITY] Scanning for Secrets (Keys, Tokens)..."
grep -r "BEGIN RSA PRIVATE KEY" services/ || echo ">> [INFO] No Private Keys found."
grep -r "AWS_ACCESS_KEY_ID" services/ || echo ">> [INFO] No AWS Keys found."
grep -r "api_key" services/ | grep -v "example" | grep -v "test" || echo ">> [INFO] No API Keys found (excluding tests)."

echo ">> [SECURITY] Audit Complete."
