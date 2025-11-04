#!/usr/bin/env pwsh
<#
.SYNOPSIS
    自動版本發布腳本 v2.0
    
.DESCRIPTION
    此腳本用於自動化版本發布流程:
    1. 從 version_config.json 讀取配置
    2. 執行完整的 CI 測試
    3. 計算新版本號
    4. 更新所有文件中的版本資訊
    5. 生成 Release Notes
    6. 創建 Git 標籤
    7. 推送到 GitHub 觸發自動發布
    
.PARAMETER BumpType
    版本進版類型: patch (預設), minor, 或 major
    - patch: 1.8.4 -> 1.8.5 (小修復)
    - minor: 1.8.4 -> 1.9.0 (新功能)
    - major: 1.8.4 -> 2.0.0 (重大更新)
    
.PARAMETER SkipTests
    跳過測試直接發布 (不建議)
    
.PARAMETER SkipVersionUpdate
    跳過版本更新 (僅用於測試)
    
.EXAMPLE
    .\scripts\release.ps1
    # 發布 patch 版本 (預設)
    
.EXAMPLE
    .\scripts\release.ps1 -BumpType minor
    # 發布 minor 版本
    
.EXAMPLE
    .\scripts\release.ps1 -BumpType major
    # 發布 major 版本
#>

param(
    [Parameter()]
    [ValidateSet("patch", "minor", "major")]
    [string]$BumpType = "patch",
    
    [Parameter()]
    [switch]$SkipTests,
    
    [Parameter()]
    [switch]$SkipVersionUpdate
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 顏色輸出函數
function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White")
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
║         自動版本發布腳本 v2.0             ║
╚═══════════════════════════════════════════╝

"@ -ForegroundColor Cyan

# 讀取配置
Write-Step "讀取配置"
$configPath = Join-Path $ScriptDir "version_config.json"
if (-not (Test-Path $configPath)) {
    Write-Error "找不到配置文件: $configPath"
    exit 1
}
$config = Get-Content $configPath -Raw | ConvertFrom-Json
Write-Success "配置已載入"

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
Write-Step "計算新版本"
$currentVersion = $config.version.current
Write-ColorOutput "當前版本: $currentVersion" "White"

# 計算新版本
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
Write-ColorOutput "  Publisher: $($config.publisher.name)" "Yellow"
Write-ColorOutput "  Extension ID: $($config.extension.id)" "Yellow"
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
    
    Write-ColorOutput "  ├─ 檢查 Python 版本..." "Gray"
    python --version
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Python 版本檢查失敗"
        exit 1
    }
    
    Write-ColorOutput "  ├─ 檢查包導入..." "Gray"
    python -c "import fubon_mcp; print('版本:', fubon_mcp.__version__)"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "包導入檢查失敗"
        exit 1
    }
    
    Write-ColorOutput "  ├─ 檢查 Black 格式化..." "Gray"
    python -m black --check --diff fubon_mcp tests
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Black 格式化檢查失敗"
        exit 1
    }
    
    Write-ColorOutput "  ├─ 檢查 isort 導入排序..." "Gray"
    python -m isort --check-only --diff fubon_mcp tests --skip fubon_mcp/_version.py
    if ($LASTEXITCODE -ne 0) {
        Write-Error "isort 導入排序檢查失敗"
        exit 1
    }
    
    Write-ColorOutput "  ├─ 檢查 flake8 代碼品質..." "Gray"
    python -m flake8 fubon_mcp tests
    if ($LASTEXITCODE -ne 0) {
        Write-Error "flake8 代碼品質檢查失敗"
        exit 1
    }
    
    Write-ColorOutput "  ├─ 檢查 mypy 類型檢查..." "Gray"
    python -m mypy fubon_mcp
    if ($LASTEXITCODE -ne 0) {
        Write-Error "mypy 類型檢查失敗"
        exit 1
    }
    
    Write-ColorOutput "  └─ 運行測試套件..." "Gray"
    python -m pytest --tb=short
    if ($LASTEXITCODE -ne 0) {
        Write-Error "測試套件運行失敗"
        exit 1
    }
    
    Write-Success "所有測試通過"
} else {
    Write-Warning "已跳過測試(不建議)"
}

# 更新版本號
if (-not $SkipVersionUpdate) {
    Write-Step "更新版本資訊"
    & "$ScriptDir\update_version.ps1" -Version $newVersion -ConfigPath $configPath
    if ($LASTEXITCODE -ne 0) {
        Write-Error "版本更新失敗"
        exit 1
    }
    Write-Success "版本資訊已更新"
    
    # 生成 Release Notes
    Write-Step "生成 Release Notes"
    & "$ScriptDir\generate_release_notes.ps1" -Version $newVersion -ConfigPath $configPath
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Release Notes 生成失敗"
        exit 1
    }
    Write-Success "Release Notes 已生成"
    
    # 提交版本更新
    Write-Step "提交版本更新"
    git add .
    git commit -m "chore: bump version to $newVersion"
    git push origin $currentBranch
    Write-Success "版本更新已提交"
}

# 構建測試
Write-Step "測試構建"
python -m build
if ($LASTEXITCODE -ne 0) {
    Write-Error "構建失敗"
    exit 1
}
Write-Success "構建測試通過"

# 檢查 twine 驗證
Write-Step "檢查 twine 包驗證"
if (Test-Path "dist") {
    python -m twine check dist/*
    if ($LASTEXITCODE -ne 0) {
        Write-Error "twine 包驗證失敗"
        exit 1
    }
    Write-Success "twine 包驗證通過"
} else {
    Write-Warning "跳過 twine 檢查 - 沒有 dist 目錄"
}

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
Write-ColorOutput "  GitHub Actions: $($config.urls.repository)/actions" "Blue"
Write-ColorOutput "  PyPI: $($config.urls.pypi)" "Blue"
Write-ColorOutput "  Marketplace: $($config.urls.marketplace)" "Blue"
Write-Host ""

Write-ColorOutput "版本: $newVersion 預計將在 5-10 分鐘內發布完成" "Yellow"
Write-Host ""
