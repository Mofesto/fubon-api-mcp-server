# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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