<#
.SYNOPSIS
    Quick CI Check - Fast pre-commit validation

.DESCRIPTION
    This is a lightweight PowerShell script that runs the most important checks quickly.
    Use this for rapid feedback before committing.

.EXAMPLE
    .\quick_check.ps1
    Run quick validation checks

.NOTES
    For full CI validation, use: .\check_and_fix.ps1
#>

# Get script directory and change to project root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = if (Test-Path (Join-Path $scriptDir "scripts")) {
    # Running from scripts directory
    $scriptDir
} elseif (Test-Path (Join-Path $scriptDir ".." "fubon_api_mcp_server")) {
    # Running from scripts subdirectory
    Split-Path -Parent $scriptDir
} else {
    # Assume current directory is project root
    Get-Location
}

# Change to project root
Push-Location $projectRoot

# Ensure we can find the source directories
if (-not (Test-Path "fubon_api_mcp_server") -or -not (Test-Path "tests")) {
    Write-Host "Error: Cannot find fubon_api_mcp_server or tests directory" -ForegroundColor Red
    Write-Host "Current location: $(Get-Location)" -ForegroundColor Yellow
    Write-Host "Please run this script from the project root or scripts directory" -ForegroundColor Yellow
    Pop-Location
    exit 1
}

# Color output functions
function Write-CheckResult {
    param(
        [string]$Name,
        [bool]$Success
    )
    
    $status = if ($Success) { 
        Write-Host "✓" -ForegroundColor Green -NoNewline
    } else { 
        Write-Host "✗" -ForegroundColor Red -NoNewline
    }
    Write-Host ""
}

function Invoke-QuickCheck {
    param(
        [string]$Name,
        [string]$Command,
        [string[]]$Arguments,
        [string]$FixCommand = $null,
        [string[]]$FixArguments = $null
    )
    
    Write-Host "Checking $Name... " -NoNewline
    
    $result = & $Command $Arguments 2>&1
    $success = $LASTEXITCODE -eq 0
    
    if ($success) {
        Write-Host "✓" -ForegroundColor Green
        return $true
    }
    
    Write-Host "✗" -ForegroundColor Red
    
    if ($FixCommand) {
        Write-Host "  Fixing... " -ForegroundColor Yellow -NoNewline
        $fixResult = & $FixCommand $FixArguments 2>&1
        $fixSuccess = $LASTEXITCODE -eq 0
        
        if ($fixSuccess) {
            Write-Host "✓ Fixed" -ForegroundColor Green
            return $true
        }
        Write-Host "✗ Failed to fix" -ForegroundColor Red
    }
    
    return $false
}

# Main execution
Write-Host "Quick CI Check - Fast validation" -ForegroundColor Cyan
Write-Host ""

$results = @()

# Black formatting (auto-fix)
$results += Invoke-QuickCheck `
    -Name "Code formatting (black)" `
    -Command "black" `
    -Arguments @("--check", "--quiet", "fubon_api_mcp_server", "tests", "--exclude", "_version.py") `
    -FixCommand "black" `
    -FixArguments @("--quiet", "fubon_api_mcp_server", "tests", "--exclude", "_version.py")

# Import sorting (auto-fix)
$results += Invoke-QuickCheck `
    -Name "Import sorting (isort)" `
    -Command "isort" `
    -Arguments @("--check-only", "fubon_api_mcp_server", "tests", "--skip", "_version.py") `
    -FixCommand "isort" `
    -FixArguments @("fubon_api_mcp_server", "tests", "--skip", "_version.py")

# Flake8 critical errors (no auto-fix)
$results += Invoke-QuickCheck `
    -Name "Critical code errors (flake8)" `
    -Command "flake8" `
    -Arguments @("fubon_api_mcp_server", "tests", "--select=E9,F63,F7,F82", "--quiet")

# Quick test run (most important tests only)
Write-Host "Running quick tests... " -NoNewline

try {
    $testOutput = & pytest -q --tb=no `
        tests/test_config.py `
        tests/test_models.py `
        tests/test_package.py 2>&1
    
    $testSuccess = $LASTEXITCODE -eq 0
    
    if ($testSuccess) {
        Write-Host "✓" -ForegroundColor Green
    } else {
        Write-Host "✗" -ForegroundColor Red
        if ($testOutput) {
            Write-Host "  Output:" -ForegroundColor Gray
            $testOutput | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
        }
        Write-Host "  Run 'pytest -v' for details" -ForegroundColor Yellow
    }
    
    $results += $testSuccess
} catch {
    Write-Host "✗" -ForegroundColor Red
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Red
    $results += $false
}

# Summary
Write-Host ""

if ($results -notcontains $false) {
    Write-Host "✓ All quick checks passed!" -ForegroundColor Green
    Write-Host "Note: Run '.\check_and_fix.ps1' for full CI validation" -ForegroundColor Yellow
    Pop-Location
    exit 0
} else {
    Write-Host "✗ Some checks failed" -ForegroundColor Red
    Write-Host "Run '.\check_and_fix.ps1 -Fix -Verbose' for details" -ForegroundColor Yellow
    Pop-Location
    exit 1
}
