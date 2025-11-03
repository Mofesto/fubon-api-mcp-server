# Fubon MCP Server

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

富邦證券市場資料 MCP (Model Communication Protocol) 伺服器，提供完整的台股交易功能與市場數據查詢。

## ✨ 功能特點

### 🚀 完整交易功能
- ✅ **買賣下單**：支援所有Order參數（market_type、price_type、time_in_force、order_type、user_def）
- ✅ **委託管理**：查詢委託狀態、修改價格/數量、取消委託
- ✅ **批量下單**：並行處理多筆訂單，支援ThreadPoolExecutor
- ✅ **非阻塞模式**：同步/非同步下單操作

### 📊 市場數據
- ✅ **即時行情**：盤中報價、K線、成交明細、分價量表
- ✅ **行情快照**：市場概覽、漲跌幅排行、成交量排行
- ✅ **歷史數據**：52週統計、歷史K線、本地數據快取

### 💰 帳戶資訊
- ✅ **銀行水位**：資金餘額、可用餘額查詢
- ✅ **庫存明細**：實際持股狀況、交易狀態
- ✅ **未實現損益**：浮動盈虧、成本價分析
- ✅ **交割資訊**：應收付金額、結算明細

### 🔄 主動回報
- ✅ **委託回報**：即時委託狀態通知
- ✅ **成交回報**：成交確認與明細
- ✅ **事件通知**：系統狀態、連線狀態
- ✅ **改價/改量回報**：委託變更確認

### 🛡️ 系統穩定性
- ✅ **斷線重連**：自動偵測並恢復WebSocket連線
- ✅ **錯誤處理**：完善的異常處理機制
- ✅ **參數驗證**：輸入驗證與錯誤訊息

## 📋 系統需求

- **Python**: 3.8 或以上版本
- **作業系統**: macOS / Linux / Windows
- **憑證**: 富邦證券電子憑證 (.pfx 文件)
- **網路**: 穩定網路連線

## 🚀 快速開始

### 1. 環境準備

```bash
# 克隆專案
git clone https://github.com/mofesto/fubon-api-mcp-server.git
cd fubon-api-mcp-server

# 建立虛擬環境
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

### 2. 安裝依賴

```bash
# 安裝Python套件
pip install -r requirements.txt

# 安裝富邦Neo SDK
python install_fubon_neo.py
```

**注意**: `fubon_neo` 套件需要從富邦官方網站下載 `.whl` 文件。

### 3. 環境配置

複製並編輯環境變數文件：

```bash
cp .env.example .env
```

編輯 `.env` 文件：

```env
FUBON_USERNAME=您的富邦證券帳號
FUBON_PASSWORD=您的富邦證券密碼
FUBON_PFX_PATH=/path/to/your/certificate.pfx
FUBON_PFX_PASSWORD=您的憑證密碼（如果有）
FUBON_DATA_DIR=./data
```

### 4. 啟動服務

```bash
python server.py
```

### 5. VS Code 配置

在工作區設定中加入 MCP 伺服器：

```json
{
  "mcpServers": {
    "fubon-api-mcp-server": {
      "command": "python",
      "args": ["server.py"],
      "env": {
        "FUBON_USERNAME": "您的帳號",
        "FUBON_PASSWORD": "您的密碼",
        "FUBON_PFX_PATH": "/path/to/certificate.pfx",
        "FUBON_PFX_PASSWORD": "憑證密碼",
        "FUBON_DATA_DIR": "./data"
      }
    }
  }
}
```

## 📖 API 參考

### 交易功能

#### 下單買賣股票

```python
from mcp_fubon import place_order

result = place_order({
    "account": "帳戶號碼",
    "symbol": "2330",           # 股票代碼
    "quantity": 1000,           # 數量 (1000股 = 1張)
    "price": 1500.0,            # 價格
    "buy_sell": "Buy",          # "Buy" 或 "Sell"
    "market_type": "Common",    # 市場別
    "price_type": "Limit",      # 價格類型
    "time_in_force": "ROD",     # 有效期間
    "order_type": "Stock",      # 委託類型
    "user_def": "自定義標記",   # 可選
    "is_non_blocking": False    # 是否非阻塞
})
```

**參數說明**:
- `market_type`: `Common`(一般), `Emg`(緊急), `Odd`(盤後零股)
- `price_type`: `Limit`(限價), `Market`(市價), `LimitUp`(漲停), `LimitDown`(跌停)
- `time_in_force`: `ROD`(當日), `IOC`(立即成交否則取消), `FOK`(全部成交否則取消)
- `order_type`: `Stock`(現股), `Margin`(融資), `Short`(融券), `DayTrade`(當沖)

#### 批量下單

```python
from mcp_fubon import batch_place_order

result = batch_place_order({
    "account": "帳戶號碼",
    "orders": [
        {
            "symbol": "2330",
            "quantity": 1000,
            "price": 1500.0,
            "buy_sell": "Buy",
            "user_def": "訂單1"
        },
        {
            "symbol": "2881",
            "quantity": 1000,
            "price": 66.0,
            "buy_sell": "Buy",
            "user_def": "訂單2"
        }
    ],
    "max_workers": 10  # 最大並行數量
})
```

#### 委託管理

```python
# 查詢委託結果
from mcp_fubon import get_order_results
orders = get_order_results({"account": "帳戶號碼"})

# 修改價格
from mcp_fubon import modify_price
result = modify_price({
    "account": "帳戶號碼",
    "order_no": "委託單號",
    "new_price": 1505.0
})

# 修改數量
from mcp_fubon import modify_quantity
result = modify_quantity({
    "account": "帳戶號碼",
    "order_no": "委託單號",
    "new_quantity": 500
})

# 取消委託
from mcp_fubon import cancel_order
result = cancel_order({
    "account": "帳戶號碼",
    "order_no": "委託單號"
})
```

### 帳戶資訊

#### 完整帳戶概覽

```python
from mcp_fubon import get_account_info

account_info = get_account_info({"account": "帳戶號碼"})
# 返回: 基本資訊 + 銀行水位 + 庫存 + 未實現損益 + 交割資訊
```

#### 銀行水位查詢

```python
from mcp_fubon import get_bank_balance

balance = get_bank_balance({"account": "帳戶號碼"})
# 返回: 總餘額、可用餘額、貨幣種類等
```

#### 庫存明細

```python
from mcp_fubon import get_inventory

inventory = get_inventory({"account": "帳戶號碼"})
# 返回: 每檔股票的實際持股狀況
```

#### 未實現損益

```python
from mcp_fubon import get_unrealized_pnl

pnl = get_unrealized_pnl({"account": "帳戶號碼"})
# 返回: 每檔股票的盈虧狀況
```

### 市場數據

#### 即時行情

```python
from mcp_fubon import get_intraday_quote

quote = get_intraday_quote({"symbol": "2330"})
# 返回: 最新價、漲跌、成交量等
```

#### 歷史K線

```python
from mcp_fubon import get_historical_candles

candles = get_historical_candles({
    "symbol": "2330",
    "from_date": "2024-01-01",
    "to_date": "2024-12-31"
})
```

#### 行情快照

```python
from mcp_fubon import get_snapshot_quotes

snapshot = get_snapshot_quotes({"market": "TSE"})
# 返回: 全市場股票行情快照
```

### 主動回報

```python
# 委託回報
from mcp_fubon import get_order_reports
reports = get_order_reports({"limit": 10})

# 成交回報
from mcp_fubon import get_filled_reports
filled = get_filled_reports({"limit": 10})

# 事件通知
from mcp_fubon import get_event_reports
events = get_event_reports({"limit": 10})

# 所有回報
from mcp_fubon import get_all_reports
all_reports = get_all_reports({"limit": 5})
```

## 🧪 測試與驗證

### 運行完整測試套件

```bash
# API 功能測試 (17項測試)
python test_fubon_api.py

# 交易流程測試
python test_trading_workflow.py

# 帳戶資訊測試
python test_account_balance.py

# 行情數據測試
python test_snapshot_actives.py
```

### 測試結果

- ✅ **API 連線**: 100% 成功
- ✅ **交易功能**: 完整支持買賣下單、委託管理
- ✅ **帳戶查詢**: 銀行水位、庫存、損益查詢正常
- ✅ **市場數據**: 即時行情、歷史數據正常
- ✅ **主動回報**: 委託、成交、事件通知正常
- ✅ **斷線重連**: 自動重連機制正常

## 🔧 開發與部署

### 專案結構

```
fubon-api-mcp-server/
├── fubon_mcp/              # 主要程式碼包
│   ├── __init__.py        # 包初始化
│   └── server.py          # MCP 伺服器主程式
├── examples/               # 示範腳本
│   ├── demo_*.py          # 各功能演示
│   └── debug_*.py         # 除錯腳本
├── tests/                  # 測試套件
│   ├── __init__.py        # 測試包
│   ├── conftest.py        # 測試配置和fixtures
│   ├── test_*.py          # 各模組測試
│   └── key/               # 測試憑證
├── data/                   # 數據快取目錄
├── log/                    # 日誌檔案
├── .env                    # 環境變數配置
├── .env.example           # 環境變數範例
├── .gitignore             # Git 忽略規則
├── requirements.txt       # Python 依賴
├── setup.py               # 安裝腳本
├── pytest.ini             # 測試配置
├── run_tests.py           # 測試運行器
└── README.md              # 專案說明
```

### 環境變數說明

| 變數名稱 | 必填 | 說明 |
|---------|------|------|
| `FUBON_USERNAME` | ✅ | 富邦證券帳號 |
| `FUBON_PASSWORD` | ✅ | 登入密碼 |
| `FUBON_PFX_PATH` | ✅ | 電子憑證路徑 (.pfx) |
| `FUBON_PFX_PASSWORD` | ❌ | 憑證密碼（如果有） |
| `FUBON_DATA_DIR` | ❌ | 數據快取目錄（預設: ./data） |

### 安全注意事項

- 🔒 **敏感資訊**: 密碼和憑證檔案請勿提交至版本控制
- 🔒 **環境變數**: 使用 `.env` 文件管理敏感配置
- 🔒 **權限控制**: 限制憑證檔案的存取權限
- 🔒 **網路安全**: 確保網路連線的安全性

## 📝 更新日誌

### v1.6.0 (2025-11-03)
- 🐛 **帳戶查詢修正**: 修正正式環境帳戶資訊查詢問題
- 🔧 **API 調用優化**: 修正庫存、損益、結算資訊的 API 調用方式
- ✅ **測試覆蓋完善**: 所有帳戶資訊功能測試通過 (7/7)
- 📊 **正式環境支援**: 確認正式環境支持所有查詢功能

### v1.5.0 (2025-11-03)
- 🎯 **完整交易功能**: 實現完整的買賣流程
- 🔧 **參數驗證增強**: 支持所有交易參數
- 📊 **測試套件擴展**: 新增完整交易流程測試
- 📚 **文檔完善**: 詳細API說明和使用範例

### v1.4.0 (2025-10-XX)
- 🔄 **斷線重連**: 自動WebSocket重連機制
- 🛡️ **系統穩定性**: 完善的錯誤處理
- 📈 **測試覆蓋**: 17項完整測試

### v1.3.0 (2025-10-XX)
- 📡 **主動回報**: 委託、成交、事件通知
- 🔍 **即時監控**: 交易狀態追蹤

### v1.2.0 (2025-10-XX)
- 💰 **帳戶資訊**: 完整庫存和損益查詢
- 📊 **財務分析**: 成本價和盈虧計算

### v1.1.0 (2025-10-XX)
- 🏦 **銀行水位**: 資金餘額查詢
- 💳 **帳戶管理**: 基本帳戶資訊

### v1.0.0 (2025-09-XX)
- 🚀 **初始版本**: 基礎交易和行情功能
- 📦 **MCP整合**: Model Communication Protocol支持

## 🤝 貢獻指南

歡迎貢獻！請遵循以下步驟：

1. Fork 此專案
2. 建立功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交變更 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 開啟 Pull Request

### 開發環境設定

```bash
# 安裝開發依賴
pip install -r requirements-dev.txt

# 運行測試
python -m pytest

# 代碼格式化
black .
flake8 .
```

## 📄 授權條款

本專案採用 [MIT License](LICENSE) 授權。

## ⚠️ 免責聲明

- 📢 **投資風險**: 股票交易具有風險，請謹慎投資
- 📢 **使用責任**: 用戶需自行承擔使用本軟體的風險
- 📢 **法規遵循**: 請遵守相關金融法規和平台使用條款
- 📢 **技術支援**: 本專案不提供官方技術支援

## 👥 作者與致謝

- **開發者**: Mofesto.Cui
- **貢獻者**: 歡迎所有貢獻者

---

⭐ 如果這個專案對您有幫助，請給我們一個星標！