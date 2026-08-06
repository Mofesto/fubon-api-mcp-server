# Scripts 資料夾

此資料夾包含所有專案管理和發布相關的腳本。

## 📁 文件說明

### 配置文件
- **`version_config.json`** - 集中管理所有版本和配置資訊
  - 專案名稱、描述
  - 當前版本號
  - Publisher 資訊
  - Extension ID
  - 所有 URL 連結

### 核心腳本

#### `release.ps1` - 自動發布腳本 (v2.0)
完整的自動化發布流程，從配置文件讀取版本資訊。

```powershell
# 發布 patch 版本 (預設)
.\scripts\release.ps1

# 發布 minor 版本
.\scripts\release.ps1 -BumpType minor

# 發布 major 版本
.\scripts\release.ps1 -BumpType major

# 跳過測試 (不建議)
.\scripts\release.ps1 -SkipTests
```

**功能**:
1. 讀取 `version_config.json` 配置
2. 檢查 Git 狀態和分支
3. 執行完整測試套件
4. 計算新版本號
5. 調用 `update_version.ps1` 更新所有文件
6. 調用 `generate_release_notes.ps1` 生成發布說明
7. 提交版本更新
8. 創建並推送 Git 標籤
9. 觸發 GitHub Actions 自動發布

#### `update_version.ps1` - 版本更新腳本
統一更新所有文件中的版本號和配置資訊。

```powershell
# 使用配置文件中的版本
.\scripts\update_version.ps1

# 更新到指定版本
.\scripts\update_version.ps1 -Version 1.8.5
```

**更新的文件**:
- `README.md`
- `INSTALL.md`
- `CHANGELOG.md`
- `vscode-extension/README.md`
- `vscode-extension/package.json`
- `vscode-extension/CHANGELOG.md`
- `GITHUB_PUBLISH_GUIDE.md`
- `version_config.json`

#### `generate_release_notes.ps1` - Release Notes 生成腳本
從配置文件動態生成 GitHub Release Notes。

```powershell
# 生成當前版本的 Release Notes
.\scripts\generate_release_notes.ps1

# 生成指定版本的 Release Notes
.\scripts\generate_release_notes.ps1 -Version 1.8.5

# 指定輸出路徑
.\scripts\generate_release_notes.ps1 -OutputPath custom_notes.md
```

## 🔄 工作流程

### 完整發布流程

```powershell
# 1. 確保代碼已提交
git add .
git commit -m "feat: add new feature"
git push

# 2. 執行發布腳本
.\scripts\release.ps1 -BumpType minor

# 3. 腳本會自動:
#    - 運行測試
#    - 更新版本號
#    - 生成 Release Notes
#    - 創建 Git 標籤
#    - 推送到 GitHub
#    - 觸發自動發布
```

### 僅更新版本號

```powershell
# 更新到新版本
.\scripts\update_version.ps1 -Version 1.9.0

# 提交更改
git add .
git commit -m "chore: bump version to 1.9.0"
git push
```

### 僅生成 Release Notes

```powershell
.\scripts\generate_release_notes.ps1 -Version 1.9.0
# 編輯生成的 RELEASE_NOTES_v1.9.0.md
# 在 GitHub Release 頁面使用
```

## 📝 配置管理

### 修改配置

編輯 `version_config.json`:

```json
{
  "version": {
    "current": "1.8.4",
    "fubon_neo": "2.2.8",
    "mcp": "2.0.0",
    "mcp_protocol": "2026-07-28"
  },
  "publisher": {
    "name": "mofesto",
    "display_name": "Mofesto.Cui"
  }
}
```

### 添加新的 URL

```json
{
  "urls": {
    "new_service": "https://example.com"
  }
}
```

然後修改相應的腳本以使用新的 URL。

## 🛡️ 最佳實踐

1. **版本號管理**
   - 所有版本號統一在 `version_config.json` 中管理
   - 使用 `update_version.ps1` 確保一致性

2. **發布前檢查**
   - 確保所有測試通過
   - 檢查 Git 狀態乾淨
   - 在 main 分支發布

3. **語義化版本**
   - patch: 向後兼容的錯誤修復
   - minor: 向後兼容的新功能
   - major: 破壞性變更

4. **文檔同步**
   - Release Notes 描述清晰
   - CHANGELOG 保持更新
   - README 包含最新功能

## 🐛 故障排除

### 版本更新失敗
```powershell
# 檢查配置文件
Get-Content scripts\version_config.json | ConvertFrom-Json

# 手動運行更新腳本
.\scripts\update_version.ps1 -Version 1.8.5
```

### Git 推送失敗
```powershell
# 檢查遠端狀態
git remote -v
git fetch origin

# 確保本地最新
git pull origin main
```

### 測試失敗
```powershell
# 運行特定測試
pytest tests/test_specific.py -v

# 檢查代碼格式
black fubon_api_mcp_server --check
flake8 fubon_api_mcp_server
```

## 📚 相關文檔

- [發布指南](.github/RELEASE_GUIDE.md)
- [貢獻指南](../CONTRIBUTING.md)
- [GitHub 發布指南](../GITHUB_PUBLISH_GUIDE.md)

## 🔧 維護

腳本由專案維護者維護。如有問題或建議，請提交 Issue。
