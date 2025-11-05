# 工作區變數修復說明 (v1.8.9)

## 問題描述

在 v1.8.8 及之前版本中，VS Code 擴充套件在 `package.json` 的 MCP 配置中使用了相對路徑 `./data`：

```json
{
  "modelContextProtocol": {
    "servers": {
      "fubon-api": {
        "env": {
          "FUBON_DATA_DIR": "./data"  // ❌ 問題：相對路徑需要 workspaceFolder
        }
      }
    }
  }
}
```

這會導致以下錯誤：
```
CodeExpectedError: 無法解析變數 workspaceFolder。請開啟資料夾
```

## 根本原因

- VS Code 的 MCP 擴充套件會嘗試解析配置中的路徑變數
- 相對路徑（如 `./data`）會被解析為 `${workspaceFolder}/data`
- 如果使用者沒有開啟工作區資料夾，`workspaceFolder` 變數就無法解析
- 導致 MCP 伺服器無法啟動

## 解決方案 (v1.8.9)

### 1. 移除預設相對路徑

從 `package.json` 的 MCP 配置中移除 `FUBON_DATA_DIR` 環境變數：

```json
{
  "modelContextProtocol": {
    "servers": {
      "fubon-api": {
        "env": {
          "FUBON_USERNAME": "",
          "FUBON_PASSWORD": "",
          "FUBON_PFX_PATH": "",
          "FUBON_PFX_PASSWORD": ""
          // ✅ 不再包含 FUBON_DATA_DIR
        }
      }
    }
  }
}
```

### 2. 使用程式預設路徑

`fubon_api_mcp_server/config.py` 已定義預設路徑：

```python
# Default data directory for storing local stock historical data
DEFAULT_DATA_DIR = Path.home() / "Library" / "Application Support" / "fubon-mcp" / "data"
BASE_DATA_DIR = Path(os.getenv("FUBON_DATA_DIR", DEFAULT_DATA_DIR))
```

這個路徑會自動解析為：
- **Windows**: `C:\Users\<username>\Library\Application Support\fubon-mcp\data`
- **macOS**: `~/Library/Application Support/fubon-mcp/data`
- **Linux**: `~/Library/Application Support/fubon-mcp/data`

### 3. 允許使用者自訂路徑（可選）

使用者仍可透過配置介面指定自訂路徑：

1. 執行命令：`Fubon MCP: Configure Fubon MCP Server`
2. 在「數據儲存目錄」欄位輸入絕對路徑（或留空使用預設）
3. 配置會寫入 GitHub Copilot 的 MCP 設定檔

## 升級步驟

### 方法 1: 重新安裝擴充套件（推薦）

```bash
# 從專案根目錄執行
code --install-extension vscode-extension/fubon-api-mcp-server-1.8.9.vsix
```

### 方法 2: 手動修正現有配置

如果已經安裝了舊版本，需要手動編輯 MCP 配置檔案：

**Windows 路徑：**
```
%APPDATA%\Code\User\globalStorage\github.copilot-chat\config.json
```

**修改內容：**
```json
{
  "mcpServers": {
    "fubon-api": {
      "command": "python",
      "args": ["-m", "fubon_api_mcp_server.server"],
      "env": {
        "FUBON_USERNAME": "你的帳號",
        "FUBON_PFX_PATH": "你的憑證路徑",
        "FUBON_PASSWORD": "${env:FUBON_PASSWORD}",
        "FUBON_PFX_PASSWORD": "${env:FUBON_PFX_PASSWORD}"
        // ✅ 移除 "FUBON_DATA_DIR": "./data"
      }
    }
  }
}
```

## 驗證修正

1. **重新載入 VS Code**
2. **開啟 GitHub Copilot Chat**
3. **測試 MCP 伺服器是否可用**

如果沒有看到錯誤訊息，表示修正成功！

## 相關變更

- `vscode-extension/package.json`: 移除 `FUBON_DATA_DIR` 預設值
- `vscode-extension/src/extension.js`: 
  - 更新配置介面提示文字
  - 條件式新增 `FUBON_DATA_DIR`（僅在使用者明確設定時）
- 版本號: `1.8.8` → `1.8.9`

## 附註

此問題僅影響 VS Code 擴充套件的 MCP 整合。直接使用命令列啟動（`python -m fubon_api_mcp_server.server`）不受影響。
