#!/usr/bin/env bash
# GitHub 發佈腳本 - 富邦 MCP 伺服器
# 使用方法: ./publish_to_github.sh <github_username> <repository_name>

set -e

# 檢查參數
if [ $# -ne 2 ]; then
    echo "使用方法: $0 <github_username> <repository_name>"
    echo "範例: $0 yourusername fubon-api-mcp-server"
    exit 1
fi

GITHUB_USERNAME=$1
REPOSITORY_NAME=$2
REPOSITORY_URL="https://github.com/$GITHUB_USERNAME/$REPOSITORY_NAME.git"

echo "🚀 開始發佈富邦 MCP 伺服器到 GitHub"
echo "========================================"
echo "GitHub 用戶名: $GITHUB_USERNAME"
echo "倉庫名稱: $REPOSITORY_NAME"
echo "倉庫 URL: $REPOSITORY_URL"
echo ""

# 檢查是否已配置遠端倉庫
if git remote get-url origin >/dev/null 2>&1; then
    echo "⚠️  發現已存在的遠端倉庫，正在重新配置..."
    git remote remove origin
fi

# 添加 GitHub 遠端倉庫
echo "📡 添加 GitHub 遠端倉庫..."
git remote add origin $REPOSITORY_URL

# 推送代碼到 GitHub
echo "⬆️  推送代碼到 GitHub..."
echo "   (請確保您有推送權限，並已配置 SSH 金鑰或個人存取權杖)"
git push -u origin main

echo ""
echo "✅ 發佈完成！"
echo "========================================"
echo "您的專案現在可以在以下位置查看:"
echo "https://github.com/$GITHUB_USERNAME/$REPOSITORY_NAME"
echo ""
echo "📖 建議下一步:"
echo "1. 在 GitHub 上為專案添加描述和主題標籤"
echo "2. 啟用 GitHub Actions (如果需要 CI/CD)"
echo "3. 設定 Issues 和 Projects 來管理開發"
echo "4. 考慮發佈到 PyPI: python setup.py sdist bdist_wheel && twine upload dist/*"