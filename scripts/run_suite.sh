#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  Flow Manager — Test Suite Runner (Bash)
#
#  Usage:
#    ./scripts/run_suite.sh                # fast tests only (default)
#    ./scripts/run_suite.sh --fast         # fast tests only (~8s)
#    ./scripts/run_suite.sh --slow         # slow tests only (~40s)
#    ./scripts/run_suite.sh --fast --slow  # all tests (~50s)
#    ./scripts/run_suite.sh --all          # all tests (~50s)
#
#  Fast tests: tests/unit (core logic, quick feedback)
#  Slow tests: tests/unit_slow (threading, timeouts, stress)
# ─────────────────────────────────────────────────────────────
set -euo pipefail

REPORT_FILE="test-report.xml"
RUN_FAST=false
RUN_SLOW=false

# ─── Parse flags (combinable) ───────────────────────────────
if [ $# -eq 0 ]; then
    RUN_FAST=true
else
    for arg in "$@"; do
        case "$arg" in
            --fast) RUN_FAST=true ;;
            --slow) RUN_SLOW=true ;;
            --all)  RUN_FAST=true; RUN_SLOW=true ;;
            *)
                echo "Usage: $0 [--fast] [--slow] [--all]"
                echo "  --fast        Fast tests only (~8s, default)"
                echo "  --slow        Slow tests only (~40s)"
                echo "  --fast --slow All tests (~50s)"
                echo "  --all         All tests (~50s)"
                exit 1
                ;;
        esac
    done
fi

# ─── Build test paths from flags ────────────────────────────
TEST_PATHS=""
LABEL=""
if [ "$RUN_FAST" = true ]; then
    TEST_PATHS="tests/unit"
    LABEL="FAST"
fi
if [ "$RUN_SLOW" = true ]; then
    TEST_PATHS="${TEST_PATHS:+$TEST_PATHS }tests/unit_slow"
    LABEL="${LABEL:+$LABEL+}SLOW"
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  Flow Manager — Test Suite Runner ($LABEL)       "
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ─── Run pytest ─────────────────────────────────────────────
echo "[1/3] Running pytest ($LABEL mode)..."
# shellcheck disable=SC2086
python -m pytest $TEST_PATHS \
    --ignore=tests/unit/knowledge \
    -q --tb=short --no-header \
    --junitxml="$REPORT_FILE" \
    || true

# ─── Check XML ──────────────────────────────────────────────
if [ ! -f "$REPORT_FILE" ]; then
    echo "ERROR: $REPORT_FILE was not generated."
    exit 1
fi

# ─── Parse XML and print summary ────────────────────────────
echo ""
echo "[2/3] Parsing results..."
echo ""

# Use python to parse JUnit XML (portable, no xmllint dependency)
python -c "
import xml.etree.ElementTree as ET
import sys

tree = ET.parse('$REPORT_FILE')
root = tree.getroot()

stats = {}
for tc in root.iter('testcase'):
    classname = tc.get('classname', '')
    parts = classname.split('.')
    if len(parts) >= 3 and parts[1] in ('unit', 'unit_slow'):
        pkg = parts[2]
        if parts[1] == 'unit_slow':
            pkg = f'{pkg} (slow)'
    elif len(parts) >= 2 and parts[1] == 'quality':
        pkg = 'quality'
    else:
        pkg = 'other'

    if pkg not in stats:
        stats[pkg] = {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0}

    stats[pkg]['total'] += 1
    if tc.find('failure') is not None:
        stats[pkg]['failed'] += 1
    elif tc.find('skipped') is not None:
        stats[pkg]['skipped'] += 1
    else:
        stats[pkg]['passed'] += 1

print('Test Summary Report')
print('─' * 60)
print(f'{\"Package\":<20} | {\"Total\":>8} | {\"Pass\":>8} | {\"Fail\":>8} | {\"Skip\":>8}')
print('─' * 60)

g_total = g_pass = g_fail = g_skip = 0
for pkg in sorted(stats.keys()):
    s = stats[pkg]
    g_total += s['total']
    g_pass += s['passed']
    g_fail += s['failed']
    g_skip += s['skipped']
    marker = '  FAIL' if s['failed'] > 0 else ('  SKIP' if s['skipped'] > 0 else '  OK')
    print(f'{pkg:<20} | {s[\"total\"]:>8} | {s[\"passed\"]:>8} | {s[\"failed\"]:>8} | {s[\"skipped\"]:>8}{marker}')

print('─' * 60)
print(f'{\"TOTAL\":<20} | {g_total:>8} | {g_pass:>8} | {g_fail:>8} | {g_skip:>8}')
print()

sys.exit(g_fail)
"

EXIT_CODE=$?

# ─── Cleanup ────────────────────────────────────────────────
echo "[3/3] Done."
# rm -f "$REPORT_FILE"

exit $EXIT_CODE
