<#
.SYNOPSIS
    Runs the full cycle end-to-end: loads Schwab trade history into
    dbo.SchwabTransactions (schwab_market_data\transactions_main.py), then
    runs the Sales Analytics ETL against it with --write-back.

    Must be run from an interactive PowerShell session — step 1 may prompt
    for an OAuth browser login if the refresh token has expired.
.EXAMPLE
    .\run_full_cycle.ps1 -Start 2026-01-01 -End 2026-07-01
.EXAMPLE
    .\run_full_cycle.ps1 -Start 2026-01-01 -End 2026-07-01 -Symbols AAPL,MSFT -Period year
#>

param(
    [Parameter(Mandatory = $true)] [string] $Start,
    [Parameter(Mandatory = $true)] [string] $End,
    [string] $Symbols,
    [ValidateSet("month", "year")] [string] $Period = "month"
)

$ErrorActionPreference = "Stop"
$etlDir = $PSScriptRoot
$loaderDir = Join-Path (Split-Path $etlDir -Parent) "schwab_market_data"

if (!(Test-Path $loaderDir)) {
    throw "Could not find sibling project at $loaderDir"
}

Write-Host "=== Step 1/2: Loading Schwab transactions ($Start -> $End) ===" -ForegroundColor Cyan
Push-Location $loaderDir
try {
    & .\.venv\Scripts\python.exe transactions_main.py --start $Start --end $End
    if ($LASTEXITCODE -ne 0) { throw "transactions_main.py failed (exit code $LASTEXITCODE)" }
} finally {
    Pop-Location
}

Write-Host "`n=== Step 2/2: Running Sales Analytics ETL ===" -ForegroundColor Cyan
Push-Location $etlDir
try {
    $pyArgs = @("main.py", "--start", $Start, "--end", $End, "--period", $Period, "--write-back")
    if ($Symbols) { $pyArgs += @("--symbols", $Symbols) }
    & .\.venv\Scripts\python.exe @pyArgs
    if ($LASTEXITCODE -ne 0) { throw "main.py failed (exit code $LASTEXITCODE)" }
} finally {
    Pop-Location
}

Write-Host "`nFull cycle complete." -ForegroundColor Green
