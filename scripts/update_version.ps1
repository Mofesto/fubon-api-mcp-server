#!/usr/bin/env pwsh
<#
.SYNOPSIS
    統一更新所有文件中的版本號
    
.DESCRIPTION
    從 version_config.json 讀取版本資訊，並更新所有相關文件:
    - README.md
    - INSTALL.md
    - CHANGELOG.md
    - vscode-extension/README.md
    - vscode-extension/package.json
    - vscode-extension/CHANGELOG.md
    - GITHUB_PUBLISH_GUIDE.md
    
.PARAMETER Version
    新版本號 (如: 1.8.5)，如果不指定則使用 version_config.json 中的版本
    
.PARAMETER ConfigPath
    配置文件路徑，預設為 scripts/version_config.json
    
.EXAMPLE
    .\scripts\update_version.ps1
    # 使用配置文件中的版本更新所有文件
    
.EXAMPLE
    .\scripts\update_version.ps1 -Version 1.8.5
    # 更新到指定版本
#>

param(
    [Parameter()]
    [string]$Version,
    
    [Parameter()]
    [string]$ConfigPath = "scripts/version_config.json"
)

$ErrorActionPreference = "Stop"

# 顏色輸出函數
function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
}

# 讀取配置
Write-ColorOutput "`n==> 讀取版本配置" "Cyan"
if (-not (Test-Path $ConfigPath)) {
    Write-ColorOutput "✗ 找不到配置文件: $ConfigPath" "Red"
    exit 1
}

$config = Get-Content $ConfigPath -Raw | ConvertFrom-Json

if ($Version) {
    $targetVersion = $Version
    Write-ColorOutput "使用指定版本: $targetVersion" "Yellow"
} else {
    # 自動從 setuptools-scm 獲取版本
    try {
        $scmVersion = & python -c "import setuptools_scm; print(setuptools_scm.get_version())" 2>$null
        if ($LASTEXITCODE -eq 0) {
            # 移除開發版本後綴，如 .dev0+...
            $targetVersion = $scmVersion -replace '\.dev\d+\+.*', ''
            Write-ColorOutput "從 setuptools-scm 獲取版本: $targetVersion" "Green"
        } else {
            $targetVersion = $config.version.current
            Write-ColorOutput "無法獲取 setuptools-scm 版本，使用配置版本: $targetVersion" "Yellow"
        }
    } catch {
        $targetVersion = $config.version.current
        Write-ColorOutput "無法獲取 setuptools-scm 版本，使用配置版本: $targetVersion" "Yellow"
    }
}

$date = Get-Date -Format "yyyy-MM-dd"
$displayDate = Get-Date -Format "yyyy年MM月dd日"

# 準備替換資料
$replacements = @{
    "PROJECT_NAME" = $config.project.name
    "DISPLAY_NAME" = $config.project.display_name
    "DESCRIPTION" = $config.project.description
    "VERSION" = $targetVersion
    "DATE" = $date
    "DISPLAY_DATE" = $displayDate
    "FUBON_NEO_VERSION" = $config.version.fubon_neo
    "PUBLISHER" = $config.publisher.name
    "PUBLISHER_DISPLAY" = $config.publisher.display_name
    "EXTENSION_ID" = $config.extension.id
    "URL_PYPI" = $config.urls.pypi
    "URL_MARKETPLACE" = $config.urls.marketplace
    "URL_REPOSITORY" = $config.urls.repository
    "URL_ISSUES" = $config.urls.issues
    "URL_DOCUMENTATION" = $config.urls.documentation
    "URL_FUBON_API" = $config.urls.fubon_api
}

Write-ColorOutput "`n版本資訊:" "Cyan"
Write-ColorOutput "  專案: $($config.project.display_name)" "White"
Write-ColorOutput "  版本: $targetVersion" "Yellow"
Write-ColorOutput "  Publisher: $($config.publisher.name)" "White"
Write-ColorOutput "  Extension ID: $($config.extension.id)" "White"

# 更新函數
function Update-FileVersion {
    param(
        [string]$FilePath,
        [string]$OldVersion,
        [string]$NewVersion
    )
    
    if (Test-Path $FilePath) {
        $content = Get-Content $FilePath -Raw
        $updated = $content -replace [regex]::Escape($OldVersion), $NewVersion
        
        if ($content -ne $updated) {
            Set-Content -Path $FilePath -Value $updated -NoNewline
            Write-ColorOutput "  ✓ $FilePath" "Green"
            return $true
        } else {
            Write-ColorOutput "  - $FilePath (未變更)" "Gray"
            return $false
        }
    } else {
        Write-ColorOutput "  ✗ $FilePath (不存在)" "Red"
        return $false
    }
}

# 獲取當前版本
$oldVersion = $config.version.current

Write-ColorOutput "`n==> 更新文件" "Cyan"

$updatedCount = 0

# 更新 vscode-extension/package.json
$packageJsonPath = "vscode-extension/package.json"
if (Test-Path $packageJsonPath) {
    $packageJson = Get-Content $packageJsonPath -Raw | ConvertFrom-Json
    $packageJson.version = $targetVersion
    $packageJson.publisher = $config.publisher.name
    $packageJson | ConvertTo-Json -Depth 10 | Set-Content $packageJsonPath
    Write-ColorOutput "  ✓ $packageJsonPath" "Green"
    $updatedCount++
}

# 更新其他文件中的版本號
$filesToUpdate = @(
    "README.md",
    "INSTALL.md",
    "CHANGELOG.md",
    "vscode-extension/README.md",
    "vscode-extension/CHANGELOG.md",
    "GITHUB_PUBLISH_GUIDE.md",
    "RELEASE_NOTES_v$targetVersion.md"
)

foreach ($file in $filesToUpdate) {
    if (Update-FileVersion -FilePath $file -OldVersion $oldVersion -NewVersion $targetVersion) {
        $updatedCount++
    }
}

# 更新配置文件中的版本
$config.version.current = $targetVersion
$config | ConvertTo-Json -Depth 10 | Set-Content $ConfigPath
Write-ColorOutput "  ✓ $ConfigPath" "Green"
$updatedCount++

Write-ColorOutput "`n==> 完成" "Cyan"
Write-ColorOutput "已更新 $updatedCount 個文件" "Green"
Write-ColorOutput "新版本: $targetVersion" "Yellow"
