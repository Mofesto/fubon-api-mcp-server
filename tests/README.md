# 測試文檔

本專案使用 `pytest` 作為測試框架，提供完整的測試套件來驗證富邦MCP服務器的功能。

## 測試結構

```
tests/
├── __init__.py              # 測試包配置
├── conftest.py              # 共享fixtures和配置
├── test_api_connection.py   # API連線測試
├── test_market_data.py      # 市場數據測試
├── test_account_info.py     # 帳戶資訊測試
├── test_trading.py          # 交易功能測試
└── test_integration.py      # 整合測試
```

## 運行測試

### 基本運行

```bash
# 運行所有測試
python -m pytest

# 或使用運行器腳本
python run_tests.py all
```

### 分類運行

```bash
# 單元測試（API連線和市場數據）
python run_tests.py unit

# 帳戶資訊測試
python run_tests.py account

# 交易功能測試（需要特殊啟用）
python run_tests.py trading

# 整合測試
python run_tests.py integration
```

### 詳細輸出

```bash
# 詳細輸出
python -m pytest --verbose -s

# 或
python run_tests.py all --verbose
```

### 覆蓋率報告

```bash
# 生成覆蓋率報告
python -m pytest --cov=server --cov-report=html

# 或
python run_tests.py all --coverage
```

## 測試Fixtures

### 共享Fixtures (`conftest.py`)

- `fubon_credentials`: 富邦API認證資訊
- `fubon_sdk`: 初始化後的SDK實例
- `rest_client`: REST API客戶端
- `test_account`: 測試帳戶號碼
- `data_dir`: 測試數據目錄

### 使用範例

```python
def test_example(fubon_sdk, test_account):
    """測試範例"""
    assert fubon_sdk is not None
    assert test_account is not None
```

## 測試分類

### 🔗 API連線測試 (`test_api_connection.py`)

- SDK初始化
- 登入驗證
- 即時連線初始化
- REST客戶端可用性
- 環境變數載入

### 📊 市場數據測試 (`test_market_data.py`)

- 股票基本資料
- 即時報價
- 盤中K線
- 成交明細
- 分價量表
- 行情快照
- 漲跌幅排行
- 成交量排行
- 歷史K線
- 歷史統計

### 💰 帳戶資訊測試 (`test_account_info.py`)

- 銀行水位查詢
- 庫存資訊
- 未實現損益
- 完整帳戶資訊
- 交割資訊
- 數據結構驗證

### 💼 交易功能測試 (`test_trading.py`)

- 下單功能結構
- 委託結果查詢
- 價格/數量修改
- 批量下單
- 取消委託
- 參數驗證

### 🔄 整合測試 (`test_integration.py`)

- 完整工作流程
- 數據一致性
- 錯誤處理
- API回應格式
- 效能測試
- 並發請求模擬

## 測試配置

### pytest.ini

```ini
[tool:pytest]
testpaths = tests
addopts = --verbose --tb=short --strict-markers
markers =
    slow: 標記慢速測試
    integration: 標記整合測試
    trading: 標記交易相關測試
```

### 自定義標記

- `@pytest.mark.slow`: 慢速測試
- `@pytest.mark.integration`: 整合測試
- `@pytest.mark.trading`: 交易相關測試

## 測試環境配置

### 正式環境 vs 測試環境

本專案支援富邦證券的正式環境和測試環境：

#### 正式環境
- URL: 預設 WebSocket 連線
- 帳戶: 真實交易帳戶
- 功能: 完整功能可用

#### 測試環境
- URL: `wss://neoapitest.fbs.com.tw/TASP/XCPXWS`
- SDK 初始化: `FubonSDK(30, 2, url="wss://neoapitest.fbs.com.tw/TASP/XCPXWS")`
- 帳戶: 測試帳號（憑證ID），密碼: `12345678`
- 功能限制:
  - 帳務資訊可能不正確
  - 部分 REST API 可能不可用
  - 即時連線可能受限
- 開盤時間: 09:30~19:00
- 預設庫存:
  - 2002 (融券): 500張
  - 2330 (融資): 500張
  - 2881 (現貨): 500張
  - 0050 (現貨): 500張

### 切換測試環境

1. 更新 `conftest.py` 中的 SDK 初始化
2. 設置測試憑證路徑
3. 更新環境變數使用測試帳號

```python
# 測試環境 SDK 初始化
sdk = FubonSDK(30, 2, url="wss://neoapitest.fbs.com.tw/TASP/XCPXWS")
```

### 測試環境注意事項

- 行情資料即時但中台參考價格不即時更新
- 可通過下兩張反向單測試成交
- 測試帳號庫存每日重設
- 使用 `user_def` 欄位區別委託單

### 跳過條件

- 缺少必要環境變數時自動跳過
- API不可用時跳過相關測試
- 非交易時段跳過交易測試

## CI/CD 整合

### GitHub Actions 範例

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    - name: Run tests
      run: python -m pytest --cov=server --cov-report=xml
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

## 測試最佳實務

### 編寫測試

1. **使用描述性名稱**: `test_get_bank_balance_returns_valid_data`
2. **單一責任**: 每個測試只驗證一個行為
3. **獨立性**: 測試之間不互相依賴
4. **使用fixtures**: 重用設置和清理邏輯

### 範例測試

```python
import pytest

class TestBankBalance:
    def test_successful_balance_retrieval(self, fubon_sdk, test_account):
        """測試成功獲取銀行餘額"""
        from server import get_bank_balance

        result = get_bank_balance({'account': test_account})

        assert result['status'] == 'success'
        assert 'data' in result
        assert result['data'].balance > 0

    def test_invalid_account_returns_error(self, fubon_sdk):
        """測試無效帳戶返回錯誤"""
        from server import get_bank_balance

        result = get_bank_balance({'account': 'INVALID'})

        assert result['status'] == 'error'
```

## 故障排除

### 常見問題

1. **環境變數缺失**
   ```
   解決方案：檢查 .env 文件和環境變數設定
   ```

2. **API連線失敗**
   ```
   解決方案：檢查網路連線和憑證有效性
   ```

3. **測試跳過**
   ```
   解決方案：某些測試在非交易時段會自動跳過
   ```

4. **效能問題**
   ```
   解決方案：使用 -k 選項運行特定測試
   ```

### 調試選項

```bash
# 運行特定測試
python -m pytest tests/test_account_info.py::TestAccountInfo::test_get_bank_balance -v -s

# 只運行失敗的測試
python -m pytest --lf

# 顯示最慢的測試
python -m pytest --durations=10
```