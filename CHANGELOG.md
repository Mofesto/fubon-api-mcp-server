# Changelog

## [Unreleased]

### MCP 2.0 / Protocol 2026-07-28

### Changed
- 遷移官方 MCP Python SDK v2，使用 `MCPServer` 取代 v1 的 `FastMCP`。
- 新增 Streamable HTTP transport 設定，預設使用 stateless 模式；stdio 維持預設以相容桌面 Host。
- 由官方 SDK 處理 `server/discover`、2026-07-28 per-request metadata、structured output 與嚴格 schema 驗證。
- 移除與官方 MCP v2 不相容的獨立 `fastmcp` 依賴。

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

### SDK v2.2.8

#### Added
- 新增 `get_capital_changes`、`get_dividends` 與 `get_listing_applicants` MCP 市場資料工具。
- 歷史 K 線支援 `adjusted` 還原股價，以及 `timeframe`、`fields`、`sort` 參數。
- 證券普通下單與批量下單支援 `user_def`，並在送出 SDK 前驗證英數字與 10 字元上限。

#### Changed
- `fubon_neo` 升級至 v2.2.8，並更新 Windows、Linux、macOS ARM64、macOS x86_64 wheels。
- API-Key 登入改用 v2.2.8 正式介面 `apikey_login(personal_id, api_key, cert_path, cert_password)`；傳統 PFX 登入維持相容。
- adjusted、非日線或指定欄位的歷史查詢不使用既有未調整日線 SQLite 快取，避免資料語意混用。

## [2.2.7] - 2026-01-19

### Added - SDK v2.2.7 Upgrade

#### 🔐 API-Key Authentication (P1 Feature)
- **New authentication method**: API-Key + Secret for passwordless login
- **Use cases**: CI/CD pipelines, cloud deployments, IP whitelisting
- **Dual authentication support**: Traditional PFX and API-Key both fully supported
- **Environment variables**: `FUBON_API_KEY` and `FUBON_API_SECRET`
- **Bilingual error messages**: All validation messages in English + Traditional Chinese (繁體中文)
- **Comprehensive tests**: 14 new tests covering all API-Key scenarios (100% passing)

新增 API-Key 認證機制：支援無密碼登入、CI/CD 整合、雲端部署場景。同時支援傳統 PFX 憑證認證與新式 API-Key 認證。

#### 📜 Certificate Export (P2 Feature)
- **Export web certificates**: Programmatic export in PKCS#12 (.pfx) format
- **Password protection**: Required password for export security
- **Format validation**: PKCS#12 magic bytes verification (0x30 0x82)
- **Round-trip testing**: Export and import validation
- **Bilingual error messages**: Certificate export errors in English + Chinese
- **Comprehensive tests**: 12 new tests covering all export scenarios (100% passing)

新增憑證匯出功能：支援程式化匯出 PKCS#12 格式憑證、密碼保護、格式驗證。

#### ✅ SDK Compatibility Validation (P2 Feature)
- **100% backward compatible**: All 316 existing tests pass unchanged
- **Enum verification**: All trading parameters (BSAction, PriceType, MarketType, OrderType, TimeInForce) validated
- **API signature compatibility**: All methods unchanged, only additive changes
- **Platform support**: Windows, macOS (ARM64 + x86_64), Linux x86_64
- **Python 3.13 support**: Extended Python version support (3.8 - 3.13)
- **Comprehensive tests**: 14 new compatibility tests (100% passing)

完成 SDK v2.2.7 相容性驗證：所有 316 個現有測試通過、所有交易參數 enum 驗證通過、多平台支援。

### Changed
- **SDK version**: Upgraded from `fubon_neo==2.2.4` to `fubon_neo>=2.2.7`
- **Test suite**: Expanded from 316 to 342 total tests (+26 new tests)
- **Code coverage**: Core services 81% (exceeds 80% target)
- **Documentation**: README.md updated with bilingual API-Key setup guide

### Dependencies
- **Python**: Now supports Python 3.8 - 3.13 (previously 3.8 - 3.12)
- **SDK wheels**: Platform-specific wheels included in `wheels/` directory
  - Windows 64-bit: `fubon_neo-2.2.7-cp37-abi3-win_amd64.whl`
  - macOS ARM64: `fubon_neo-2.2.7-cp37-abi3-macosx_11_0_arm64.whl`
  - macOS x86_64: `fubon_neo-2.2.7-cp37-abi3-macosx_10_12_x86_64.whl`
  - Linux x86_64: `fubon_neo-2.2.7-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`

### Documentation
- **README.md**: Added comprehensive API-Key authentication section (bilingual)
- **.env.example**: Updated with API-Key configuration examples
- **COMPATIBILITY_REPORT.md**: Full SDK v2.2.4→v2.2.7 compatibility analysis
- **Bilingual support**: All user-facing messages in English + Traditional Chinese

### Testing
- **Total tests**: 342 (316 existing + 26 new)
- **Pass rate**: 100% (342/342 passing)
- **Code coverage**: 69% overall, 81% core services
- **New test files**:
  - `tests/test_auth_apikey.py`: 14 tests for API-Key authentication
  - `tests/test_certificate_export.py`: 12 tests for certificate export
  - `tests/test_sdk_compatibility.py`: 14 tests for SDK compatibility

### Fixed
- **Python 3.13 compatibility**: All tests pass on Python 3.13.2
- **No breaking changes**: Zero modifications required for existing code
- **Enum compatibility**: All trading parameter enums validated

### Migration Guide
1. **Option 1 - Keep using PFX authentication** (no changes required):
   ```bash
   # Your existing .env configuration still works
   FUBON_USERNAME=your_username
   FUBON_PASSWORD=your_password
   FUBON_PFX_PATH=path/to/certificate.pfx
   FUBON_PFX_PASSWORD=pfx_password
   ```

2. **Option 2 - Switch to API-Key authentication** (optional):
   ```bash
   # New API-Key authentication (no PFX file needed)
   FUBON_API_KEY=your_api_key
   FUBON_API_SECRET=your_api_secret
   ```

3. **Upgrade SDK**:
   ```bash
   # Upgrade to SDK v2.2.7
   pip install --upgrade fubon_neo>=2.2.7
   
   # Or install from local wheels
   pip install wheels/fubon_neo-2.2.7-cp37-abi3-<your_platform>.whl
   ```

### Security Notes
- **API-Key authentication**: Requires API-Key申請 from Fubon portal
- **IP whitelisting**: Recommended for production API-Key usage
- **Key rotation**: Follow Fubon's key rotation policy
- **Environment isolation**: Use different API-Keys for dev/staging/prod

### Known Limitations
- **Certificate export**: PKCS#12 format only (PEM not supported)
- **API-Key**: Requires SDK v2.2.7+ (not available in older versions)
- **Backward compatibility**: API-Key credentials not supported by SDK v2.2.4 or earlier

---

## [2.2.3] - 2026-01-24
### Fixed
- 🔧 **MCP 自動註冊**: 修正 VS Code 擴展安裝後 MCP Server 無法自動出現在已註冊列表的問題
- 擴展激活時自動寫入 `mcp.json` 配置，無需用戶手動執行 Configure 命令
- 同步所有版本號 (`package.json`, `__init__.py`, `version_config.json`) 至 2.2.3

### Changed
- 重構 `registerMCPServerProvider()` 函數，新增 `autoRegisterMCPServer()` 自動註冊邏輯
- 改進 inputs 配置，為密碼欄位添加 `password: true` 屬性

## [2.2.1] - 2025-11-24
### Added
- ✅ Normalize SDK responses across services: `_normalize_result` to standardize dict/object/string returns for tools.
- 🧪 New SQLite-backed local cache for historical candles; `_save_to_local_db` and `_get_local_historical_data`.
- 📈 `get_trading_signals` improvements and robust indicator scoring/computation.

### Changed
- 🔧 Replace print(stderr) debug statements with proper `logging` across server components (`server.py`, `utils.py`, `streaming_service.py`, `analysis_service.py`, `market_data_service.py`).
- ♻️ Migration: historical data cache moved from CSV to SQLite and relevant API/data I/O updates.

### Fixed
- 🐛 Improved error handling and SDK result normalization for `query_symbol_snapshot`, `query_symbol_quote`, `margin_quota`, and `daytrade_and_stock_info`.
- ✅ Tests updated/added to cover normalization and SQLite caching. All existing tests now pass.


## [2.1.1] - 2025-11-10

### Added
- 🚀 **Phase 3 Advanced Analysis**: 新增投資組合優化、市場情緒指數生成、套利機會偵測等進階功能
- 📊 **新 MCP 工具**: 添加多項量化交易和風險管理工具
- 🧪 **測試增強**: 新增串流測試和服務測試覆蓋率
- 📚 **文檔更新**: 更新 README 和 Extension 文檔

### Fixed
- 🐛 **Bug 修復**: 修正多個服務和工具的問題

## [2.0.6] - 2025-11-05

### Fixed
- 🐛 **CI Build Error**: Fixed ModuleNotFoundError in GitHub Actions by adding `pip install -e .` to install the package for testing
- 📚 **Documentation Cleanup**: Removed outdated release notes files and redundant installation guide to simplify project structure

## [1.8.6] - 2025-11-04

### Added
- 🚀 **VS Code Extension**: 完整的 VS Code Extension 功能
	- Extension ID: `mofesto.fubon-api-mcp-server`
	- 一鍵啟動/停止/重啟 MCP Server
	- 內建配置管理（帳號、憑證、數據目錄）
	- 安全密碼輸入（不儲存在設定中）
	- 即時日誌輸出面板
	- 命令面板支援（Start/Stop/Restart/Show Logs）
- 🔧 **動態版本管理**: 採用 setuptools-scm 從 Git tags 自動生成版本號
- 📦 **自動化發佈流程**:
	- PyPI 自動發佈（從 GitHub Release 觸發）
	- VS Code Marketplace 自動發佈
	- VSIX 檔案自動附加到 GitHub Release
- 📚 **完整文檔**: 新增發佈指南、使用說明和 Extension 文檔

### Changed
- 版本號管理方式改為動態生成（不再寫死在程式碼中）
- 改善 CI/CD 流程的穩定性和可靠性
- 更新所有文檔以包含 VS Code Extension 資訊

### Fixed
- 修正 Python 3.14 支援問題（移除未發布版本）
- 改善版本號一致性

### Security
- Extension 密碼採用安全輸入方式
- 敏感資訊不儲存在配置檔中


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
