<#
.SYNOPSIS
    Builds a standalone Windows executable (dist\SalesAnalyticsETL.exe)
    from main.py using PyInstaller. Requires pyinstaller in .venv
    (pip install pyinstaller).
.EXAMPLE
    .\run_build_exe.ps1
#>

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

& .\.venv\Scripts\python.exe -m PyInstaller `
    --name SalesAnalyticsETL `
    --onefile `
    --console `
    --add-data "sql;sql" `
    --add-data "sales_analytics_etl.ini.template;." `
    main.py

exit $LASTEXITCODE
