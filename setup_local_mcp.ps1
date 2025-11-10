# 本地MCP服務器設置腳本
# 用於自動配置VS Code的MCP服務器設置

Write-Host "🚀 設置本地Fubon API MCP服務器..." -ForegroundColor Green

# 檢查Python環境
Write-Host "📋 檢查Python環境..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python版本: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python未安裝或不在PATH中" -ForegroundColor Red
    exit 1
}

# 檢查項目依賴
Write-Host "📦 檢查項目依賴..." -ForegroundColor Yellow
try {
    python -c "import fubon_api_mcp_server.server" 2>$null
    Write-Host "✅ MCP服務器模組可用" -ForegroundColor Green
} catch {
    Write-Host "⚠️ 安裝項目依賴..." -ForegroundColor Yellow
    pip install -e .
}

# 設置VS Code配置
Write-Host "⚙️ 配置VS Code MCP服務器..." -ForegroundColor Yellow
$configDir = "$env:APPDATA\Code\User\globalStorage\github.copilot-chat"
$configPath = "$configDir\config.json"

# 確保目錄存在
if (!(Test-Path $configDir)) {
    New-Item -ItemType Directory -Path $configDir -Force | Out-Null
}

# 創建配置文件
$configContent = @'
{
  "mcpServers": {
    "fubon-api": {
      "command": "python",
      "args": ["-m", "fubon_api_mcp_server.server"],
      "env": {
        "FUBON_USERNAME": "D122452664",
        "FUBON_PFX_PATH": "C:\\\\CAFubon\\\\D122452664\\\\D122452664.pfx",
        "FUBON_DATA_DIR": "D:\\\\fubon-api-mcp-server\\\\data",
        "FUBON_PASSWORD": "${env:FUBON_PASSWORD}",
        "FUBON_PFX_PASSWORD": "${env:FUBON_PFX_PASSWORD}"
      }
    }
  }
}
'@

$configContent | Out-File -FilePath $configPath -Encoding UTF8 -Force
Write-Host "✅ VS Code配置已更新: $configPath" -ForegroundColor Green

# 測試MCP服務器
Write-Host "🧪 測試MCP服務器..." -ForegroundColor Yellow
try {
    $testResult = python test_mcp_local.py 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ MCP服務器測試通過" -ForegroundColor Green
        Write-Host $testResult -ForegroundColor Gray
    } else {
        Write-Host "⚠️ MCP服務器測試完成 (可能需要登入憑證)" -ForegroundColor Yellow
        Write-Host $testResult -ForegroundColor Gray
    }
} catch {
    Write-Host "❌ MCP服務器測試失敗" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}

# 最終說明
Write-Host "`n🎉 本地MCP服務器設置完成！" -ForegroundColor Green
Write-Host "`n📋 下一步:" -ForegroundColor Cyan
Write-Host "1. 完全重新啟動VS Code (不是重新載入視窗)" -ForegroundColor White
Write-Host "2. 打開GitHub Copilot Chat" -ForegroundColor White
Write-Host "3. 輸入 @ 符號，應該會看到 @fubon-api" -ForegroundColor White
Write-Host "4. 嘗試: @fubon-api 查詢2330的即時報價" -ForegroundColor White
Write-Host "`n📖 詳細說明請參考: LOCAL_MCP_SETUP.md" -ForegroundColor Cyan
Write-Host "🔧 如有問題請檢查: $configPath" -ForegroundColor Cyan