<#
.SYNOPSIS
    Runs the unit test suite (tests/test_fifo_matching.py) — pure Polars,
    no SQL Server connection required.
.EXAMPLE
    .\run_tests.ps1
#>

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

& .\.venv\Scripts\python.exe -m pytest tests\ -v
exit $LASTEXITCODE
