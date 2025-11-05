# Release Notes v1.8.8

Released: 2025-11-05

## 🎯 主要更新

### ✅ 測試覆蓋率大幅提升
- **總覆蓋率**: 從 65% 提升至 **82%**
- **218 個測試**全部通過 (1 個跳過)
- 新增 69 個測試案例

### 📊 模組覆蓋率改善
| 模組 | 之前 | 現在 | 提升 |
|------|------|------|------|
| `indicators_service.py` | 9% | 88% | +79% |
| `callbacks.py` | 29% | 82% | +53% |
| `server.py` | 51% | 77% | +26% |

### 🧪 新增測試模組
- `tests/test_indicators_service.py` - 23 個技術指標測試
- `tests/test_callbacks.py` - 19 個回調函數測試
- `tests/test_server.py` - 27 個 callable wrapper 測試

### 🔧 MCP 兼容性修正
- 為所有 MCP 工具函數添加 `.fn` 屬性兼容層
- 修正 `reports_service.py` - 6 個報表函數
- 修正 `trading_service.py` - 5 個交易函數
- 修正 `historical_data_service.py` - 1 個歷史數據函數

### 🚀 CI/CD 工具改進
- **新增**: `check_and_fix.py` - Python 版本完整 CI 檢查工具
- **新增**: `check_and_fix.ps1` - PowerShell 版本完整 CI 檢查工具
- **新增**: `quick_check.py` - 快速預提交檢查工具
- **新增**: `scripts/quick_check.ps1` - PowerShell 快速檢查工具
- **新增**: `quick_check_root.ps1` - 根目錄便捷包裝器
- **支援**: 自動修正代碼格式問題 (black, isort)
- **支援**: 從任意位置執行檢查腳本

### 🎨 VS Code Extension 重大更新 (v1.8.7)
- **修正**: MCP Server 無法在 GitHub Copilot 中顯示的問題
- **新增**: `modelContextProtocol` contribution point
- **新增**: `Configure Fubon MCP Server` 互動式配置命令
- **新增**: 自動寫入 GitHub Copilot MCP 配置檔案
- **新增**: MCP Server Provider 註冊機制
- **新增**: `MCP_SETUP_GUIDE.md` 詳細設置指南
- **改進**: 跨平台配置檔案路徑支援 (Windows/macOS/Linux)

### 🔒 安全性改進
- 建議使用環境變數管理敏感資訊
- 配置範例使用 `${env:VAR}` 語法
- 添加安全最佳實踐文檔

### 🐛 Bug 修正
- 修正 `test_execute_batch_orders` 缺少 `mock_executor` fixture
- 修正 `test_server.py` 中 21 個測試的 mock 設置
- 修正 `__init__.py` RuntimeWarning 通過延遲載入
- 修正 ThreadPoolExecutor mock 問題

### 📝 文檔更新
- 新增 `CI_SCRIPTS_GUIDE.md` - CI 腳本完整使用指南
- 新增 `MCP_SETUP_GUIDE.md` - VS Code MCP 設置疑難排解
- 更新 VS Code Extension CHANGELOG
- 添加多個配置範例和最佳實踐

## 📦 安裝

```bash
pip install --upgrade fubon-api-mcp-server
```

## 🔍 測試統計

```
==================== 217 passed, 1 skipped in 1.94s ====================
Coverage: 82% (905/1111 statements)
```

## 🚀 快速開始 CI 檢查

```bash
# Python 快速檢查
python quick_check.py

# PowerShell 快速檢查
.\quick_check_root.ps1

# 完整檢查並自動修正
python check_and_fix.py --fix
.\check_and_fix.ps1 -Fix
```

## 🔗 相關連結

- [GitHub Repository](https://github.com/Mofesto/fubon-api-mcp-server)
- [PyPI Package](https://pypi.org/project/fubon-api-mcp-server/)
- [VS Code Extension](https://marketplace.visualstudio.com/items?itemName=mofesto.fubon-api-mcp-server)
- [文檔](https://github.com/Mofesto/fubon-api-mcp-server#readme)

## 💡 重要提示

### VS Code Extension 用戶
如果你的 MCP Server 沒有在 GitHub Copilot 中顯示:
1. 更新到 Extension v1.8.7
2. 執行 `Configure Fubon MCP Server` 命令
3. 完全重新啟動 VS Code
4. 參考 `vscode-extension/MCP_SETUP_GUIDE.md`

### 開發者
- 提交前請執行 `quick_check` 進行快速驗證
- PR 前請執行完整的 `check_and_fix` 檢查
- 測試覆蓋率目標: 80%+ (當前: 82%)

## 🙏 貢獻者

感謝所有為此版本做出貢獻的開發者！

---

**完整更新日誌**: [CHANGELOG.md](CHANGELOG.md)
