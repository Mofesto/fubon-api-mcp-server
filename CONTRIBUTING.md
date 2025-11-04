# Contributing to Fubon MCP Server

感謝您對富邦 MCP 伺服器專案的興趣！我們歡迎所有形式的貢獻，包括但不限於：

- 🐛 回報錯誤
- 💡 提出新功能建議
- 📝 改進文檔
- 🔧 提交代碼修復或功能增強
- 🎨 改進用戶界面和體驗

## 🚀 快速開始

### 開發環境設定

1. **Fork 專案**
   ```bash
   git clone https://github.com/mofesto/fubon-api-mcp-server.git
   cd fubon-api-mcp-server
   ```

2. **建立開發環境**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

3. **安裝 pre-commit hooks**
   ```bash
   pre-commit install
   ```

4. **運行測試**
   ```bash
   pytest
   ```

### 專案結構

```
fubon-api-mcp-server/
├── fubon_mcp/              # 主要程式碼
│   ├── __init__.py        # 包初始化
│   └── server.py          # MCP 伺服器主程式
├── tests/                  # 測試套件
├── examples/               # 使用範例
├── docs/                   # 文檔
├── .github/               # GitHub 配置
│   └── workflows/         # CI/CD 工作流程
├── pyproject.toml         # 專案配置
├── requirements.txt       # 依賴列表
└── README.md             # 專案說明
```

## 📝 開發工作流程

### 1. 建立功能分支

```bash
git checkout -b feature/your-feature-name
# 或
git checkout -b fix/issue-number-description
```

### 2. 編寫代碼

- 遵循 PEP 8 編碼規範
- 添加適當的類型提示
- 編寫完整的文檔字串
- 確保代碼通過所有測試

### 3. 提交代碼

```bash
# 添加更改
git add .

# 使用 conventional commits 格式
git commit -m "feat: add new trading feature"
git commit -m "fix: resolve account balance issue"
git commit -m "docs: update API documentation"
git commit -m "test: add unit tests for new feature"
```

### 4. 推送並建立 Pull Request

```bash
git push origin feature/your-feature-name
```

然後在 GitHub 上建立 Pull Request。

## 🧪 測試要求

### 運行測試套件

```bash
# 運行所有測試
pytest

# 運行特定測試
pytest tests/test_account_info.py

# 運行覆蓋率測試
pytest --cov=fubon_mcp --cov-report=html
```

### 測試覆蓋率要求

- 整體覆蓋率應 >= 80%
- 新功能必須包含對應的單元測試
- 關鍵路徑應有整合測試

## 🎨 代碼品質

### 代碼格式化

專案使用以下工具確保代碼品質：

- **Black**: 代碼格式化
- **isort**: 導入排序
- **flake8**: 代碼檢查
- **mypy**: 類型檢查

```bash
# 格式化代碼
black fubon_mcp tests
isort fubon_mcp tests

# 檢查代碼
flake8 fubon_mcp tests
mypy fubon_mcp
```

### Pre-commit Hooks

專案配置了 pre-commit hooks，會在提交前自動檢查代碼品質：

```bash
# 安裝 hooks
pre-commit install

# 手動運行
pre-commit run --all-files
```

## 📚 文檔

### 更新文檔

- 修改 `README.md` 中的使用說明
- 在 `examples/` 中添加使用範例
- 更新 docstrings

### 編寫提交訊息

使用 [Conventional Commits](https://conventionalcommits.org/) 格式：

```
type(scope): description

[optional body]

[optional footer]
```

類型包括：
- `feat`: 新功能
- `fix`: 錯誤修復
- `docs`: 文檔更新
- `style`: 代碼格式調整
- `refactor`: 代碼重構
- `test`: 測試相關
- `chore`: 建構工具或輔助工具變更

## 🔒 安全注意事項

- 不要提交敏感資訊（如密碼、API 金鑰）
- 確保所有依賴項都是安全的
- 及時更新安全漏洞修復

## 🐛 回報問題

### 錯誤回報

請使用 GitHub Issues 回報錯誤，包含：

- 錯誤描述
- 重現步驟
- 預期行為
- 實際行為
- 環境資訊（Python 版本、作業系統等）

### 功能請求

請使用 GitHub Issues 提出新功能請求，包含：

- 功能描述
- 使用場景
- 預期實現方式

## 📋 Pull Request 檢查清單

提交 PR 前請確認：

- [ ] 代碼通過所有測試
- [ ] 代碼覆蓋率 >= 80%
- [ ] 通過所有代碼品質檢查
- [ ] 更新相關文檔
- [ ] 添加適當的測試
- [ ] 遵循編碼規範
- [ ] 提交訊息清晰且遵循 conventional commits

## 🎯 行為準則

請閱讀並遵循我們的 [行為準則](CODE_OF_CONDUCT.md)。

## 📞 聯絡方式

- 📧 Email: mcp@fubon.com
- 💬 Issues: [GitHub Issues](https://github.com/Mofesto/fubon-api-mcp-server/issues)

感謝您的貢獻！🎉