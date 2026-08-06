# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.2.8] - 2026-08-06

### Changed
- Synchronize the extension release with the Fubon API MCP Server v2.2.8 release.
- Preserve automatic MCP registration and password-protected credential inputs.

## [2.2.3] - 2026-01-24

### 🔧 Fixed
- **MCP 自動註冊問題修正**: 修正擴展安裝後 MCP Server 無法自動出現在「已註冊 MCP」列表的問題
- 擴展激活時自動將 `fubon-api-mcp-server` 配置寫入 `mcp.json`
- 無需用戶手動執行 "Configure Fubon MCP Server" 命令

### ✨ Added
- 新增 `autoRegisterMCPServer()` 函數實現自動註冊邏輯
- 註冊成功後提示用戶重新載入 VS Code

### 📝 Changed
- 重構 `registerMCPServerProvider()` 函數
- 改進 inputs 配置，為密碼欄位添加 `password: true` 屬性

## [1.8.8] - 2025-11-05

### 🔧 Fixed
- **編碼問題修正**: 修正 VS Code 輸出通道中文亂碼問題
- 設置 `PYTHONIOENCODING=utf-8` 和 `PYTHONUTF8=1` 環境變數
- 改進 stdout/stderr 數據處理,明確使用 UTF-8 解碼

### 📝 Changed
- 優化日誌輸出的錯誤處理
- 添加編碼異常的 fallback 機制

## [1.8.7] - 2025-11-05

### 🔧 Fixed
- **MCP Server 註冊問題**: 添加正確的 `modelContextProtocol` contribution point 到 package.json
- 修正 MCP Server 無法在 GitHub Copilot "已安裝的 MCP Servers" 列表中顯示的問題
- 修正配置檔案路徑在不同作業系統上的相容性問題

### ✨ Added
- **Configure 命令**: 新增 `Configure Fubon MCP Server` 命令,提供互動式設定流程
- **自動配置寫入**: 自動更新 GitHub Copilot 的 MCP 配置檔案 (config.json)
- **MCP Server Provider**: 實作標準的 MCP Server Provider 註冊機制
- **詳細設置指南**: 添加 `MCP_SETUP_GUIDE.md` 完整的設置與疑難排解文檔
- 支援跨平台配置檔案路徑 (Windows/macOS/Linux)

### 📝 Changed
- 優化 extension.js 的 MCP Server Provider 註冊邏輯
- 改進配置檔案自動生成與更新機制
- 更新 README 添加 "為什麼 MCP Server 沒有出現" 疑難排解章節
- 添加環境變數配置範例

### 🔒 Security
- 強烈建議使用環境變數儲存敏感資訊 (密碼、憑證密碼)
- 配置範例使用 `${env:VAR}` 語法替代硬編碼密碼
- 添加安全最佳實踐說明

### 📚 Documentation
- 新增完整的 MCP Server 配置步驟說明
- 添加多個配置範例 (絕對路徑、環境變數、虛擬環境)
- 提供詳細的除錯步驟與檢查清單

## [1.8.6] - 2025-11-04

### Added
- 🚀 **VS Code Extension**: 完整的 VS Code Extension 功能
	- Extension ID: `mofesto.fubon-api-mcp-server`
	- Publisher: mofesto
	- Marketplace 發佈
- 🎯 **一鍵操作**: 啟動、停止、重啟 MCP Server
- 🔧 **配置管理**: 內建設定管理（帳號、憑證、數據目錄）
- 🔒 **安全輸入**: 密碼安全輸入，不儲存在設定檔中
- 📊 **即時日誌**: 輸出面板顯示 server 日誌
- ⚙️ **命令面板**: 支援所有操作指令
- 🔧 **動態版本**: setuptools-scm 自動版本管理
- 📦 **自動發佈**: GitHub Actions 自動發佈到 Marketplace

### Features
- Command: `Fubon MCP: Start Fubon MCP Server`
- Command: `Fubon MCP: Stop Fubon MCP Server`
- Command: `Fubon MCP: Restart Fubon MCP Server`
- Command: `Fubon MCP: Show Fubon MCP Server Logs`
- Configuration: Username, PFX Path, Data Dir, Auto Start

### Changed
- 版本管理改為從 Git tags 動態生成
- 改善發佈流程和自動化

### Security
- 密碼採用安全輸入方式
- 敏感資訊不儲存在配置中


## [1.7.0] - 2025-11-03

### Added
- GitHub Actions CI/CD workflows
- Pre-commit hooks configuration
- Dependabot dependency updates
- Code quality tools (Black, isort, flake8, mypy, bandit)
- Security scanning and vulnerability checks
- Automated PyPI publishing workflow
- Modern Python packaging with pyproject.toml
- Contributor guidelines and code of conduct
- Security policy documentation

### Changed
- Migrated from setup.py to pyproject.toml
- Enhanced testing infrastructure
- Improved code quality standards

### Fixed
- PyPI publishing authentication parameters in release workflow

### Added
- 🐛 **帳戶查詢修正**: 修正正式環境帳戶資訊查詢問題
- 🔧 **API 調用優化**: 修正庫存、損益、結算資訊的 API 調用方式
- ✅ **測試覆蓋完善**: 所有帳戶資訊功能測試通過 (7/7)
- 📊 **正式環境支援**: 確認正式環境支持所有查詢功能

### Fixed
- Account lookup logic to use first logged-in account instead of credential username
- API method calls for inventory, unrealized PnL, and settlement information
- Test fixtures to enable actual testing of formal environment capabilities

## [1.5.0] - 2025-11-03

### Added
- 🎯 **完整交易功能**: 實現完整的買賣流程
- 🔧 **參數驗證增強**: 支持所有交易參數
- 📊 **測試套件擴展**: 新增完整交易流程測試
- 📚 **文檔完善**: 詳細API說明和使用範例

### Features
- Complete order placement with all parameters (market_type, price_type, time_in_force, order_type)
- Order management (modify price/quantity, cancel orders)
- Batch parallel order placement using ThreadPoolExecutor
- Non-blocking order execution modes
- Comprehensive order status tracking

## [1.4.0] - 2025-10-XX

### Added
- 🔄 **斷線重連**: 自動WebSocket重連機制
- 🛡️ **系統穩定性**: 完善的錯誤處理
- 📈 **測試覆蓋**: 17項完整測試

### Features
- Automatic WebSocket reconnection on connection loss
- Comprehensive error handling and recovery
- Enhanced system stability and reliability

## [1.3.0] - 2025-10-XX

### Added
- 📡 **主動回報**: 委託、成交、事件通知
- 🔍 **即時監控**: 交易狀態追蹤

### Features
- Real-time order reports and notifications
- Filled order confirmations
- System event notifications
- Active monitoring capabilities

## [1.2.0] - 2025-10-XX

### Added
- 💰 **帳戶資訊**: 完整庫存和損益查詢
- 📊 **財務分析**: 成本價和盈虧計算

### Features
- Bank balance and available funds
- Complete inventory tracking
- Unrealized profit and loss calculations
- Financial analysis tools

## [1.1.0] - 2025-10-XX

### Added
- 🏦 **銀行水位**: 資金餘額查詢
- 💳 **帳戶管理**: 基本帳戶資訊

### Features
- Bank balance inquiries
- Basic account information management

## [1.0.0] - 2025-09-XX

### Added
- 🚀 **初始版本**: 基礎交易和行情功能
- 📦 **MCP整合**: Model Communication Protocol支持

### Features
- Basic trading functionality
- Market data access
- MCP server implementation
- Initial API integration

---

## Types of changes

- `Added` for new features
- `Changed` for changes in existing functionality
- `Deprecated` for soon-to-be removed features
- `Removed` for now removed features
- `Fixed` for any bug fixes
- `Security` in case of vulnerabilities

## Versioning

This project uses [Semantic Versioning](https://semver.org/).

Given a version number MAJOR.MINOR.PATCH, increment the:

- **MAJOR** version when you make incompatible API changes
- **MINOR** version when you add functionality in a backwards compatible manner
- **PATCH** version when you make backwards compatible bug fixes

Additional labels for pre-release and build metadata are available as extensions to the MAJOR.MINOR.PATCH format.
