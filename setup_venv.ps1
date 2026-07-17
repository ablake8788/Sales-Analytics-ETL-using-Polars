<#
.SYNOPSIS
    Creates the project's virtual environment and installs dependencies
    from requirements.txt (polars, pyodbc, pytest).
.EXAMPLE
    .\setup_venv.ps1
#>

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (!(Test-Path ".\.venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

Write-Host "Installing dependencies from requirements.txt..."
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host "`nDone. Either call scripts here directly, or activate with:"
Write-Host "  .\.venv\Scripts\activate"
