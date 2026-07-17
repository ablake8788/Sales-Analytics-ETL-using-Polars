<#
.SYNOPSIS
    Runs the Sales Analytics ETL — FIFO realized gain/loss over
    dbo.SchwabTransactions, computed with Polars.
.EXAMPLE
    .\run_etl.ps1 -Start 2026-01-01 -End 2026-07-01
.EXAMPLE
    .\run_etl.ps1 -Start 2026-01-01 -End 2026-07-01 -Symbols AAPL,MSFT -Period year -WriteBack -WriteMode replace
#>

param(
    [Parameter(Mandatory = $true)] [string] $Start,
    [Parameter(Mandatory = $true)] [string] $End,
    [string] $Symbols,
    [ValidateSet("month", "year")] [string] $Period = "month",
    [switch] $WriteBack,
    [ValidateSet("append", "replace")] [string] $WriteMode = "append",
    [string] $LogDir
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$pyArgs = @("main.py", "--start", $Start, "--end", $End, "--period", $Period, "--write-mode", $WriteMode)
if ($Symbols) { $pyArgs += @("--symbols", $Symbols) }
if ($WriteBack) { $pyArgs += "--write-back" }
if ($LogDir) { $pyArgs += @("--log-dir", $LogDir) }

& .\.venv\Scripts\python.exe @pyArgs
exit $LASTEXITCODE
