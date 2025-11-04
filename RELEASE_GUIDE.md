# 版本發布指南

## 🚀 自動化 CI/CD 流程

本專案採用完全自動化的 CI/CD 流程,支援自動測試、版本管理和發布。

### 📋 流程概覽

```
開發完成 → 執行測試 → 創建標籤 → 推送到 GitHub
    ↓
GitHub Actions 自動執行:
    ├─ CI 測試 (所有 Python 版本)
    ├─ 版本驗證
    ├─ 發布到 PyPI
    ├─ 發布到 VS Code Marketplace
    └─ 創建 GitHub Release
```

---

## 🎯 發布新版本

### 方法 1: 使用自動化腳本 (推薦)

```powershell
# 發布 patch 版本 (1.8.0 -> 1.8.1)
.\release.ps1

# 發布 minor 版本 (1.8.0 -> 1.9.0)
.\release.ps1 -BumpType minor

# 發布 major 版本 (1.8.0 -> 2.0.0)
.\release.ps1 -BumpType major
```

**腳本會自動:**
1. ✅ 檢查 Git 狀態
2. ✅ 執行完整測試
3. ✅ 計算新版本號
4. ✅ 創建並推送標籤
5. ✅ 觸發 GitHub Actions 自動發布

### 方法 2: 手動創建標籤

```bash
# 1. 確保所有變更已提交
git status

# 2. 創建標籤 (格式: v主版本.次版本.修訂版本)
git tag v1.8.1

# 3. 推送標籤到 GitHub
git push origin v1.8.1
```

推送標籤後,GitHub Actions 會自動:
- 執行 CI 測試
- 發布到 PyPI
- 發布到 VS Code Marketplace
- 創建 GitHub Release

### 方法 3: 使用 GitHub Actions 手動觸發

1. 前往 [GitHub Actions](https://github.com/Mofesto/fubon-api-mcp-server/actions)
2. 選擇 "Auto Release" 工作流程
3. 點擊 "Run workflow"
4. 選擇版本類型 (patch/minor/major)
5. 點擊 "Run workflow" 確認

---

## 📦 版本號規則

採用 [Semantic Versioning](https://semver.org/lang/zh-TW/) (語意化版本):

```
格式: v主版本.次版本.修訂版本

例如: v1.8.0
      │ │ │
      │ │ └─ 修訂版本 (patch): 向下相容的問題修正
      │ └─── 次版本 (minor): 向下相容的新功能
      └───── 主版本 (major): 不向下相容的 API 變更
```

### 何時使用哪種版本?

| 變更類型 | 版本類型 | 範例 |
|---------|---------|------|
| 🐛 Bug 修復 | `patch` | 1.8.0 → 1.8.1 |
| ✨ 新功能 (向下相容) | `minor` | 1.8.0 → 1.9.0 |
| 💥 破壞性變更 | `major` | 1.8.0 → 2.0.0 |

---

## 🔍 監控發布進度

### GitHub Actions
- 網址: https://github.com/Mofesto/fubon-api-mcp-server/actions
- 查看: CI 測試狀態、發布進度

### PyPI 發布
- 網址: https://pypi.org/project/fubon-api-mcp-server/
- 驗證: `pip search fubon-api-mcp-server` 或訪問網頁

### VS Code Marketplace
- 網址: https://marketplace.visualstudio.com/
- 搜尋: "fubon-api-mcp-server"

### GitHub Releases
- 網址: https://github.com/Mofesto/fubon-api-mcp-server/releases
- 下載: VSIX 文件、查看 Changelog

---

## ⚙️ CI/CD 配置

### 必要的 GitHub Secrets

在 GitHub 儲存庫設定中配置以下 Secrets:

1. **PYPI_API_TOKEN**
   - 用途: 發布到 PyPI
   - 獲取: https://pypi.org/manage/account/token/
   - 權限: 僅限此專案

2. **VSCODE_MARKETPLACE_TOKEN**
   - 用途: 發布到 VS Code Marketplace
   - 獲取: https://dev.azure.com/
   - 步驟:
     1. 創建 Azure DevOps 組織
     2. 創建 Personal Access Token
     3. 權限選擇: Marketplace (Publish)

### Workflow 文件

- **`.github/workflows/auto-release.yml`**: 自動發布流程
  - 觸發: 推送 `v*.*.*` 標籤或手動觸發
  - 執行: CI 測試 → PyPI 發布 → VS Code 發布 → GitHub Release

- **`.github/workflows/ci.yml`**: 持續整合測試
  - 觸發: 推送到 main/develop 或 PR
  - 執行: Lint + 測試 + 覆蓋率檢查

---

## 🛠️ 本地測試

在發布前,建議先在本地執行完整測試:

```powershell
# 執行 CI 驗證腳本
python validate_ci.py

# 或手動執行各項檢查
flake8 fubon_mcp tests
black --check fubon_mcp tests --exclude fubon_mcp/_version.py
isort --check-only fubon_mcp tests --skip fubon_mcp/_version.py
mypy fubon_mcp
pytest --cov=fubon_mcp --cov-fail-under=10
```

---

## 📝 發布清單

每次發布前檢查:

- [ ] 所有測試通過
- [ ] 代碼已格式化 (Black, isort)
- [ ] 類型檢查通過 (mypy)
- [ ] 覆蓋率達標 (≥10%)
- [ ] CHANGELOG.md 已更新
- [ ] README.md 版本號已更新 (如需要)
- [ ] 所有變更已提交並推送

---

## 🔄 回滾版本

如果發布後發現問題,可以快速回滾:

### 1. PyPI 回滾 (Yank)
```bash
# 標記版本為不推薦
pip install twine
twine yank fubon-api-mcp-server <版本號>
```

### 2. 刪除 GitHub 標籤
```bash
# 刪除本地標籤
git tag -d v1.8.1

# 刪除遠端標籤
git push origin :refs/tags/v1.8.1
```

### 3. 發布修復版本
```bash
# 修復問題後,發布新版本
.\release.ps1 -BumpType patch
```

---

## ❓ 常見問題

### Q: 為什麼 CI 測試失敗但沒有阻擋發布?

A: 因為所有 CI 步驟都設置了 `continue-on-error: true`,只會顯示警告。可以修改 `.github/workflows/auto-release.yml` 移除此設定來嚴格檢查。

### Q: 如何跳過某個發布步驟?

A: 編輯 `.github/workflows/auto-release.yml`,註解掉不需要的 job。

### Q: 版本號計算錯誤怎麼辦?

A: 使用手動標籤方式,明確指定版本號:
```bash
git tag v1.8.2
git push origin v1.8.2
```

### Q: 如何發布 beta 或 rc 版本?

A: 創建預發布標籤:
```bash
git tag v1.9.0-beta.1
git push origin v1.9.0-beta.1
```

---

## 📚 相關文件

- [GitHub Actions 文件](https://docs.github.com/actions)
- [PyPI 發布指南](https://packaging.python.org/tutorials/packaging-projects/)
- [VS Code Extension 發布](https://code.visualstudio.com/api/working-with-extensions/publishing-extension)
- [Semantic Versioning](https://semver.org/lang/zh-TW/)

---

## 🤝 需要協助?

如有問題,請:
1. 查看 [GitHub Issues](https://github.com/Mofesto/fubon-api-mcp-server/issues)
2. 查看 [GitHub Actions 日誌](https://github.com/Mofesto/fubon-api-mcp-server/actions)
3. 聯繫維護者

---

*最後更新: 2025-11-04*
