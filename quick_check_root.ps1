#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Quick Check - Fast pre-commit validation

.DESCRIPTION
    Quick validation script for checking code quality before commits.
    This is a convenience wrapper that calls scripts/quick_check.ps1

.EXAMPLE
    .\quick_check.ps1
    Run quick validation checks
#>

& "$PSScriptRoot\scripts\quick_check.ps1" @args
exit $LASTEXITCODE
