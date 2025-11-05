# 發佈指南 - Release Guide

## 版本管理策略

本專案使用 **setuptools-scm** 進行動態版本管理，版本號從 Git tags 自動生成，不在程式碼中寫死。

### 版本號規則

- **Release 版本**: `1.8.0`, `1.9.0` (從 Git tag 生成)
- **開發版本**: `1.8.1.dev0+g668432028.d20251104` (自動生成)

### setuptools-scm 配置

```toml
[tool.setuptools_scm]
write_to = "fubon_api_mcp_server/_version.py"
version_scheme = "post-release"
local_scheme = "node-and-date"
fallback_version = "1.8.0"
```

## 發佈到 PyPI

### 方式一：透過 GitHub Release (推薦)

#### 步驟 1: 創建 Git Tag

```powershell
# 創建版本標籤 (例如: v1.8.0)
git tag v1.8.0

# 推送標籤到 GitHub
git push origin v1.8.0
```

#### 步驟 2: 創建 GitHub Release

1. 訪問: https://github.com/Mofesto/fubon-api-mcp-server/releases/new
2. 選擇剛才創建的標籤: `v1.8.0`
3. 填寫 Release 標題: `Release v1.8.0`
4. 填寫 Release 說明 (參考下方模板)
5. 點擊 "Publish release"

#### 步驟 3: GitHub Actions 自動發佈

- Workflow 會自動觸發: `.github/workflows/release.yml`
- 自動構建套件: `python -m build`
- 自動上傳到 PyPI: 使用 `PYPI_API_TOKEN`
- 驗證上傳: https://pypi.org/project/fubon-api-mcp-server/

#### Release 說明模板

```markdown
## What's Changed in v1.8.0

### 🚀 新功能 (Features)
- 完整的 VS Code Extension (Extension ID: mofesto.fubon-api-mcp-server)
- 新增動態版本管理 (setuptools-scm)
- 完整的 MCP server 功能驗證
- 自動化發佈流程 (PyPI + Marketplace)

### 🐛 修正 (Bug Fixes)
- 修正版本號管理問題
- 改善 CI/CD 流程

### 📚 文檔 (Documentation)
- 新增發佈指南
- 更新 README 和 API 說明

### 🔧 維護 (Maintenance)
- 移除 Python 3.14 支援 (未發布)
- 更新所有依賴到最新版本
- 改善測試覆蓋率

### 📦 依賴更新 (Dependencies)
- actions/checkout: v4 → v5
- actions/setup-python: v4 → v6
- codecov-action: v3 → v5

**Full Changelog**: https://github.com/Mofesto/fubon-api-mcp-server/compare/v1.7.0...v1.8.0
```

### 方式二：手動觸發 Workflow

1. 訪問: https://github.com/Mofesto/fubon-api-mcp-server/actions/workflows/release.yml
2. 點擊 "Run workflow"
3. 選擇分支: `main`
4. 選擇版本升級類型:
   - `patch`: 1.8.0 → 1.8.1
   - `minor`: 1.8.0 → 1.9.0
   - `major`: 1.8.0 → 2.0.0
5. 點擊 "Run workflow"

### 方式三:本地構建並上傳 (測試用)

```powershell
# 1. 確保在正確的 tag 上
git checkout v1.8.0

# 2. 清理舊的構建
Remove-Item -Recurse -Force dist, build, *.egg-info -ErrorAction SilentlyContinue

# 3. 構建套件
python -m build

# 4. 檢查套件
twine check dist/*

# 5. 上傳到 TestPyPI (測試)
twine upload --repository testpypi dist/*

# 6. 上傳到 PyPI (正式)
twine upload dist/*
```

## 設定 PyPI API Token

### 步驟 1: 獲取 PyPI Token

1. 登入 PyPI: https://pypi.org/
2. 進入 Account settings → API tokens
3. 創建新 token:
   - Token name: `fubon-api-mcp-server-github-actions`
   - Scope: 選擇 `fubon-api-mcp-server` 專案
4. **複製 token** (只會顯示一次！)

### 步驟 2: 設定 GitHub Secret

1. 訪問: https://github.com/Mofesto/fubon-api-mcp-server/settings/secrets/actions
2. 點擊 "New repository secret"
3. Name: `PYPI_API_TOKEN`
4. Value: 貼上剛才複製的 token
5. 點擊 "Add secret"

## 驗證發佈成功

### 檢查 PyPI

1. 訪問: https://pypi.org/project/fubon-api-mcp-server/
2. 確認版本號正確: `1.8.0`
3. 檢查套件資訊是否完整

### 測試安裝

```powershell
# 創建測試環境
python -m venv test_env
.\test_env\Scripts\activate

# 安裝最新版本
pip install fubon-api-mcp-server

# 驗證版本
python -c "import fubon_api_mcp_server; print(fubon_api_mcp_server.__version__)"

# 測試基本功能
python -c "from fubon_api_mcp_server import mcp; print('MCP server loaded')"

# 清理
deactivate
Remove-Item -Recurse test_env
```

### 監控 GitHub Actions

1. 訪問: https://github.com/Mofesto/fubon-api-mcp-server/actions
2. 檢查 "Release" workflow 狀態
3. 查看 workflow logs 確認所有步驟成功

## VS Code Marketplace 發佈

### 前置作業

VS Code Extension 需要 VS Code 特定的結構，我們需要創建 extension 包裝器。

#### Extension 結構

```
fubon-api-mcp-server-vscode/
├── package.json          # Extension 配置
├── README.md            # Extension 說明
├── CHANGELOG.md         # 版本歷史
├── icon.png            # Extension 圖示
└── src/
    └── extension.js    # Extension 程式碼
```

### 步驟 1: 準備 Extension 專案

```powershell
# 創建 extension 目錄
New-Item -ItemType Directory -Path .\vscode-extension

# 複製必要文件
Copy-Item README.md .\vscode-extension\
Copy-Item CHANGELOG.md .\vscode-extension\
```

### 步驟 2: 創建 package.json

```json
{
  "name": "fubon-api-mcp-server",
  "displayName": "Fubon API MCP Server",
  "description": "富邦證券 MCP Server - 完整的台股交易功能與市場數據查詢",
  "version": "1.8.0",
  "publisher": "mofesto",
  "engines": {
    "vscode": "^1.80.0"
  },
  "categories": ["Other"],
  "keywords": ["fubon", "trading", "mcp", "taiwan-stock"],
  "repository": {
    "type": "git",
    "url": "https://github.com/Mofesto/fubon-api-mcp-server"
  },
  "contributes": {
    "mcpServers": {
      "fubon-api": {
        "command": "python",
        "args": ["-m", "fubon_api_mcp_server.server"]
      }
    }
  }
}
```

### 步驟 3: 發佈到 Marketplace

```powershell
# 安裝 vsce
npm install -g @vscode/vsce

# 打包 extension
vsce package

# 發佈到 marketplace
vsce publish -p YOUR_PERSONAL_ACCESS_TOKEN
```

### 獲取 Visual Studio Marketplace Token

1. 訪問: https://dev.azure.com/
2. 創建 Personal Access Token
3. Scope: Marketplace (Publish)
4. 設定為 GitHub Secret: `VSCODE_MARKETPLACE_TOKEN`

## 版本發佈檢查清單

### 發佈前

- [ ] 所有測試通過 (`pytest`)
- [ ] CI/CD pipeline 成功
- [ ] 代碼格式化完成 (`black`, `isort`)
- [ ] 型別檢查通過 (`mypy`)
- [ ] 覆蓋率達標 (>80%)
- [ ] CHANGELOG.md 已更新
- [ ] README.md 已更新

### 發佈中

- [ ] 創建 Git tag: `git tag v1.8.0`
- [ ] 推送 tag: `git push origin v1.8.0`
- [ ] 創建 GitHub Release
- [ ] 確認 GitHub Actions 執行成功
- [ ] 驗證 PyPI 上傳成功

### 發佈後

- [ ] 測試 PyPI 安裝: `pip install fubon-api-mcp-server`
- [ ] 驗證版本號正確
- [ ] 測試基本功能
- [ ] 更新文檔連結
- [ ] 公告發佈資訊

## 回滾策略

### 如果發現嚴重問題

1. **PyPI 無法刪除版本**，只能標記為 "yanked"
2. **快速修正**: 發佈 patch 版本 (例如: 1.8.1)
3. **GitHub Release**: 標記為 "Pre-release" 或刪除

### Yank 版本 (PyPI)

```powershell
# 標記版本為 yanked (不推薦安裝)
twine upload --skip-existing --repository pypi dist/*
# 然後在 PyPI 網頁手動 yank
```

## 故障排查

### 問題: setuptools-scm 無法讀取版本

```powershell
# 確認 Git tags 存在
git tag

# 確認 .git 目錄存在
Test-Path .git

# 手動測試版本生成
python -c "from setuptools_scm import get_version; print(get_version())"
```

### 問題: PyPI 上傳失敗

```powershell
# 檢查 token 是否正確設定
# 在 GitHub: Settings → Secrets → PYPI_API_TOKEN

# 測試 token (本地)
twine upload --repository testpypi dist/* --verbose
```

### 問題: GitHub Actions 失敗

1. 檢查 workflow logs
2. 確認所有 secrets 已設定
3. 驗證 workflow 語法正確
4. 測試本地構建流程

## 相關連結

- **PyPI 專案**: https://pypi.org/project/fubon-api-mcp-server/
- **GitHub Releases**: https://github.com/Mofesto/fubon-api-mcp-server/releases
- **GitHub Actions**: https://github.com/Mofesto/fubon-api-mcp-server/actions
- **PyPI 說明文檔**: https://packaging.python.org/
- **setuptools-scm 文檔**: https://github.com/pypa/setuptools_scm

---

**Created**: 2025-11-04  
**Last Updated**: 2025-11-04  
**Version**: 1.0.0
