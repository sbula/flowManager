$ErrorActionPreference = "Continue"
$ReportFile = "test-report.xml"

Write-Host "Running Virtual Test Suite (Unit + Quality + Integration)..." -ForegroundColor Cyan
Write-Host "Packages: flow" -ForegroundColor Gray
Write-Host "--------------" -ForegroundColor Gray

# 1. Run Tests (Capture Output)
Write-Host "Executing pytest..." -ForegroundColor Yellow
cmd /c "poetry run pytest -v --junitxml=$ReportFile"

if ($LASTEXITCODE -eq 0) {
    Write-Host "Pytest finished successfully." -ForegroundColor Green
} else {
    Write-Host "Pytest finished with errors (this is expected if tests failed)." -ForegroundColor Yellow
}

# 2. Check XML
if (-not (Test-Path $ReportFile)) {
    Write-Host "Error: $ReportFile was not generated." -ForegroundColor Red
    exit 1
}

# 3. Parse XML
try {
    [xml]$xml = Get-Content $ReportFile
} catch {
    Write-Host "Error parsing XML: $_" -ForegroundColor Red
    exit 1
}

$stats = @{}
$testcases = $xml.testsuites.testsuite.testcase

if (-not $testcases) {
    # Sometimes structure varies (testsuites -> testsuite -> testcase OR testsuites -> testcase)
    # Or multiple testsuites
    $testcases = $xml.SelectNodes("//testcase")
}

Write-Host "Found $(@($testcases).Count) test cases." -ForegroundColor Cyan

foreach ($testcase in $testcases) {
    $classname = $testcase.classname
    $parts = $classname -split '\.'
    
    # Heuristic
    if ($parts.Count -ge 3 -and $parts[1] -eq "unit") {
        $pkg = $parts[2]
    } elseif ($parts.Count -ge 2 -and $parts[1] -eq "quality") {
        $pkg = "quality"
    } else {
        $pkg = "other"
    }
    
    if (-not $stats.ContainsKey($pkg)) {
        $stats[$pkg] = @{ Total = 0; Passed = 0; Failed = 0; Skipped = 0 }
    }
    
    $stats[$pkg].Total++
    
    if ($testcase.failure) {
        $stats[$pkg].Failed++
    } elseif ($testcase.skipped) {
        $stats[$pkg].Skipped++
    } else {
        $stats[$pkg].Passed++
    }
}

# 4. Table
Write-Host ""
Write-Host "Test Summary Report" -ForegroundColor Yellow
Write-Host "--------------------------------------------------------"
Write-Host ("{0,-15} | {1,8} | {2,8} | {3,8} | {4,8}" -f "Package", "Total", "Pass", "Fail", "Skip")
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
    
    Write-Host ("{0,-15} | {1,8} | {2,8} | {3,8} | {4,8}" -f $pkg, $s.Total, $s.Passed, $s.Failed, $s.Skipped) -ForegroundColor $color
}

Write-Host "--------------------------------------------------------"
Write-Host ("{0,-15} | {1,8} | {2,8} | {3,8} | {4,8}" -f "TOTAL", $GrandTotal, $GrandPass, $GrandFail, $GrandSkip)

# 5. Cleanup
# Remove-Item $ReportFile -Force -ErrorAction SilentlyContinue

exit $GrandFail
