#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Quick Check Wrapper - Execute from anywhere

.DESCRIPTION
    This wrapper script ensures quick_check.ps1 runs from the correct location
    regardless of where it is invoked from.

.EXAMPLE
    .\run_quick_check.ps1
    Run quick validation checks from any directory
#>

# Save current location
$originalLocation = Get-Location

try {
    # Get the directory where this script is located
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    
    # Navigate to project root (parent of scripts directory)
    if (Split-Path -Leaf $scriptDir) -eq "scripts") {
        $projectRoot = Split-Path -Parent $scriptDir
    } else {
        $projectRoot = $scriptDir
    }
    
    # Verify we're in the right place
    if (-not (Test-Path (Join-Path $projectRoot "fubon_mcp"))) {
        Write-Error "Cannot find project root. Expected fubon_mcp directory."
        exit 1
    }
    
    # Change to project root and execute quick_check.ps1
    Set-Location $projectRoot
    
    # Execute the actual check script
    $checkScript = Join-Path $projectRoot "scripts" "quick_check.ps1"
    if (Test-Path $checkScript) {
        & $checkScript
        $exitCode = $LASTEXITCODE
    } else {
        Write-Error "Cannot find quick_check.ps1 at: $checkScript"
        exit 1
    }
} finally {
    # Always return to original location
    Set-Location $originalLocation
}

exit $exitCode
