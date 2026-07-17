<#
.SYNOPSIS
    Byte-compiles all project source files (main.py, core, db, etl, cli,
    tests) to catch syntax errors without running anything — no SQL Server
    connection required.
.EXAMPLE
    .\run_compile.ps1
#>

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

& .\.venv\Scripts\python.exe -m compileall -q main.py core db etl cli tests
exit $LASTEXITCODE
