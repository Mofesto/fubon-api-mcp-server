# GitHub Copilot Instructions - Fubon API MCP Server

## 專案概述

這是一個基於 [富邦證券官方 Trade API](https://www.fbs.com.tw/TradeAPI/docs/) 的 **MCP (Model Context Protocol) 服務器**，將富邦證券的 Python SDK (`fubon_neo`) 包裝為 MCP 協議介面，提供完整的台股交易、行情查詢和帳戶管理功能。

**核心依賴**: `fubon_neo` (富邦官方 SDK)、`fastmcp` (MCP 框架)、`pandas` (數據處理)

## 架構設計

### 單體式 MCP 服務器
- **主程式**: `fubon_api_mcp_server/server.py` (1800+ 行) - 所有功能集中在一個檔案
- **配置模組**: `config.py` - 環境變數和全局配置
- **工具模組**: `utils.py` - 共用輔助函數 (帳戶驗證、錯誤處理、API 調用封裝)

### 全局狀態管理
```python
# server.py 中的全局變數
sdk = None        # FubonSDK 實例 (登入後初始化)
accounts = None   # 帳戶列表 (登入後取得)
reststock = None  # REST API 客戶端 (用於行情查詢)
```

**重要**: 所有 MCP tools 都依賴這些全局變數，在 `main()` 函數中初始化一次後全程使用。

### MCP Tools 組織結構
服務器提供 **30+ MCP tools**，使用 `@mcp.tool()` 裝飾器註冊：

1. **交易功能** (8 tools): 下單、改價、改量、取消、批量下單
2. **帳戶資訊** (4 tools): 銀行水位、庫存、損益、結算
3. **市場數據** (10 tools): 即時行情、歷史 K 線、行情快照、排行榜
4. **主動回報** (5 tools): 委託回報、成交回報、事件通知
5. **數據管理** (3 tools): 本地快取、歷史數據處理

### 資源端點
```python
@mcp.resource("twstock://{symbol}/historical")
def get_stock_resource(symbol: str) -> str:
    # 提供股票歷史數據的 MCP 資源端點
```

## 關鍵開發模式

### 1. 帳戶驗證模式 (所有交易/查詢前必須)
```python
# utils.py 提供統一的帳戶驗證
def validate_and_get_account(account: str) -> tuple[Optional[Any], Optional[str]]:
    # 在 MCP tool 調用時重新初始化 SDK (因為 MCP 運行在獨立上下文)
    # 從環境變數載入憑證 -> 登入 -> 查找對應帳戶對象
    # 返回: (account_obj, error_msg)
```

**使用模式**:
```python
@mcp.tool()
def place_order(order_data: dict) -> dict:
    account_obj, error = validate_and_get_account(order_data["account"])
    if error:
        return {"status": "error", "message": error}
    # 繼續執行...
```

### 2. 錯誤處理裝飾器
```python
# utils.py
@handle_exceptions
def some_function():
    # 全局異常處理，自動捕獲並輸出詳細 traceback 到 stderr
```

### 3. 安全 API 調用模式
```python
# utils.py
def _safe_api_call(api_func: Callable, error_prefix: str):
    """統一處理 API 調用，檢查 result.is_success"""
    result = api_func()
    if result and hasattr(result, "is_success") and result.is_success:
        return result.data
    return None  # 或錯誤訊息
```

### 4. 批量並行處理 (ThreadPoolExecutor)
```python
@mcp.tool()
def batch_place_order(params: dict) -> dict:
    with concurrent.futures.ThreadPoolExecutor(max_workers=params.get("max_workers", 10)) as executor:
        futures = [executor.submit(place_single_order, order) for order in orders]
        results = [future.result() for future in futures]
    return _summarize_batch_results(results)
```

### 5. 本地數據快取策略
```python
# 歷史 K 線數據儲存在 BASE_DATA_DIR/{symbol}.csv
# 讀取時先檢查本地快取，不存在則調用 API 並保存
def read_local_stock_data(symbol: str) -> Optional[pd.DataFrame]:
    file_path = BASE_DATA_DIR / f"{symbol}.csv"
    if file_path.exists():
        return pd.read_csv(file_path, parse_dates=["date"])
    return None
```

## 環境配置與憑證管理

### 必要環境變數 (.env)
```bash
FUBON_USERNAME=您的帳號
FUBON_PASSWORD=您的密碼
FUBON_PFX_PATH=/path/to/certificate.pfx  # 電子憑證
FUBON_PFX_PASSWORD=憑證密碼 (選填)
FUBON_DATA_DIR=./data  # 本地快取目錄
```

### VS Code Extension 整合
- Extension 位於 `vscode-extension/` 目錄
- 使用 Node.js/JavaScript，透過 `child_process.spawn` 啟動 Python MCP 服務器
- Extension 命令: Start/Stop/Restart/ShowLogs/Configure
- **安全設計**: 密碼不儲存在 settings.json，每次啟動時輸入

## 測試策略

### 測試結構 (`tests/`)
- **conftest.py**: 提供 fixtures (mock_accounts, mock_sdk, mock_server_globals)
- **test_*.py**: 各模組單元測試 (使用 pytest + pytest-mock)
- **覆蓋率目標**: >80% (當前 28%)

### Mock 模式
```python
@pytest.fixture
def mock_server_globals(mock_accounts, mock_sdk):
    """Mock 全局變數進行測試"""
    with patch("fubon_api_mcp_server.server.accounts", mock_accounts), \
         patch("fubon_api_mcp_server.server.sdk", mock_sdk):
        yield
```

### 運行測試
```bash
# 完整測試 + 覆蓋率
pytest --cov=fubon_api_mcp_server --cov-report=html

# 特定測試
pytest tests/test_utils.py::TestHandleExceptions -v
```

## 版本管理與發布

### 動態版本管理 (setuptools-scm)
- **版本來源**: Git tags (`v*.*.*`)
- **自動生成**: `fubon_api_mcp_server/_version.py` (不要手動編輯)
- **配置文件**: `scripts/version_config.json` (集中管理所有版本資訊)

### 自動化發布流程
```powershell
# 發布新版本 (會自動推送到 PyPI 和 VS Code Marketplace)
.\scripts\release.ps1 -BumpType patch|minor|major

# 腳本執行:
# 1. 運行測試
# 2. 更新所有文件版本號 (README, package.json, CHANGELOG)
# 3. 生成 Release Notes
# 4. 創建 Git tag
# 5. 推送觸發 GitHub Actions
```

### CI/CD Pipeline (`.github/workflows/auto-release.yml`)
1. **test** job: 測試 Python 3.10-3.13
2. **version** job: 計算新版本號
3. **pypi-release** job: 發布到 PyPI
4. **vscode-release** job: 發布到 VS Code Marketplace
5. **github-release** job: 創建 GitHub Release

## 常見開發任務

### 新增 MCP Tool
1. 在 `server.py` 添加函數，使用 `@mcp.tool()` 裝飾器
2. 定義 Pydantic 模型驗證輸入參數
3. 調用 `validate_and_get_account()` 驗證帳戶
4. 使用 `_safe_api_call()` 封裝 API 調用
5. 返回統一格式: `{"status": "success|error", "data": ..., "message": ...}`

### 新增測試
1. 在 `tests/` 創建 `test_<module>.py`
2. 使用 `conftest.py` 提供的 fixtures
3. Mock 全局變數和外部依賴
4. 運行 `pytest` 驗證

### 修改版本號
```powershell
# 更新 scripts/version_config.json
# 然後運行:
.\scripts\update_version.ps1 -Version x.y.z
```

### 優雅關閉處理
```python
# server.py main() 中處理 KeyboardInterrupt
except KeyboardInterrupt:
    print("收到中斷信號，正在優雅關閉...", file=sys.stderr)
    if sdk:
        result = sdk.logout()
    sys.exit(0)
```

## 專案特定慣例

### 中文輸出編碼
```python
# server.py 開頭強制 UTF-8 編碼
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
```

### 代碼格式化
- **Black**: line-length=127, 排除 `_version.py`
- **isort**: profile="black"
- **flake8**: 只檢查嚴重錯誤 (E9, F63, F7, F82)

### 類型檢查 (mypy)
- 逐步啟用嚴格模式 (當前階段 2)
- 忽略 `fubon_neo`、`mcp`、`fastmcp` 的類型檢查

## 外部整合點

### 富邦官方 SDK (`fubon_neo`)
- 安裝: `pip install fubon-neo` 或使用 `wheels/` 中的 `.whl` 檔案
- 主要模組: `FubonSDK`, `Order`, `BSAction`, `MarketType`, 等常數
- 官方文檔: https://www.fbs.com.tw/TradeAPI/docs/

### VS Code MCP 整合
- Extension 透過 `package.json` 中的 `contributes.modelContextProtocol` 註冊 MCP Server
- 使用 `python -m fubon_api_mcp_server.server` 啟動
- GitHub Copilot 可透過 MCP 協議調用所有 tools

## 除錯技巧

### 查看 MCP Server 日誌
```bash
# VS Code Extension 啟動時的日誌
# 在 VS Code: View > Output > Fubon MCP Server

# 或直接運行 server
python -m fubon_api_mcp_server.server
```

### 測試單一 Tool
```python
# examples/ 目錄包含各功能的演示腳本
python examples/demo_bank_balance.py
python examples/demo_inventory.py
```

### 常見錯誤
- **ModuleNotFoundError**: 使用 `pip install -e .` 可編輯安裝
- **帳戶認證失敗**: 檢查 `.env` 檔案和憑證路徑
- **API 調用失敗**: 確認 `sdk.init_realtime()` 已執行

## 效能考量

- **並行下單**: 使用 `ThreadPoolExecutor` 限制 max_workers 避免過載
- **本地快取**: 歷史數據優先使用本地 CSV，減少 API 調用
- **全局連線**: SDK 和 WebSocket 連線在 main() 初始化一次，避免重複登入

---

**提醒**: 此專案為非官方社群開發，使用前請參考[富邦官方文檔](https://www.fbs.com.tw/TradeAPI/docs/)了解 API 規範和限制。
