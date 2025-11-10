# 本地MCP服務器設置指南

## 概述

本指南將幫助你在本地設置Fubon API MCP Server，以便在VS Code的GitHub Copilot Chat中使用。

## 環境要求

- Python 3.10+
- VS Code with GitHub Copilot Chat extension
- 富邦證券帳號和憑證

## 快速設置

### 自動設置（推薦）

運行自動設置腳本：

```powershell
cd d:\fubon-api-mcp-server
.\setup_local_mcp.ps1
```

這個腳本會自動：
- 檢查Python環境
- 安裝項目依賴
- 配置VS Code MCP設置
- 測試MCP服務器功能

### 手動設置

#### 1. 安裝依賴

```bash
cd d:\fubon-api-mcp-server
pip install -e .
```

### 2. 配置環境變數

項目根目錄已包含 `.env` 文件，包含必要的環境變數：
- `FUBON_USERNAME`: 富邦證券帳號
- `FUBON_PASSWORD`: 帳號密碼
- `FUBON_PFX_PATH`: PFX憑證檔案路徑
- `FUBON_PFX_PASSWORD`: 憑證密碼

### 3. 配置VS Code MCP

VS Code的MCP配置文件已自動設置在：
```
%APPDATA%\Code\User\globalStorage\github.copilot-chat\config.json
```

配置內容：
```json
{
  "mcpServers": {
    "fubon-api": {
      "command": "python",
      "args": ["-m", "fubon_api_mcp_server.server"],
      "env": {
        "FUBON_USERNAME": "D122452664",
        "FUBON_PFX_PATH": "C:\\\\CAFubon\\\\D122452664\\\\D122452664.pfx",
        "FUBON_DATA_DIR": "D:\\\\fubon-api-mcp-server\\\\data",
        "FUBON_PASSWORD": "${env:FUBON_PASSWORD}",
        "FUBON_PFX_PASSWORD": "${env:FUBON_PFX_PASSWORD}"
      }
    }
  }
}
```

### 4. 重新啟動VS Code

配置完成後，**必須完全重新啟動VS Code**（不是重新載入視窗）。

## 測試設置

### 運行本地測試

```bash
cd d:\fubon-api-mcp-server
python test_mcp_local.py
```

成功輸出應類似：
```
🚀 啟動MCP服務器測試...
🔍 測試MCP服務器...
✅ 找到 77 個工具
📋 前5個工具: get_trading_signals, historical_candles, place_order, _find_target_order, modify_quantity
🎉 MCP服務器測試完成!
```

### 在VS Code中測試

1. 打開GitHub Copilot Chat
2. 輸入 `@` 符號
3. 應該會看到 `@fubon-api` 出現在建議列表中
4. 嘗試查詢：`@fubon-api 查詢2330的即時報價`

## 可用工具

MCP服務器提供77個工具，包括：

### 市場數據
- `get_realtime_quotes`: 獲取即時行情
- `get_intraday_quote`: 獲取盤中報價
- `get_intraday_candles`: 獲取K線數據
- `get_intraday_trades`: 獲取成交明細
- `get_snapshot_quotes`: 獲取行情快照

### 期貨/選擇權
- `get_intraday_futopt_tickers`: 獲取合約代碼列表
- `get_intraday_futopt_quote`: 獲取期貨/選擇權報價
- `get_intraday_futopt_candles`: 獲取期貨/選擇權K線

### 交易功能
- `place_order`: 下單
- `cancel_order`: 取消委託
- `batch_place_order`: 批量下單
- `place_condition_order`: 條件單

### 帳戶管理
- `get_account_info`: 獲取帳戶資訊
- `get_inventory`: 獲取庫存
- `get_order_results`: 獲取委託結果

## 疑難排解

### 問題：MCP服務器沒有出現在VS Code中

1. 確認配置文件路徑正確
2. 檢查JSON格式是否正確
3. 完全重新啟動VS Code
4. 檢查VS Code輸出面板的GitHub Copilot Chat日誌

### 問題：工具調用失敗

1. 確認環境變數設置正確
2. 檢查憑證檔案路徑和密碼
3. 查看MCP服務器日誌：`python -m fubon_api_mcp_server.server`

### 問題：Python模組找不到

```bash
# 重新安裝
pip install -e .
# 或
python -m pip install --upgrade fubon-api-mcp-server
```

## 開發模式

如果你要修改MCP服務器代碼：

1. 修改 `fubon_api_mcp_server/server.py`
2. 運行測試：`python -m pytest tests/`
3. 重新啟動VS Code以載入新版本

## 日誌位置

- MCP服務器日誌：`log/` 目錄
- VS Code日誌：查看輸出面板 > GitHub Copilot Chat

---

設置完成後，你就可以在VS Code的Copilot Chat中使用 `@fubon-api` 來訪問富邦證券的完整交易功能了！