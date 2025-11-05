# 發佈完成檢查清單

## ✅ 已完成項目

### 1. 本地 MCP 功能驗證 ✓
- [x] 創建 `test_mcp_server.py` 測試腳本
- [x] 測試版本資訊讀取
- [x] 測試模組導入功能
- [x] 測試 MCP server 物件創建
- [x] 測試 callable wrappers
- [x] **結果**: 5/5 測試全部通過 🎉

### 2. 動態版本管理配置 ✓
- [x] 安裝 `setuptools-scm`
- [x] 更新 `setup.py` 使用 `use_scm_version`
- [x] 更新 `pyproject.toml` fallback 版本為 1.8.0
- [x] 移除所有 Python 3.14 引用 (未發布)
- [x] 創建 Git tag: `v1.8.0`
- [x] 測試版本生成: `1.8.0.post0+g668432028.d20251104`
- [x] 成功構建套件: `python -m build`
- [x] **結果**: 版本自動從 Git tags 生成 ✓

### 3. PyPI 發佈流程更新 ✓
- [x] GitHub Actions Release workflow 已存在
- [x] 配置 setuptools-scm 整合
- [x] 支援從 GitHub Release 自動觸發
- [x] 支援手動觸發 (workflow_dispatch)
- [x] 創建 `.github/RELEASE_GUIDE.md` 詳細文檔
- [x] **結果**: 完整的自動化發佈流程 ✓

### 4. VS Code Extension 準備 ✓
- [x] 創建 `vscode-extension/` 目錄結構
- [x] 創建 `package.json` (extension manifest)
- [x] 創建 `src/extension.js` (主程式)
- [x] 創建 `README.md` (使用說明)
- [x] 複製 `CHANGELOG.md`
- [x] 創建 icon 說明文件
- [x] **結果**: Extension 完整結構就緒 ✓

### 5. VS Code Marketplace 發佈配置 ✓
- [x] 創建 `.github/workflows/vscode-extension.yml`
- [x] 配置自動版本同步
- [x] 配置 VSIX 打包流程
- [x] 配置 Marketplace 發佈流程
- [x] 配置 GitHub Release 附件上傳
- [x] **結果**: 完整的 Extension CI/CD pipeline ✓

## 📋 待執行項目 (需要手動操作)

### A. PyPI 發佈前置作業

#### 1. 設定 PyPI Token
```powershell
# 步驟:
# 1. 訪問 https://pypi.org/ 登入
# 2. Account settings → API tokens
# 3. 創建 token (scope: fubon-api-mcp-server)
# 4. 複製 token
# 5. GitHub repo → Settings → Secrets → Actions
# 6. 新增 secret: PYPI_API_TOKEN = <your_token>
```

#### 2. 創建 GitHub Release
```powershell
# 方式一: 使用 Web UI
# 1. 訪問 https://github.com/Mofesto/fubon-api-mcp-server/releases/new
# 2. 選擇 tag: v1.8.0
# 3. 填寫 release notes (參考 RELEASE_GUIDE.md)
# 4. 點擊 "Publish release"

# 方式二: 使用 gh CLI
gh release create v1.8.0 --title "Release v1.8.0" --notes "參考 .github/RELEASE_GUIDE.md"
```

#### 3. 驗證 PyPI 發佈
```powershell
# 等待 GitHub Actions 完成
# 訪問 https://github.com/Mofesto/fubon-api-mcp-server/actions

# 測試安裝
python -m venv test_env
.\test_env\Scripts\activate
pip install fubon-api-mcp-server==1.8.0
python -c "import fubon_api_mcp_server; print(fubon_api_mcp_server.__version__)"
deactivate
Remove-Item -Recurse test_env
```

### B. VS Code Extension 發佈前置作業

#### 1. 創建 Publisher Account
```powershell
# 步驟:
# 1. 訪問 https://marketplace.visualstudio.com/manage
# 2. 使用 Microsoft 帳號登入
# 3. 創建 Publisher (ID: mofesto)
# 4. 填寫 Publisher 資訊
```

#### 2. 獲取 Personal Access Token
```powershell
# 步驟:
# 1. 訪問 https://dev.azure.com/
# 2. User Settings → Personal Access Tokens
# 3. 創建 token:
#    - Name: vscode-marketplace-fubon-mcp
#    - Organization: All accessible organizations
#    - Expiration: 1 year
#    - Scopes: Marketplace (Publish)
# 4. 複製 token
# 5. GitHub repo → Settings → Secrets → Actions
# 6. 新增 secret: VSCODE_MARKETPLACE_TOKEN = <your_token>
```

#### 3. 準備 Extension Icon
```powershell
# 創建或取得 128x128 PNG icon
# 放置到 vscode-extension/icon.png
# 確保符合 VS Code Extension 設計規範
```

#### 4. 本地測試 Extension (可選)
```powershell
cd vscode-extension
npm install
npm install -g @vscode/vsce
vsce package
# 會生成 .vsix 文件

# 在 VS Code 中測試:
# Extensions → ... → Install from VSIX
```

#### 5. 觸發 Extension 發佈
```powershell
# GitHub Release 會自動觸發 vscode-extension.yml workflow
# 或手動觸發:
# 1. 訪問 https://github.com/Mofesto/fubon-api-mcp-server/actions/workflows/vscode-extension.yml
# 2. 點擊 "Run workflow"
# 3. 輸入 version: 1.8.0
# 4. 點擊 "Run workflow"
```

## 📝 提交變更

```powershell
# 查看變更
git status

# 添加所有變更
git add .

# 提交 (完整訊息)
git commit -m "feat: add release automation and VS Code extension

- Setup setuptools-scm for dynamic versioning from Git tags
- Update pyproject.toml and setup.py for version 1.8.0
- Remove Python 3.14 support (not yet released)
- Create comprehensive RELEASE_GUIDE.md
- Add VS Code extension structure:
  - package.json with MCP server commands
  - extension.js with server lifecycle management
  - README.md with usage instructions
- Add vscode-extension.yml workflow for automated publishing
- Create test_mcp_server.py for local validation
- Update .gitignore for extension artifacts

Breaking Changes:
- Version now generated from Git tags, not hardcoded
- Requires setuptools-scm for builds

BREAKING CHANGE: Version management migrated to setuptools-scm"

# 推送到 GitHub
git push origin main

# 推送 tag
git push origin v1.8.0
```

## 🎯 發佈流程總覽

### PyPI 發佈
```
Git Tag (v1.8.0)
    ↓
GitHub Release
    ↓
release.yml workflow 觸發
    ↓
setuptools-scm 生成版本
    ↓
python -m build
    ↓
PyPI 發佈
    ↓
驗證安裝
```

### VS Code Extension 發佈
```
GitHub Release (v1.8.0)
    ↓
vscode-extension.yml workflow 觸發
    ↓
更新 package.json 版本
    ↓
npm install & vsce package
    ↓
VS Code Marketplace 發佈
    ↓
VSIX 附加到 GitHub Release
```

## 📊 驗證清單

### PyPI 驗證
- [ ] PyPI 頁面版本正確: https://pypi.org/project/fubon-api-mcp-server/
- [ ] pip install 成功
- [ ] import fubon_api_mcp_server 成功
- [ ] 版本號匹配: `fubon_api_mcp_server.__version__`
- [ ] 所有依賴正確安裝

### VS Code Extension 驗證
- [ ] Marketplace 頁面顯示正常
- [ ] Extension 可搜尋到: "Fubon API MCP Server"
- [ ] Extension 可安裝
- [ ] Commands 正常運作
- [ ] Settings 配置正常
- [ ] Server 可正常啟動

## 📚 相關文檔

- **發佈指南**: `.github/RELEASE_GUIDE.md`
- **CI 修正**: `.github/CI_FIXES.md`
- **提交指南**: `.github/COMMIT_GUIDE.md`
- **Extension README**: `vscode-extension/README.md`

## 🔗 重要連結

- **GitHub Repo**: https://github.com/Mofesto/fubon-api-mcp-server
- **PyPI Project**: https://pypi.org/project/fubon-api-mcp-server/
- **VS Code Marketplace**: https://marketplace.visualstudio.com/items?itemName=mofesto.fubon-api-mcp-server
- **GitHub Actions**: https://github.com/Mofesto/fubon-api-mcp-server/actions
- **Codecov**: https://codecov.io/gh/Mofesto/fubon-api-mcp-server

---

**Created**: 2025-11-04  
**Status**: ✅ 所有技術準備完成，等待發佈執行  
**Next Step**: 設定 PyPI 和 VS Code Marketplace tokens，然後創建 GitHub Release
