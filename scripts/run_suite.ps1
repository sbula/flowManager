# ─── Parameters ────────────────────────────────────────────────
# Usage: .\scripts\run_suite.ps1               # fast (default)
#        .\scripts\run_suite.ps1 -Fast         # fast only (~8s)
#        .\scripts\run_suite.ps1 -Slow         # slow only (~40s)
#        .\scripts\run_suite.ps1 -Fast -Slow   # all tests (~50s)
param(
    [switch]$Fast,
    [switch]$Slow
)

$ErrorActionPreference = "Continue"
$ReportFile = "test-report.xml"

# Default to -Fast when neither flag is specified
if (-not $Fast -and -not $Slow) { $Fast = $true }

# Build test paths and label from flags
$TestPaths = @()
$Labels = @()
if ($Fast) { $TestPaths += "tests/unit"; $Labels += "FAST" }
if ($Slow) { $TestPaths += "tests/unit_slow"; $Labels += "SLOW" }
$Label = $Labels -join "+"

Write-Host ""
Write-Host "Running Virtual Test Suite ($Label)..." -ForegroundColor Cyan
Write-Host "Packages: flow" -ForegroundColor Gray
Write-Host "--------------" -ForegroundColor Gray

# 1. Run Tests
Write-Host "Executing pytest ($Label mode)..." -ForegroundColor Yellow
$pytestArgs = $TestPaths + @("--ignore=tests/unit/knowledge", "-q", "--tb=short", "--no-header", "--junitxml=$ReportFile")
& python -m pytest @pytestArgs
$pytestExit = $LASTEXITCODE

if ($pytestExit -eq 0) {
    Write-Host "Pytest finished successfully." -ForegroundColor Green
}
else {
    Write-Host "Pytest finished with errors (this is expected if tests failed)." -ForegroundColor Yellow
}

# 2. Check XML
if (-not (Test-Path $ReportFile)) {
    Write-Host "Error: $ReportFile was not generated." -ForegroundColor Red
    exit 1
}

# 3. Parse XML
try {
    [xml]$xml = Get-Content $ReportFile -Raw
}
catch {
    Write-Host "Error parsing XML: $_" -ForegroundColor Red
    exit 1
}

$stats = @{}
$testcases = $xml.testsuites.testsuite.testcase

if (-not $testcases) {
    $testcases = $xml.SelectNodes("//testcase")
}

if (-not $testcases -or @($testcases).Count -eq 0) {
    Write-Host "Warning: No test cases found in report." -ForegroundColor Yellow
    exit $pytestExit
}

Write-Host "Found $(@($testcases).Count) test cases." -ForegroundColor Cyan

foreach ($testcase in $testcases) {
    $classname = $testcase.classname
    $parts = $classname -split '\.'

    # Map classname to package: tests.unit.<pkg>.* or tests.unit_slow.<pkg>.*
    if ($parts.Count -ge 3 -and $parts[1] -eq "unit") {
        $pkg = $parts[2]
    }
    elseif ($parts.Count -ge 3 -and $parts[1] -eq "unit_slow") {
        $pkg = "$($parts[2]) (slow)"
    }
    elseif ($parts.Count -ge 2 -and $parts[1] -eq "quality") {
        $pkg = "quality"
    }
    else {
        $pkg = "other"
    }

    if (-not $stats.ContainsKey($pkg)) {
        $stats[$pkg] = @{ Total = 0; Passed = 0; Failed = 0; Skipped = 0 }
    }

    $stats[$pkg].Total++

    if ($testcase.failure) {
        $stats[$pkg].Failed++
    }
    elseif ($testcase.skipped) {
        $stats[$pkg].Skipped++
    }
    else {
        $stats[$pkg].Passed++
    }
}

# 4. Summary Table
Write-Host ""
Write-Host "Test Summary Report ($Label)" -ForegroundColor Yellow
Write-Host "--------------------------------------------------------"
Write-Host ("{0,-20} | {1,8} | {2,8} | {3,8} | {4,8}" -f "Package", "Total", "Pass", "Fail", "Skip")
Write-Host "--------------------------------------------------------"

$GrandTotal = 0
$GrandPass = 0
$GrandFail = 0
$GrandSkip = 0

foreach ($pkg in ($stats.Keys | Sort-Object)) {
    $s = $stats[$pkg]
    $GrandTotal += $s.Total
    $GrandPass += $s.Passed
    $GrandFail += $s.Failed
    $GrandSkip += $s.Skipped

    $color = "Green"
    if ($s.Failed -gt 0) { $color = "Red" }
    elseif ($s.Skipped -gt 0) { $color = "Yellow" }

    Write-Host ("{0,-20} | {1,8} | {2,8} | {3,8} | {4,8}" -f $pkg, $s.Total, $s.Passed, $s.Failed, $s.Skipped) -ForegroundColor $color
}

Write-Host "--------------------------------------------------------"
Write-Host ("{0,-20} | {1,8} | {2,8} | {3,8} | {4,8}" -f "TOTAL", $GrandTotal, $GrandPass, $GrandFail, $GrandSkip)

# 5. Cleanup
# Remove-Item $ReportFile -Force -ErrorAction SilentlyContinue

exit $GrandFail
