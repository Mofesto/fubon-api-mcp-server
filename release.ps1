#!/usr/bin/env pwsh
<#
.SYNOPSIS
    自動版本發布腳本
    
.DESCRIPTION
    此腳本用於自動化版本發布流程:
    1. 執行完整的 CI 測試
    2. 計算新版本號
    3. 創建 Git 標籤
    4. 推送到 GitHub 觸發自動發布
    
.PARAMETER BumpType
    版本進版類型: patch (預設), minor, 或 major
    - patch: 1.8.0 -> 1.8.1 (小修復)
    - minor: 1.8.0 -> 1.9.0 (新功能)
    - major: 1.8.0 -> 2.0.0 (重大更新)
    
.PARAMETER SkipTests
    跳過測試直接發布 (不建議)
    
.EXAMPLE
    .\release.ps1
    # 發布 patch 版本 (預設)
    
.EXAMPLE
    .\release.ps1 -BumpType minor
    # 發布 minor 版本
    
.EXAMPLE
    .\release.ps1 -BumpType major
    # 發布 major 版本
#>

param(
    [Parameter()]
    [ValidateSet("patch", "minor", "major")]
    [string]$BumpType = "patch",
    
    [Parameter()]
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"

# 顏色輸出函數
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

function Write-Step {
    param([string]$Message)
    Write-ColorOutput "`n==> $Message" "Cyan"
}

function Write-Success {
    param([string]$Message)
    Write-ColorOutput "✓ $Message" "Green"
}

function Write-Error {
    param([string]$Message)
    Write-ColorOutput "✗ $Message" "Red"
}

function Write-Warning {
    param([string]$Message)
    Write-ColorOutput "⚠ $Message" "Yellow"
}

# 顯示標題
Write-Host @"

╔═══════════════════════════════════════════╗
║   Fubon API MCP Server - Auto Release    ║
║         自動版本發布腳本 v1.0             ║
╚═══════════════════════════════════════════╝

"@ -ForegroundColor Cyan

# 檢查 Git 狀態
Write-Step "檢查 Git 狀態"
$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Error "工作目錄有未提交的變更，請先提交或暫存"
    Write-Host $gitStatus
    exit 1
}
Write-Success "工作目錄乾淨"

# 確保在 main 分支
$currentBranch = git branch --show-current
if ($currentBranch -ne "main") {
    Write-Warning "當前分支: $currentBranch"
    $continue = Read-Host "建議在 main 分支發布，是否繼續? (y/N)"
    if ($continue -ne "y" -and $continue -ne "Y") {
        exit 0
    }
}

# 拉取最新代碼
Write-Step "拉取最新代碼"
git pull origin $currentBranch
Write-Success "代碼已更新"

# 獲取當前版本
Write-Step "獲取當前版本"
$currentVersion = python -c "import setuptools_scm; print(setuptools_scm.get_version())" | Select-String -Pattern '^\d+\.\d+\.\d+' | ForEach-Object { $_.Matches.Value }
Write-ColorOutput "當前版本: $currentVersion" "White"

# 計算新版本
Write-Step "計算新版本"
$versionParts = $currentVersion -split '\.'
$major = [int]$versionParts[0]
$minor = [int]$versionParts[1]
$patch = [int]$versionParts[2]

switch ($BumpType) {
    "major" {
        $newVersion = "$($major + 1).0.0"
    }
    "minor" {
        $newVersion = "$major.$($minor + 1).0"
    }
    "patch" {
        $newVersion = "$major.$minor.$($patch + 1)"
    }
}

Write-ColorOutput "新版本: $newVersion ($BumpType)" "Yellow"

# 確認發布
Write-Host ""
Write-ColorOutput "========================================" "Yellow"
Write-ColorOutput "  準備發布版本: v$newVersion" "Yellow"
Write-ColorOutput "  版本類型: $BumpType" "Yellow"
Write-ColorOutput "========================================" "Yellow"
Write-Host ""

$confirm = Read-Host "確認發布? (y/N)"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Warning "發布已取消"
    exit 0
}

# 執行測試
if (-not $SkipTests) {
    Write-Step "執行完整測試"
    
    Write-ColorOutput "  ├─ 檢查語法..." "Gray"
    flake8 fubon_mcp tests --count --select=E9,F63,F7,F82 --show-source --statistics
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Flake8 檢查失敗"
        exit 1
    }
    
    Write-ColorOutput "  ├─ 檢查格式..." "Gray"
    black --check fubon_mcp tests --exclude fubon_mcp/_version.py --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Black 格式檢查有警告(已忽略)"
    }
    
    Write-ColorOutput "  ├─ 檢查導入..." "Gray"
    isort --check-only fubon_mcp tests --skip fubon_mcp/_version.py --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "isort 檢查有警告(已忽略)"
    }
    
    Write-ColorOutput "  ├─ 類型檢查..." "Gray"
    mypy fubon_mcp --no-error-summary 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "mypy 檢查有警告(已忽略)"
    }
    
    Write-ColorOutput "  └─ 單元測試..." "Gray"
    pytest --cov=fubon_mcp --cov-fail-under=10 -q --tb=no
    if ($LASTEXITCODE -ne 0) {
        Write-Error "測試失敗，請修復後再發布"
        exit 1
    }
    
    Write-Success "所有測試通過"
} else {
    Write-Warning "已跳過測試(不建議)"
}

# 構建測試
Write-Step "測試構建"
python -m build --outdir dist-test 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "構建失敗"
    exit 1
}
Remove-Item -Recurse -Force dist-test -ErrorAction SilentlyContinue
Write-Success "構建測試通過"

# 創建標籤
Write-Step "創建並推送標籤"
$tag = "v$newVersion"

git tag $tag
if ($LASTEXITCODE -ne 0) {
    Write-Error "創建標籤失敗"
    exit 1
}
Write-Success "標籤已創建: $tag"

Write-ColorOutput "正在推送標籤到 GitHub..." "Gray"
git push origin $tag
if ($LASTEXITCODE -ne 0) {
    Write-Error "推送標籤失敗"
    git tag -d $tag
    exit 1
}
Write-Success "標籤已推送"

# 顯示後續步驟
Write-Host ""
Write-ColorOutput "╔═══════════════════════════════════════════╗" "Green"
Write-ColorOutput "║          🎉 發布流程已啟動 🎉            ║" "Green"
Write-ColorOutput "╚═══════════════════════════════════════════╝" "Green"
Write-Host ""

Write-ColorOutput "📋 後續步驟:" "Cyan"
Write-ColorOutput "  1. GitHub Actions 將自動執行 CI 測試" "White"
Write-ColorOutput "  2. 測試通過後自動發布到 PyPI" "White"
Write-ColorOutput "  3. 自動發布到 VS Code Marketplace" "White"
Write-ColorOutput "  4. 自動創建 GitHub Release" "White"
Write-Host ""

Write-ColorOutput "🔗 監控進度:" "Cyan"
Write-ColorOutput "  GitHub Actions: https://github.com/Mofesto/fubon-api-mcp-server/actions" "Blue"
Write-ColorOutput "  PyPI: https://pypi.org/project/fubon-api-mcp-server/" "Blue"
Write-Host ""

Write-ColorOutput "版本: $newVersion 預計將在 5-10 分鐘內發布完成" "Yellow"
Write-Host ""
