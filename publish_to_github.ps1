# GitHub 發佈腳本 - 富邦 MCP 伺服器
# 使用方法: .\publish_to_github.ps1 -GitHubUsername "yourusername" -RepositoryName "fubon-api-mcp-server"

param(
    [Parameter(Mandatory=$true)]
    [string]$GitHubUsername,

    [Parameter(Mandatory=$true)]
    [string]$RepositoryName
)

$REPOSITORY_URL = "https://github.com/$GitHubUsername/$RepositoryName.git"

Write-Host "🚀 開始發佈富邦 MCP 伺服器到 GitHub" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Yellow
Write-Host "GitHub 用戶名: $GitHubUsername" -ForegroundColor Cyan
Write-Host "倉庫名稱: $RepositoryName" -ForegroundColor Cyan
Write-Host "倉庫 URL: $REPOSITORY_URL" -ForegroundColor Cyan
Write-Host ""

# 檢查是否已配置遠端倉庫
try {
    $existingRemote = git remote get-url origin 2>$null
    if ($existingRemote) {
        Write-Host "⚠️  發現已存在的遠端倉庫，正在重新配置..." -ForegroundColor Yellow
        git remote remove origin
    }
} catch {
    # 沒有遠端倉庫，繼續
}

# 添加 GitHub 遠端倉庫
Write-Host "📡 添加 GitHub 遠端倉庫..." -ForegroundColor Blue
git remote add origin $REPOSITORY_URL

# 推送代碼到 GitHub
Write-Host "⬆️  推送代碼到 GitHub..." -ForegroundColor Blue
Write-Host "   (請確保您有推送權限，並已配置 SSH 金鑰或個人存取權杖)" -ForegroundColor Gray

try {
    git push -u origin main
    Write-Host "" -ForegroundColor Green
    Write-Host "✅ 發佈完成！" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "您的專案現在可以在以下位置查看:" -ForegroundColor Cyan
    Write-Host "https://github.com/$GitHubUsername/$RepositoryName" -ForegroundColor White
    Write-Host "" -ForegroundColor Green
    Write-Host "📖 建議下一步:" -ForegroundColor Cyan
    Write-Host "1. 在 GitHub 上為專案添加描述和主題標籤" -ForegroundColor White
    Write-Host "2. 啟用 GitHub Actions (如果需要 CI/CD)" -ForegroundColor White
    Write-Host "3. 設定 Issues 和 Projects 來管理開發" -ForegroundColor White
    Write-Host "4. 考慮發佈到 PyPI: python setup.py sdist bdist_wheel; twine upload dist/*" -ForegroundColor White
} catch {
    Write-Host "" -ForegroundColor Red
    Write-Host "❌ 推送失敗！" -ForegroundColor Red
    Write-Host "錯誤信息: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "" -ForegroundColor Yellow
    Write-Host "🔧 故障排除:" -ForegroundColor Cyan
    Write-Host "1. 確保倉庫已創建: https://github.com/$GitHubUsername/$RepositoryName" -ForegroundColor White
    Write-Host "2. 檢查 SSH 金鑰或個人存取權杖配置" -ForegroundColor White
    Write-Host "3. 確認您對倉庫有推送權限" -ForegroundColor White
    exit 1
}