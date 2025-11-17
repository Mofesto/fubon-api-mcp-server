# 富邦 API MCP Server 範例

此目錄包含富邦 API MCP Server 的完整使用範例，展示如何在實際應用中使用各項功能。

## 📁 檔案結構

```
examples/
├── account_service_example.py       # Account Service 完整真實案例
├── account_service_real_test.py     # Account Service 真實 API 手動測試
├── indicators_example.py            # 技術指標計算範例（合成數據）
├── indicators_real_test.py          # 技術指標真實數據測試
├── indicators_service_real_test.py  # Indicators Service 真實數據測試
├── market_data_service_real_test.py # Market Data Service 真實 API 手動測試
├── reports_service_real_test.py     # Reports Service 真實 API 手動測試
└── README.md                        # 此說明文件
```

## 🚀 快速開始

### 1. 環境準備

首先，確保您已設定必要的環境變數：

```bash
# 設定環境變數（請替換為您的實際資訊）
export FUBON_USERNAME="您的帳號"
export FUBON_PASSWORD="您的密碼"
export FUBON_PFX_PATH="/path/to/your/certificate.pfx"
export FUBON_PFX_PASSWORD="您的憑證密碼"  # 可選
```

### 2. 安裝依賴

```bash
# 安裝必要套件
pip install python-dotenv fubon-neo mcp
```

### 運行範例

```bash
# 運行 Account Service 完整範例
python examples/account_service_example.py

# 運行 Account Service 真實 API 手動測試
python examples/account_service_real_test.py

# 運行技術指標計算範例（合成數據）
python examples/indicators_example.py

# 運行技術指標真實數據測試（需要真實 API）
python examples/indicators_real_test.py

# 運行 Indicators Service 真實數據測試（需要真實 API）
python examples/indicators_service_real_test.py

# 運行 Market Data Service 真實 API 測試
python examples/market_data_service_real_test.py

# 運行 Reports Service 真實 API 測試
python examples/reports_service_real_test.py
```

⚠️ **注意**: `account_service_real_test.py`、`indicators_real_test.py`、`indicators_service_real_test.py`、`market_data_service_real_test.py` 和 `reports_service_real_test.py` 會調用真實的富邦 API，需要正確的環境變數設定

## 📊 Account Service 範例說明

### `account_service_example.py`

此範例展示 Account Service 的完整功能，包括：

#### 🔍 帳戶資訊查詢
- **基本資訊**: 查詢帳戶基本資料
- **詳細資訊**: 查詢指定帳戶的完整資訊

#### 💰 資金管理
- **銀行餘額**: 查詢帳戶可用資金
- **維持率**: 查詢融資融券維持率資訊
- **結算資訊**: 查詢應收付金額（當日/3日）

#### 📦 庫存管理
- **股票庫存**: 查詢持有的股票明細

#### 📈 損益分析
- **未實現損益**: 查詢持倉的未實現損益
- **已實現損益**: 查詢已平倉的損益記錄
- **損益摘要**: 彙總損益統計

#### 📋 歷史記錄
- **移動鎖利歷史**: 查詢移動鎖利條件單歷史
- **條件單歷史**: 查詢條件單建立歷史

### `account_service_real_test.py`

此腳本提供完整的真實 API 手動測試，涵蓋所有 Account Service 方法：

#### 🧪 測試涵蓋範圍
- **帳戶資訊測試**: 基本資訊查詢
- **庫存測試**: 股票庫存查詢
- **資金測試**: 銀行餘額、維持率、結算資訊
- **損益測試**: 已實現/未實現損益查詢
- **歷史記錄測試**: 移動鎖利和條件單歷史

#### 📊 測試特點
- **手動執行**: 不依賴 pytest，可直接運行
- **詳細輸出**: 每個測試都有清晰的成功/失敗指示
- **統計報告**: 提供測試通過率和詳細統計
- **錯誤處理**: 完善的異常處理和錯誤訊息

### `indicators_example.py`

此範例展示如何使用 `fubon_api_mcp_server.indicators` 模塊中的技術指標函數，使用合成數據進行演示：

#### 📊 移動平均指標
- **SMA**: 簡單移動平均
- **EMA**: 指數移動平均  
- **WMA**: 加權移動平均

#### 📈 波段指標
- **Bollinger Bands**: 布林通道（上/中/下軌 + 寬度）

#### 💹 動量指標
- **RSI**: 相對強弱指標
- **Williams %R**: 威廉指標
- **CCI**: 順勢指標
- **ROC**: 變化率

#### 📉 趨勢指標
- **MACD**: 指數平滑異同移動平均
- **ADX**: 平均趨向指標

#### 📊 波動率指標
- **ATR**: 平均真實波幅

#### 📦 成交量指標
- **OBV**: 能量潮指標
- **Volume Rate**: 量比（自定義指標）

#### 🎯 隨機指標
- **KD**: 隨機指標（%K 和 %D）

**所有指標都基於 TA-Lib 實現，提供專業的技術分析功能。**

### `indicators_real_test.py`

此腳本提供完整的技術指標真實數據測試，使用真實的市場數據進行指標計算：

#### 🧪 測試特點
- **真實數據**: 使用富邦 API 獲取真實市場數據
- **完整涵蓋**: 測試所有 14 種技術指標
- **詳細輸出**: 每個指標都有清晰的計算結果顯示
- **統計報告**: 提供測試通過率和詳細統計
- **錯誤處理**: 完善的異常處理和錯誤訊息

#### 📊 測試涵蓋指標
- **移動平均**: SMA, EMA, WMA
- **波段分析**: Bollinger Bands
- **動量指標**: RSI, Williams %R, CCI, ROC
- **趨勢指標**: MACD, ADX
- **波動率**: ATR
- **成交量**: OBV, Volume Rate
- **隨機指標**: KD

#### ⚠️ 使用注意
- 需要正確的環境變數設定
- 會調用真實的富邦 API
- 建議使用台積電 (2330) 等流動性好的股票進行測試

### `indicators_service_real_test.py`

此腳本提供完整的 Indicators Service 真實數據測試，使用真實的市場數據進行高級金融分析：

#### 🧪 測試特點
- **真實數據**: 使用富邦 API 獲取多支股票的歷史數據
- **投資組合分析**: 創建示例投資組合進行風險分析
- **完整涵蓋**: 測試所有 Indicators Service 高級功能
- **詳細輸出**: 每個分析都有清晰的結果顯示
- **統計報告**: 提供測試通過率和詳細統計
- **錯誤處理**: 完善的異常處理和錯誤訊息

#### 📊 測試涵蓋功能
- **市場情緒指數**: 基於 RSI、MACD、布林通道的綜合情緒分析
- **VaR 計算**: 投資組合價值-at-risk 風險度量
- **壓力測試**: 多種市場情景下的投資組合壓力測試
- **投資組合優化**: 基於現代投資組合理論的資產配置優化

#### ⚠️ 使用注意
- 需要正確的環境變數設定
- 會調用真實的富邦 API 獲取多支股票數據
- 測試會創建示例投資組合進行風險分析
- 建議使用流動性好的股票進行測試

### `reports_service_real_test.py`

此腳本提供完整的 Reports Service 真實 API 手動測試，涵蓋所有 Reports Service 方法：

#### 🧪 測試涵蓋範圍
- **報告總覽測試**: 獲取所有類型的報告總覽
- **個別報告測試**: 委託報告、委託變更報告、成交報告、事件報告
- **委託結果測試**: 查詢帳戶委託結果和詳細資訊

#### 📊 測試特點
- **手動執行**: 不依賴 pytest，可直接運行
- **詳細輸出**: 每個測試都有清晰的成功/失敗指示
- **統計報告**: 提供測試通過率和詳細統計
- **錯誤處理**: 完善的異常處理和錯誤訊息
- **條件測試**: 委託結果詳細資訊測試會根據是否有委託單動態執行

#### ⚠️ 使用注意
- 需要正確的環境變數設定
- 會調用真實的富邦 API
- 報告資料取決於帳戶的交易活動，可能為空
- 委託結果詳細資訊測試需要有現有的委託單

## ⚠️ 重要注意事項

### 安全性
- **憑證管理**: PFX 憑證檔案請妥善保管，避免洩露
- **密碼保護**: 環境變數中的密碼不會記錄在程式碼中
- **網路安全**: 使用 HTTPS 連線，注意防火牆設定

### API 限制
- **調用頻率**: 避免過度頻繁的 API 調用
- **資料時效**: 部分資料有快取機制，請注意更新時間
- **交易時段**: 部分功能僅在交易時段可用

### 錯誤處理
- **網路異常**: 網路不穩定時會自動重試
- **權限不足**: 確保帳戶有足夠權限
- **資料異常**: 部分資料可能因市場狀況而暫時不可用

## 🧪 測試與開發

### 單元測試
```bash
# 運行所有測試
python -m pytest tests/

# 運行 Account Service 測試
python -m pytest tests/test_account_service.py -v
```

### 整合測試
```bash
# 使用真實 API 手動測試（需要設定環境變數）
python examples/account_service_real_test.py
python examples/indicators_real_test.py
python examples/indicators_service_real_test.py
python examples/market_data_service_real_test.py
python examples/reports_service_real_test.py
```

### 開發模式
```bash
# 啟動 MCP Server 進行開發測試
python -m fubon_api_mcp_server.server
```

## 📚 進一步閱讀

- [主專案 README](../README.md) - 專案總覽
- [API 文件](../docs/) - 詳細 API 說明
- [設定指南](../LOCAL_MCP_SETUP.md) - 本地 MCP 設定
- [測試文件](../tests/) - 測試案例說明

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request 來改進這些範例！

## 📄 授權

此專案採用 Apache-2.0 授權條款。