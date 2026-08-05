# Fubon MCP Server

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![PyPI version](https://img.shields.io/pypi/v/fubon-api-mcp-server?label=PyPI)](https://pypi.org/project/fubon-api-mcp-server/)
[![VS Code Extension](https://img.shields.io/visual-studio-marketplace/v/mofesto.fubon-api-mcp-server?label=VS%20Code%20Extension)](https://marketplace.visualstudio.com/items?itemName=mofesto.fubon-api-mcp-server)
[![PyPI downloads](https://img.shields.io/pypi/dm/fubon-api-mcp-server.svg)](https://pypi.org/project/fubon-api-mcp-server/)
[![codecov](https://codecov.io/gh/Mofesto/fubon-api-mcp-server/branch/main/graph/badge.svg)](https://codecov.io/gh/Mofesto/fubon-api-mcp-server)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

富邦證券市場資料 MCP (Model Context Protocol) 伺服器，提供完整的台股交易功能與市場數據查詢。

本專案目前使用官方 MCP Python SDK `mcp 2.0.x`，對應 MCP protocol revision `2026-07-28`。服務以 `MCPServer` 註冊工具與 prompts；stdio 是桌面 Host 的預設傳輸，Streamable HTTP 可透過 `FUBON_MCP_STATELESS_HTTP=true` 啟用新版無狀態請求模型。

## ✨ 功能特點

### 🚀 完整交易功能
- ✅ **買賣下單**：支援所有Order參數（market_type、price_type、time_in_force、order_type、user_def）
- ✅ **委託管理**：查詢委託狀態、修改價格/數量、取消委託
- ✅ **批量下單**：並行處理多筆訂單，支援ThreadPoolExecutor
- ✅ **條件單**：單一/多條件單、停損停利（TPSL with OCO）

#### 當沖條件單（Day-Trade Condition）

支援「當沖單一條件單」：觸發主單後，於指定時間前自動回補，可選擇加入停損停利（OCO）。

重要注意事項：
- 停損利設定僅為觸發送單，不保證必定回補成功，需視市場狀況調整
- 停損利委託類別需符合當日沖銷交易規則（例如信用交易使用資券互抵）
- 主單完全成交後，停損停利才會啟動

使用（MCP tool `place_daytrade_condition_order`）：

```python
from fubon_api_mcp_server.server import place_daytrade_condition_order

result = place_daytrade_condition_order({
    "account": "1234567",
    "stop_sign": "Full",
    "end_time": "130000",  # 父單洗價結束時間
    "condition": {
        "market_type": "Reference",
        "symbol": "2881",
        "trigger": "MatchedPrice",
        "trigger_value": "66",
        "comparison": "LessThan"
    },
    "order": {
        "buy_sell": "Buy",
        "symbol": "2881",
        "price": "66",
        "quantity": 1000,
        "market_type": "Common",
        "price_type": "Limit",
        "time_in_force": "ROD",
        "order_type": "Stock"
    },
    "daytrade": {
        "day_trade_end_time": "131500",  # 130100 ~ 132000
        "auto_cancel": True,
        "price": "",
        "price_type": "Market"
    },
    "tpsl": {  # 選填
        "stop_sign": "Full",
        "tp": {"time_in_force": "ROD", "price_type": "Limit", "order_type": "Stock", "target_price": "85", "price": "85"},
        "sl": {"time_in_force": "ROD", "price_type": "Limit", "order_type": "Stock", "target_price": "60", "price": "60"},
        "end_date": "20240517",
        "intraday": True
    },
    "fix_session": True
})
```

回傳：`{"status":"success","data":{"guid":"..."},...}`，`guid` 為條件單號。

查詢當沖條件單（依 guid）：

```python
from fubon_api_mcp_server.server import get_daytrade_condition_by_id

res = get_daytrade_condition_by_id({
    "account": "1234567",
    "guid": "8ff3472b-185a-488c-be5a-b478deda080c"
})

if res["status"] == "success":
    detail = res["data"]  # 包含 guid、status、detail_records、tpslRecord 等欄位
```

當沖多條件單（multi_condition_day_trade）：

```python
from fubon_api_mcp_server.server import place_daytrade_multi_condition_order

payload = {
    "account": "1234567",
    "stop_sign": "Full",
    "end_time": "130000",
    "conditions": [
        {"market_type": "Reference", "symbol": "2881", "trigger": "MatchedPrice", "trigger_value": "66", "comparison": "LessThan"},
        {"market_type": "Reference", "symbol": "2881", "trigger": "TotalQuantity", "trigger_value": "8000", "comparison": "LessThan"}
    ],
    "order": {"buy_sell": "Buy", "symbol": "2881", "price": "66", "quantity": 1000, "market_type": "Common", "price_type": "Limit", "time_in_force": "ROD", "order_type": "Stock"},
    "daytrade": {"day_trade_end_time": "131500", "auto_cancel": True, "price": "", "price_type": "Market"},
    "tpsl": {"stop_sign": "Full", "tp": {"time_in_force": "ROD", "price_type": "Limit", "order_type": "Stock", "target_price": "85", "price": "85"}, "sl": {"time_in_force": "ROD", "price_type": "Limit", "order_type": "Stock", "target_price": "60", "price": "60"}, "end_date": "20240517", "intraday": True},
    "fix_session": True
}

res = place_daytrade_multi_condition_order(payload)
```

移動鎖利條件單（trail_profit）：

```python
from fubon_api_mcp_server.server import place_trail_profit

res = place_trail_profit({
    "account": "1234567",
    "start_date": "20240427",
    "end_date": "20240516",
    "stop_sign": "Full",
    "trail": {
        "symbol": "2330",
        "price": "860",          # 基準價（至多小數兩位）
        "direction": "Up",        # Up / Down
        "percentage": 5,
        "buy_sell": "Buy",
        "quantity": 2000,
        "price_type": "MatchedPrice",
        "diff": 5,
        "time_in_force": "ROD",
        "order_type": "Stock"
    }
})
```

注意：TrailOrder 基準價 `price` 只可輸入至多小數點後兩位，超出可能造成洗價失敗（本工具已做基本檢核）。

查詢有效移動鎖利（get_trail_order）：

```python
from fubon_api_mcp_server.server import get_trail_order

res = get_trail_order({
    "account": "1234567"
})

if res["status"] == "success":
    trails = res["data"]  # List[ConditionDetail]，已展開為 dict
```
- ✅ **非阻塞模式**：同步/非同步下單操作

## 參數對照表（重點）

- ConditionArgs
    - market_type: Reference, Scheduled
    - trigger: BidPrice, AskPrice, MatchedPrice, TotalQuantity, Time
    - comparison: LessThan, LessThanOrEqual, Equal, GreaterThan, GreaterThanOrEqual
- ConditionOrderArgs
    - market_type: Common, Emg, Odd
    - price_type: Limit, Market, LimitUp, LimitDown
    - time_in_force: ROD, IOC, FOK
    - order_type: Stock, Margin, Short, DayTrade
- TimeSliceSplitArgs（分時分量）
    - method: Type1, Type2, Type3（Type2/Type3 需提供 `end_time`）
    - interval: 正整數（秒）
    - single_quantity: 正整數（股）
    - total_quantity: 選填（股，若提供需大於 single_quantity）
- StopSign: Full, Partial, UntilEnd

以上皆對應 `fubon_neo.constant` 之列舉，傳入時請使用成員名稱（字串）。

### 📊 市場數據
- ✅ **即時行情**：盤中報價、K線、成交明細、分價量表
- ✅ **行情快照**：市場概覽、漲跌幅排行、成交量排行
- ✅ **歷史數據**：52週統計、歷史K線、本地數據快取、還原股價與 K 線欄位/排序選項
- ✅ **股務事件**：資本變動、除權息、申請上市櫃公司資料（SDK v2.2.8）

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

### 🤖 Phase 3: 高級分析與量化交易
- ✅ **8項高級MCP提示**：投資組合績效分析、進階風險管理、投資組合優化、市場情緒分析、算法策略建構、期權策略優化、期貨價差分析、波動率交易顧問
- ✅ **6項量化交易工具**：投資組合VaR計算、投資組合壓力測試、投資組合配置優化、績效歸因分析、套利機會偵測、市場情緒指數生成

#### 高級分析提示（Advanced Analysis Prompts）
- ✅ **performance_analytics**：全面投資組合績效分析，包含Sharpe比率、Sortino比率、最大回撤等指標
- ✅ **advanced_risk_management**：多因子風險評估，包含市場風險、信用風險、流動性風險分析
- ✅ **portfolio_optimization**：現代投資組合理論（MPT）基礎的資產配置優化
- ✅ **market_sentiment_analysis**：多維度市場情緒分析，整合新聞、社交媒體、技術指標
- ✅ **algorithmic_strategy_builder**：量化策略開發，支援均值回歸、動量策略、統計套利
- ✅ **options_strategy_optimizer**：期權Greeks分析，包含Delta、Gamma、Theta、Vega、Rho計算
- ✅ **futures_spread_analyzer**：期貨價差分析，包含跨期價差、跨商品價差、統計套利機會
- ✅ **volatility_trading_advisor**：波動率基礎策略，包含VIX指數分析、隱含波動率、實現波動率

#### 量化交易工具（Quantitative Trading Tools）
- ✅ **calculate_portfolio_var**：投資組合風險價值（VaR）計算，多種方法（歷史模擬、參數法、蒙特卡洛）
- ✅ **run_portfolio_stress_test**：投資組合壓力測試，模擬極端市場狀況下的表現
- ✅ **optimize_portfolio_allocation**：投資組合配置優化，使用MPT和Black-Litterman模型
- ✅ **calculate_performance_attribution**：績效歸因分析，分解收益來源（股票選擇、資產配置、時機選擇）
- ✅ **detect_arbitrage_opportunities**：套利機會偵測，包含統計套利、期貨現貨套利、期權套利
- ✅ **generate_market_sentiment_index**：市場情緒指數生成，整合多種情緒指標的綜合指數

## � 與富邦證券官方 API 的關係

本專案是基於 [**富邦證券官方 Trade API**](https://www.fbs.com.tw/TradeAPI/docs/welcome/) 開發的 MCP (Model Context Protocol) 服務器包裝器：

### 📚 官方 API 說明
- **官方文檔**: https://www.fbs.com.tw/TradeAPI/docs/welcome/
- **核心依賴**: `fubon_neo` Python SDK（由富邦證券官方提供）
- **支援功能**: 完整的台股交易、行情數據、帳戶管理功能

### 🔄 功能對應
| MCP 服務器功能 | 官方 API 對應 |
|---------------|---------------|
| 買賣下單 | `fubon_neo.api.place_order()` |
| 委託管理 | `fubon_neo.api.modify_order()` / `cancel_order()` |
| 市場數據 | `fubon_neo.api.get_snapshot()` / `get_candles()` |
| 帳戶資訊 | `fubon_neo.api.get_account_balance()` / `get_inventory()` |
| 主動回報 | `fubon_neo.api.get_order_reports()` / WebSocket |

### 🎯 專案定位
- **非官方產品**: 本專案為社群開發的 MCP 整合方案
- **API 橋接**: 將富邦官方 API 封裝為 MCP 協議介面
- **相容性**: 完全相容官方 API 的所有功能和參數
- **增強功能**: 新增批量處理、快取優化、非阻塞操作等

**重要提醒**: 使用本專案前，請先參考[官方 API 文檔](https://www.fbs.com.tw/TradeAPI/docs/welcome/)了解詳細的 API 使用規範和限制。

## �📋 系統需求

- **Python**: 3.10 或以上版本
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

#### 方式一：使用 pip 安裝（推薦）

```bash
# 安裝本專案
pip install fubon-api-mcp-server

# 安裝富邦官方 SDK
pip install fubon-neo
```

#### 方式二：從原始碼安裝

```bash
# 克隆專案
git clone https://github.com/mofesto/fubon-api-mcp-server.git
cd fubon-api-mcp-server

# 安裝Python套件
pip install -r requirements.txt

# 安裝富邦Neo SDK
python install_fubon_neo.py
```

**注意**: 
- `fubon-neo` 套件需要從富邦官方網站下載 `.whl` 文件
- 或者直接使用 `pip install fubon-neo`（如果已上傳到 PyPI）
- 本專案的 MCP 服務器功能依賴 `fubon-neo` 作為底層 API 橋接

### 3. 環境配置

#### 方式一：傳統 PFX 憑證認證（Traditional PFX Certificate Authentication）

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

#### 方式二：API-Key 認證（API-Key Authentication）✨ SDK v2.2.8+

**適用場景**：
- 🔐 需要 IP 白名單控制的自動化交易
- 🤖 CI/CD 環境中的程式化交易
- ☁️ 以網頁憑證搭配 API Key 登入
- 🔄 需要快速輪換憑證的場景

**步驟 1：申請 API Key / Apply for API Key**

前往富邦證券 API 交易平台申請 API Key：
Visit Fubon Securities API trading platform to apply for an API Key:

https://www.fbs.com.tw/TradeAPI/docs/key/

**步驟 2：設定環境變數 / Set Environment Variables**

編輯 `.env` 文件：

```env
# API-Key 認證（SDK v2.2.8+）
FUBON_USERNAME=您的富邦證券帳號（API Key 登入的 personal_id）
FUBON_API_KEY=your_api_key_here
FUBON_PFX_PATH=/path/to/exported/web-certificate.pfx
FUBON_PFX_PASSWORD=您的憑證密碼
FUBON_DATA_DIR=./data
```

v2.2.8 的 API-Key 登入會呼叫 `apikey_login(personal_id, api_key, cert_path, cert_password)`。
請先在富邦金鑰管理頁申請網頁憑證並匯出 PFX；API Secret 僅在申請頁顯示，不是此 SDK 登入方法的參數。

**步驟 3：啟動服務 / Start Server**

```bash
python server.py
# 或使用 VS Code Extension 啟動
```

**API-Key vs 傳統認證比較 / Comparison**

| 特性 Feature | API-Key 認證 | 傳統 PFX 認證 |
|-------------|-------------|--------------|
| 認證方式 | personal_id + API Key + PFX | 帳號 + 密碼 + PFX 憑證 |
| 安全控制 | ✅ API Key 權限/IP 控制 | ❌ 無 API Key 權限控制 |
| 憑證管理 | ✅ 可由網頁匯出並輪換 | ⚠️ 需管理憑證檔案 |
| CI/CD 友善 | ✅ 可搭配環境變數 | ⚠️ 需管理憑證檔案 |
| SDK 版本要求 | v2.2.8+ | v2.2.4+ |

**安全最佳實務 / Security Best Practices**

1. **IP 白名單設定**：在富邦證券 API 平台設定允許的 IP 地址
2. **定期輪換 API Key**：建議每 90 天更新一次 API Key
3. **環境隔離**：開發、測試、生產環境使用不同的 API Key
4. **權限最小化**：僅申請需要的 API 權限
5. **密鑰保護**：
   - ❌ 不要將 API Key 提交到版本控制
   - ❌ 不要在日誌中記錄完整的 API Key
   - ✅ 使用 `.env` 文件管理敏感資訊
   - ✅ 在 CI/CD 中使用加密的環境變數

**常見錯誤處理 / Common Error Handling**

```python
# 錯誤：無效的 API Key 格式
# Error: Invalid API Key format
無效的 API 金鑰格式 (太短) / Invalid API Key format (too short)

# 錯誤：API-Key 缺少登入憑證
# Error: API-Key login requires a certificate
API 金鑰登入需要 FUBON_USERNAME、FUBON_API_KEY 與 FUBON_PFX_PATH
API-Key login requires FUBON_USERNAME, FUBON_API_KEY, and FUBON_PFX_PATH

# 錯誤：API Key 過期或已撤銷
# Error: API Key expired or revoked
API 金鑰已過期或已被撤銷 / API Key has expired or been revoked
請前往富邦證券 API 平台重新申請或檢查狀態
```

**切換認證方式 / Switch Authentication Methods**

系統會自動偵測使用哪種認證方式：

- 如果設定了 `FUBON_USERNAME` + `FUBON_API_KEY` + `FUBON_PFX_PATH` → 使用 v2.2.8 API-Key 認證
- 如果設定了 `FUBON_USERNAME` + `FUBON_PASSWORD` + `FUBON_PFX_PATH` → 使用傳統 PFX 認證
- 兩種方式皆可，系統優先使用 API-Key 認證

### 4. 啟動服務

```bash
python server.py
```

#### MCP v2 傳輸設定

預設 `stdio` 適合 VS Code、Claude Desktop 等桌面 MCP Host。需要遠端部署時，可使用新版 Streamable HTTP：

```env
FUBON_MCP_TRANSPORT=streamable-http
FUBON_MCP_HOST=127.0.0.1
FUBON_MCP_PORT=8000
FUBON_MCP_HTTP_PATH=/mcp
FUBON_MCP_STATELESS_HTTP=true
```

`stateless_http=true` 會讓每個請求使用獨立 transport，不依賴 `Mcp-Session-Id` 或 sticky session，並由官方 SDK 處理 `server/discover`、2026-07-28 per-request metadata 與協定協商。`sse` 仍可作為舊版 client 的相容選項。

### 5. VS Code Extension 安裝（推薦）

#### 從 Marketplace 安裝
1. 打開 VS Code
2. 按 `Ctrl+Shift+X` 打開擴展面板
3. 搜尋 "Fubon API MCP Server"
4. 點擊安裝（Publisher: **mofesto**）

或直接訪問：https://marketplace.visualstudio.com/items?itemName=mofesto.fubon-api-mcp-server

#### 手動安裝 VSIX
```bash
# 從 GitHub Releases 下載 .vsix 檔案
# 然後在 VS Code 中：Extensions > ... > Install from VSIX
```

#### 配置 Extension
按 `Ctrl+,` (或 `Cmd+,`) 打開設定，搜尋 "Fubon MCP"：
- **Username**: 您的富邦證券帳號
- **Pfx Path**: PFX 憑證檔案完整路徑
- **Data Dir**: 數據儲存目錄（選填，預設 `./data`）
- **Auto Start**: 自動啟動選項（選填，預設 `false`）

#### 使用 Extension
按 `Ctrl+Shift+P` (或 `Cmd+Shift+P`) 打開命令面板，輸入 "Fubon MCP"：
- **Start Fubon MCP Server**: 啟動服務
- **Stop Fubon MCP Server**: 停止服務
- **Restart Fubon MCP Server**: 重啟服務
- **Show Fubon MCP Server Logs**: 查看日誌

#### 安全性
- ✅ 帳號密碼**不會儲存**在設定檔中
- ✅ 每次啟動時需要重新輸入密碼
- ✅ 密碼輸入框使用遮罩保護

### 6. VS Code MCP 配置（手動配置方式）

如果不使用 Extension，可在工作區設定中手動配置 MCP 伺服器：

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

> 注意：條件單目前不支援期權商品與現貨商品混用。

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

#### 單一條件單

單一條件單使用富邦官方 `single_condition` API，當觸發條件達成時自動送出委託單。

```python
from mcp_fubon import place_condition_order

result = place_condition_order({
    "account": "帳戶號碼",
    "start_date": "20240427",      # 開始日期 YYYYMMDD
    "end_date": "20240516",        # 結束日期 YYYYMMDD
    "stop_sign": "Full",           # Full(全部成交), Partial(部分成交), UntilEnd(效期結束)
    
    # 觸發條件
    "condition": {
        "market_type": "Reference",     # Reference(參考價) 或 LastPrice(最新價)
        "symbol": "2881",               # 股票代碼
        "trigger": "MatchedPrice",      # MatchedPrice(成交價), BuyPrice(買價), SellPrice(賣價)
        "trigger_value": "80",          # 觸發值
        "comparison": "LessThan"        # LessThan(<), LessOrEqual(<=), Equal(=), Greater(>), GreaterOrEqual(>=)
    },
    
    # 委託單參數
    "order": {
        "buy_sell": "Sell",             # Buy 或 Sell
        "symbol": "2881",
        "price": "60",
        "quantity": 1000,
        "market_type": "Common",        # Common, Emg, Odd
        "price_type": "Limit",          # Limit, Market, LimitUp, LimitDown
        "time_in_force": "ROD",         # ROD, IOC, FOK
        "order_type": "Stock"           # Stock, Margin, Short, DayTrade
    }
})
# 返回: {"status": "success", "data": {"guid": "條件單號", ...}}
```

**單一條件單參數說明**:
- `stop_sign`: 條件停止條件
  - `Full`: 全部成交為止（預設）
  - `Partial`: 部分成交為止
  - `UntilEnd`: 效期結束為止
- `condition`: 觸發條件，當條件達成時觸發委託單
- `order`: 觸發後的委託單內容

#### 停損停利條件單（TPSL）

停損停利單使用相同的 `single_condition` API，在單一條件單基礎上加入選填的 `tpsl` 參數。

**⚠️ 停損停利重要注意事項**（來自富邦官方文檔）：
- 停損停利設定**僅為觸發送單**，不保證必定成交，需視市場狀況自行調整
- 請確認停損停利委託類別設定需符合適合之交易規則（例如信用交易資買資賣等）
- **待主單完全成交後，停損停利部分才會啟動**
- 當停利條件達成時停損失效，反之亦然（OCO機制）

```python
# 建議使用 place_condition_order 並提供 tpsl 參數
from mcp_fubon import place_condition_order

result = place_condition_order({
    "account": "帳戶號碼",
    "start_date": "20240426",      # 開始日期 YYYYMMDD
    "end_date": "20240430",        # 結束日期 YYYYMMDD
    "stop_sign": "Full",           # Full(全部) 或 Flat(減碼)
    
    # 觸發條件
    "condition": {
        "market_type": "Reference",     # Reference(參考價) 或 LastPrice(最新價)
        "symbol": "2881",               # 股票代碼
        "trigger": "MatchedPrice",      # MatchedPrice(成交價), BuyPrice(買價), SellPrice(賣價)
        "trigger_value": "66",          # 觸發值
        "comparison": "LessThan"        # LessThan(<), LessOrEqual(<=), Equal(=), Greater(>), GreaterOrEqual(>=)
    },
    
    # 委託單參數
    "order": {
        "buy_sell": "Buy",              # Buy 或 Sell
        "symbol": "2881",
        "price": "66",
        "quantity": 1000,
        "market_type": "Common",        # Common, Emg, Odd
        "price_type": "Limit",          # Limit, Market, LimitUp, LimitDown
        "time_in_force": "ROD",         # ROD, IOC, FOK
        "order_type": "Stock"           # Stock, Margin, Short, DayTrade
    },
    
    # 停損停利參數
    "tpsl": {
        "stop_sign": "Full",
        # 停利單（選填）
        "tp": {
            "time_in_force": "ROD",
            "price_type": "Limit",
            "order_type": "Stock",
            "target_price": "85",       # 停利觸發價
            "price": "85",              # 停利委託價（Market則填""）
            "trigger": "MatchedPrice"   # 觸發內容
        },
        # 停損單（選填）
        "sl": {
            "time_in_force": "ROD",
            "price_type": "Limit",
            "order_type": "Stock",
            "target_price": "60",       # 停損觸發價
            "price": "60",              # 停損委託價（Market則填""）
            "trigger": "MatchedPrice"
        },
        "end_date": "20240517",         # 停損停利結束日期 YYYYMMDD（選填）
        "intraday": False               # 是否當日有效（選填）
    }
})
```

**停損停利單參數說明**:
- `tpsl`: 停損停利參數（選填，但若提供則tp或sl至少要有一個）
  - `tp`: 停利單設定（選填），達到目標價格後賣出獲利
  - `sl`: 停損單設定（選填），跌破價格後賣出止損
  - `end_date`: 停損停利結束日期（選填）
  - `intraday`: 是否當日有效（選填）
- **OCO機制**: 停利或停損任一觸發後，另一個自動失效
- **觸發順序**: 先觸發主單條件 → 主單完全成交 → 啟動停損停利監控

**使用提醒**:
- 停損停利設定僅為觸發送單，**不保證成交**
- Market 價格類型時，price 參數填空值 `""`
- 條件單目前不支援期權商品與現貨商品混用

**便捷方法**（與上述功能完全相同）:
```python
from mcp_fubon import place_tpsl_condition_order
result = place_tpsl_condition_order({...})  # 參數同上
```

#### 多條件單（Multi-Condition）

多條件單使用富邦官方 `multi_condition` API，支援設定**多個觸發條件**，當**所有條件都達成**時才送出委託單。

**使用場景**：
- 價格 AND 成交量條件
- 多檔股票同時觸發
- 複合技術指標條件

**⚠️ 重要提醒**：
- **所有條件必須同時滿足**才會觸發委託單
- 其他注意事項與單一條件單相同

```python
from mcp_fubon import place_multi_condition_order

result = place_multi_condition_order({
    "account": "帳戶號碼",
    "start_date": "20240426",
    "end_date": "20240430",
    "stop_sign": "Full",
    
    # 多個觸發條件（全部須滿足）
    "conditions": [
        {
            "market_type": "Reference",
            "symbol": "2881",
            "trigger": "MatchedPrice",      # 成交價
            "trigger_value": "66",
            "comparison": "LessThan"        # < 66
        },
        {
            "market_type": "Reference",
            "symbol": "2881",
            "trigger": "TotalQuantity",     # 總量
            "trigger_value": "8000",
            "comparison": "LessThan"        # < 8000
        }
    ],
    
    # 委託單參數
    "order": {
        "buy_sell": "Buy",
        "symbol": "2881",
        "price": "66",
        "quantity": 1000,
        "market_type": "Common",
        "price_type": "Limit",
        "time_in_force": "ROD",
        "order_type": "Stock"
    },
    
    # 停損停利參數（選填）
    "tpsl": {
        "tp": {
            "time_in_force": "ROD",
            "price_type": "Limit",
            "order_type": "Stock",
            "target_price": "85",
            "price": "85"
        },
        "sl": {
            "time_in_force": "ROD",
            "price_type": "Limit",
            "order_type": "Stock",
            "target_price": "60",
            "price": "60"
        },
        "end_date": "20240517"
    }
})
```

**多條件單參數說明**:
- `conditions`: **條件列表**（所有條件必須同時滿足）
  - 支援的觸發內容 (`trigger`):
    - `MatchedPrice`: 成交價
    - `BuyPrice`: 買價
    - `SellPrice`: 賣價
    - `TotalQuantity`: 總量
  - 每個條件可設定不同的股票、觸發內容和比較運算子
- `order`: 當所有條件達成後的委託單內容
- `tpsl`: 停損停利參數（選填）

**範例場景**:
```python
# 場景 1: 價格跌破且成交量放大時買入
"conditions": [
    {"symbol": "2330", "trigger": "MatchedPrice", "trigger_value": "500", "comparison": "LessThan"},
    {"symbol": "2330", "trigger": "TotalQuantity", "trigger_value": "10000", "comparison": "Greater"}
]

# 場景 2: 兩檔股票同時觸發
"conditions": [
    {"symbol": "2330", "trigger": "MatchedPrice", "trigger_value": "550", "comparison": "Greater"},
    {"symbol": "2881", "trigger": "MatchedPrice", "trigger_value": "70", "comparison": "Greater"}
]
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
    "to_date": "2024-12-31",
    "adjusted": true,
    "timeframe": "D",
    "sort": "asc"
})
```

#### 股務事件（SDK v2.2.8）

```python
from mcp_fubon import get_capital_changes, get_dividends, get_listing_applicants

capital_changes = get_capital_changes({
    "start_date": "2026-01-01",
    "end_date": "2026-12-31",
    "sort": "asc"
})
dividends = get_dividends({"start_date": "2026-01-01", "end_date": "2026-12-31"})
listing_applicants = get_listing_applicants({
    "start_date": "2026-01-01",
    "end_date": "2026-12-31",
    "sort": "desc"
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

#### 測試覆蓋率
[![codecov](https://codecov.io/gh/Mofesto/fubon-api-mcp-server/branch/main/graph/badge.svg)](https://codecov.io/gh/Mofesto/fubon-api-mcp-server)

**當前覆蓋率**: 28% (目標: >80%)

#### 運行完整測試套件

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

#### 生成覆蓋率報告

```bash
# 安裝測試依賴
pip install pytest-cov coverage

# 運行測試並生成覆蓋率
pytest --cov=fubon_api_mcp_server --cov-report=html --cov-report=term-missing

# 查看 HTML 報告
open htmlcov/index.html
```

#### 測試結果

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
├── fubon_api_mcp_server/              # 主要程式碼包
│   ├── __init__.py        # 包初始化
│   └── server.py          # MCP 伺服器主程式
├── vscode-extension/       # VS Code Extension
│   ├── package.json       # Extension 配置
│   ├── README.md          # Extension 說明
│   └── src/               # Extension 程式碼
├── scripts/                # 🆕 管理和發布腳本
│   ├── version_config.json # 統一版本配置
│   ├── release.ps1        # 自動發布腳本
│   ├── update_version.ps1 # 版本更新腳本
│   ├── generate_release_notes.ps1 # Release Notes 生成
│   └── README.md          # 腳本使用說明
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
├── pyproject.toml         # 專案配置
└── README.md              # 專案說明
```

### 環境變數說明

| 變數名稱 | 必填 | 說明 |
|---------|------|------|
| **傳統 PFX 認證** | | |
| `FUBON_USERNAME` | ✅* | 富邦證券帳號 |
| `FUBON_PASSWORD` | ✅* | 登入密碼 |
| `FUBON_PFX_PATH` | ✅* | 電子憑證路徑 (.pfx) |
| `FUBON_PFX_PASSWORD` | ❌ | 憑證密碼（如果有） |
| **API-Key 認證 (SDK v2.2.8+)** | | |
| `FUBON_API_KEY` | ✅** | 富邦證券 API Key |
| `FUBON_PFX_PATH` | ✅** | 網頁匯出的 PFX 憑證路徑 |
| `FUBON_PFX_PASSWORD` | ❌ | 匯出憑證密碼 |
| **共用設定** | | |
| `FUBON_DATA_DIR` | ❌ | 數據快取目錄（預設: ./data） |
| **MCP v2 傳輸** | | |
| `FUBON_MCP_TRANSPORT` | ❌ | `stdio`（預設）、`streamable-http` 或 `sse` |
| `FUBON_MCP_HOST` | ❌ | HTTP/SSE bind host（預設 `127.0.0.1`） |
| `FUBON_MCP_PORT` | ❌ | HTTP/SSE port（預設 `8000`） |
| `FUBON_MCP_STATELESS_HTTP` | ❌ | Streamable HTTP 是否無狀態（預設 `true`） |

*必填：使用傳統 PFX 認證時  
**必填：使用 API-Key 認證時

### 核心依賴說明

- **`fubon-neo`**: 富邦證券官方 Python SDK，提供完整的交易 API
- **`mcp>=2.0.0,<3.0.0`**: 官方 MCP Python SDK，支援 protocol revision `2026-07-28`
- **`pandas`**: 數據處理和分析
- **`pydantic`**: 數據驗證和序列化
- **`python-dotenv`**: 環境變數管理

### 安全注意事項

- 🔒 **敏感資訊**: 密碼和憑證檔案請勿提交至版本控制
- 🔒 **環境變數**: 使用 `.env` 文件管理敏感配置
- 🔒 **權限控制**: 限制憑證檔案的存取權限
- 🔒 **網路安全**: 確保網路連線的安全性

## 📝 更新日誌
### v2.2.1 (2025-11-10)
- 🤖 **Phase 3 高級分析**: 新增8項高級MCP提示與6項量化交易工具
- 📊 **投資組合分析**: 績效分析、風險管理、投資組合優化
- 🎯 **市場情緒分析**: 多維度情緒分析與指數生成
- ⚡ **算法策略**: 量化策略建構與期權策略優化
- 📈 **期貨分析**: 期貨價差分析與波動率交易顧問
- 🔬 **量化工具**: VaR計算、壓力測試、績效歸因、套利偵測
- 📚 **文檔更新**: 完整記錄Phase 3新功能與使用說明

### v2.0.6 (2025-11-05)
- 🐛 **CI 修復**: 修復 GitHub Actions 中 ModuleNotFoundError，通過添加可編輯安裝解決測試時模組找不到的問題
- 📚 **文檔清理**: 移除不必要的舊版 release notes 和重複的安裝指南，簡化專案結構

### v1.8.6 (2025-11-04)
- 🚀 **VS Code Extension**: 完整的 VS Code Extension，一鍵啟動/停止 MCP Server
- 🔧 **動態版本管理**: 採用 setuptools-scm 從 Git tags 自動生成版本號
- 📦 **自動化發佈**: PyPI 和 VS Code Marketplace 自動發佈流程
- 🔒 **安全增強**: Extension 密碼不儲存在設定中，使用安全輸入
- 📚 **文檔完善**: 新增完整的發佈指南和使用說明
- 🎯 **Extension ID**: `mofesto.fubon-api-mcp-server`
- 🐛 **修正**: Release notes 和發佈流程優化


### v1.7.0 (2025-11-03)
- 🔄 **CI/CD 完善**: 新增完整的 GitHub Actions 工作流程
- 🛠️ **開發工具**: 添加 pre-commit hooks、代碼品質工具
- 📦 **現代化包裝**: 遷移至 pyproject.toml
- 🔒 **安全增強**: 新增安全掃描和漏洞檢查
- 🤝 **貢獻指南**: 添加詳細的貢獻者和行為準則
- 🔧 **PyPI 發佈修復**: 修復發佈工作流程的認證參數

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
- 📦 **MCP整合**: Model Context Protocol支持

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

# 安裝富邦官方 SDK（開發測試用）
pip install fubon-neo

# 運行測試
python -m pytest

# 代碼格式化
black .
flake8 .
```

### 🆕 自動化發布流程

專案使用統一的版本管理系統，所有版本資訊集中在 `scripts/version_config.json`：

```powershell
# 發布新版本 (patch)
.\scripts\release.ps1

# 發布 minor 版本
.\scripts\release.ps1 -BumpType minor

# 發布 major 版本
.\scripts\release.ps1 -BumpType major
```

腳本會自動：
1. 運行測試
2. 更新所有文件中的版本號
3. 生成 Release Notes
4. 創建 Git 標籤
5. 推送到 GitHub 觸發自動發布

詳細說明請參考 [scripts/README.md](scripts/README.md)

**開發者注意**: 
- 開發時請確保已安裝 `fubon-neo` 套件
- 測試需要有效的富邦證券帳號和憑證
- 請勿在生產環境中提交敏感憑證資訊
- 版本號統一在 `scripts/version_config.json` 管理

## 📄 授權條款

本專案採用 [Apache License 2.0](LICENSE) 授權。
## 📦 發佈資訊

### PyPI Package
- **套件名稱**: `fubon-api-mcp-server`
- **最新版本**: 2.2.1
- **安裝**: `pip install fubon-api-mcp-server`
- **PyPI**: https://pypi.org/project/fubon-api-mcp-server/

### VS Code Extension
- **Extension ID**: `mofesto.fubon-api-mcp-server`
- **Publisher**: mofesto
- **版本**: 2.2.1
- **Marketplace**: https://marketplace.visualstudio.com/items?itemName=mofesto.fubon-api-mcp-server
- **安裝方式**: 在 VS Code 中搜尋 "Fubon API MCP Server"

### GitHub Repository
- **Repository**: https://github.com/Mofesto/fubon-api-mcp-server
- **Issues**: https://github.com/Mofesto/fubon-api-mcp-server/issues
- **Releases**: https://github.com/Mofesto/fubon-api-mcp-server/releases
- **Documentation**: https://github.com/Mofesto/fubon-api-mcp-server#readme


## ⚠️ 免責聲明

- 📢 **投資風險**: 股票交易具有風險，請謹慎投資
- 📢 **使用責任**: 用戶需自行承擔使用本軟體的風險
- 📢 **法規遵循**: 請遵守相關金融法規和平台使用條款
- 📢 **技術支援**: 本專案不提供官方技術支援

## 👥 作者與致謝

- **開發者**: Mofesto.Cui
- **Publisher**: mofesto (VS Code Marketplace)
- **貢獻者**: 歡迎所有貢獻者

## ☕ 支持專案

如果這個專案對您有幫助，歡迎請我喝杯咖啡支持開發！

<div align="center">
  <img src="https://github.com/Mofesto/fubon-api-mcp-server/blob/main/assets/images/support-qrcode.png?raw=true" alt="Buy me a coffee" width="200"/>
  <p><i>掃描 QR Code 支持專案</i></p>
</div>

## 🔗 相關連結

- **PyPI Package**: https://pypi.org/project/fubon-api-mcp-server/
- **VS Code Extension**: https://marketplace.visualstudio.com/items?itemName=mofesto.fubon-api-mcp-server
- **GitHub Repository**: https://github.com/Mofesto/fubon-api-mcp-server
- **富邦證券 API 官方文檔**: https://www.fbs.com.tw/TradeAPI/docs/
- **問題回報**: https://github.com/Mofesto/fubon-api-mcp-server/issues


---

⭐ 如果這個專案對您有幫助，請給我們一個星標！
