# VS Code MCP Server 設置指南

## 為什麼 MCP Server 沒有出現在已安裝列表？

VS Code 的 GitHub Copilot 需要特定的配置來識別 MCP Server。以下是完整的設置步驟:

## ✅ 解決方案

### 步驟 1: 確認已安裝 Python 套件

```bash
pip install fubon-api-mcp-server
# 或
pip install -e .  # 如果你是從源碼安裝
```

驗證安裝:
```bash
python -m fubon_api_mcp_server.server --help
```

### 步驟 2: 手動配置 MCP Server (重要!)

VS Code 需要在特定位置的配置檔案中註冊 MCP Server。

#### 配置檔案位置:

**Windows**:
```
%APPDATA%\Code\User\globalStorage\github.copilot-chat\config.json
```

**macOS**:
```
~/Library/Application Support/Code/User/globalStorage/github.copilot-chat/config.json
```

**Linux**:
```
~/.config/Code/User/globalStorage/github.copilot-chat/config.json
```

#### 配置檔案內容:

創建或編輯上述檔案,添加以下內容:

```json
{
  "mcpServers": {
    "fubon-api": {
      "command": "python",
      "args": ["-m", "fubon_api_mcp_server.server"],
      "env": {
        "FUBON_USERNAME": "你的帳號",
        "FUBON_PASSWORD": "你的密碼",
        "FUBON_PFX_PATH": "C:\\path\\to\\your\\certificate.pfx",
        "FUBON_PFX_PASSWORD": "憑證密碼",
        "FUBON_DATA_DIR": "./data"
      }
    }
  }
}
```

> ⚠️ **安全提示**: 建議使用環境變數而非直接在配置檔中寫入密碼

### 步驟 3: 使用環境變數 (推薦)

更安全的做法是使用環境變數:

```json
{
  "mcpServers": {
    "fubon-api": {
      "command": "python",
      "args": ["-m", "fubon_api_mcp_server.server"],
      "env": {
        "FUBON_USERNAME": "${env:FUBON_USERNAME}",
        "FUBON_PASSWORD": "${env:FUBON_PASSWORD}",
        "FUBON_PFX_PATH": "${env:FUBON_PFX_PATH}",
        "FUBON_PFX_PASSWORD": "${env:FUBON_PFX_PASSWORD}",
        "FUBON_DATA_DIR": "./data"
      }
    }
  }
}
```

然後設定系統環境變數或使用 `.env` 檔案。

### 步驟 4: 使用 VS Code Extension 配置 (最簡單)

1. 安裝 Fubon API MCP Server 擴展
2. 按 `Ctrl+Shift+P` (Mac: `Cmd+Shift+P`)
3. 執行命令: **"Configure Fubon MCP Server"**
4. 依序輸入帳號、憑證路徑等資訊
5. 重新載入 VS Code

> 必做：首次設定時請至少執行一次「Configure Fubon MCP Server」，此步驟會將伺服器與工具正確註冊給 Copilot Chat。若未執行，`@fubon-api` 可能無法顯示可用工具或無法呼叫。

### 步驟 5: 重新啟動 VS Code

配置完成後,必須完全重新啟動 VS Code (不是重新載入視窗):
1. 關閉所有 VS Code 視窗
2. 重新開啟 VS Code

### 步驟 6: 驗證 MCP Server

1. 打開 GitHub Copilot Chat
2. 輸入 `@` 符號
3. 應該會看到 `@fubon-api` 出現在建議列表中
4. 或者查看 Copilot 設定中的 "Installed MCP Servers"

## 🔍 疑難排解

### 問題 1: MCP Server 仍未出現

**檢查清單:**
- [ ] Python 套件已正確安裝
- [ ] 配置檔案路徑正確
- [ ] JSON 格式正確 (使用 JSON validator 檢查)
- [ ] 已完全重新啟動 VS Code
- [ ] GitHub Copilot 擴展已啟用且已登入

**除錯步驟:**

1. 在終端測試 MCP Server:
```bash
python -m fubon_api_mcp_server.server
```

2. 檢查 VS Code 輸出面板:
   - View > Output
   - 選擇 "GitHub Copilot Chat"
   - 查看是否有 MCP Server 相關錯誤

3. 檢查 Developer Tools:
   - Help > Toggle Developer Tools
   - Console 標籤
   - 搜尋 "MCP" 或 "fubon"

### 問題 2: Server 啟動失敗

**常見原因:**
- Python 路徑不正確
- 套件未安裝或版本不對
- 環境變數設定錯誤
- 憑證檔案路徑錯誤

**解決方法:**

1. 確認 Python 版本:
```bash
python --version  # 應為 3.10+
```

2. 確認套件安裝:
```bash
pip show fubon-api-mcp-server
```

3. 測試手動啟動:
```bash
export FUBON_USERNAME="your_username"
export FUBON_PASSWORD="your_password"
export FUBON_PFX_PATH="/path/to/cert.pfx"
python -m fubon_api_mcp_server.server
```

### 問題 3: 權限錯誤

**Windows:**
確保配置檔案目錄有寫入權限:
```powershell
# 檢查目錄權限
icacls "%APPDATA%\Code\User\globalStorage\github.copilot-chat"
```

**macOS/Linux:**
```bash
# 檢查目錄權限
ls -la ~/Library/Application\ Support/Code/User/globalStorage/github.copilot-chat
# 或
ls -la ~/.config/Code/User/globalStorage/github.copilot-chat

# 如果需要,修正權限
chmod 755 ~/Library/Application\ Support/Code/User/globalStorage/github.copilot-chat
```

## 📝 完整配置範例

### 使用絕對路徑 (Windows)

```json
{
  "mcpServers": {
    "fubon-api": {
      "command": "C:\\Users\\YourName\\AppData\\Local\\Programs\\Python\\Python311\\python.exe",
      "args": ["-m", "fubon_api_mcp_server.server"],
      "env": {
        "FUBON_USERNAME": "A123456789",
        "FUBON_PFX_PATH": "C:\\Users\\YourName\\Documents\\fubon\\cert.pfx",
        "FUBON_DATA_DIR": "C:\\Users\\YourName\\Documents\\fubon\\data"
      }
    }
  }
}
```

### 使用虛擬環境

```json
{
  "mcpServers": {
    "fubon-api": {
      "command": "path/to/venv/bin/python",
      "args": ["-m", "fubon_api_mcp_server.server"],
      "env": {
        "FUBON_USERNAME": "${env:FUBON_USERNAME}",
        "FUBON_PASSWORD": "${env:FUBON_PASSWORD}",
        "FUBON_PFX_PATH": "${env:FUBON_PFX_PATH}",
        "FUBON_PFX_PASSWORD": "${env:FUBON_PFX_PASSWORD}"
      }
    }
  }
}
```

## 🎯 成功標誌

當一切設定正確時,你應該看到:

1. ✅ Copilot Chat 中可以使用 `@fubon-api`
2. ✅ 輸入 `@fubon-api` 後會顯示可用工具列表
3. ✅ 可以執行查詢,例如: `@fubon-api 查詢 2330 的即時報價`
4. ✅ Server 日誌顯示成功連接

## 📚 相關資源

- [MCP Protocol 官方文檔](https://modelcontextprotocol.io/)
- [GitHub Copilot Chat 文檔](https://docs.github.com/en/copilot/github-copilot-chat)
- [Fubon API MCP Server GitHub](https://github.com/Mofesto/fubon-api-mcp-server)

## 💡 提示

- 密碼建議使用環境變數管理,不要直接寫在配置檔中
- 定期檢查 Python 套件更新: `pip install --upgrade fubon-api-mcp-server`
- 可以配置多個 MCP Server,只需在 `mcpServers` 下添加更多項目

## ☕ 支持專案

如果這個專案對您有幫助，歡迎請我喝杯咖啡支持開發！

<div align="center">
  <img src="images/support-qrcode.png" alt="Buy me a coffee" width="200"/>
  <p><i>掃描 QR Code 支持專案</i></p>
</div>

---

如果仍有問題,請到 [GitHub Issues](https://github.com/Mofesto/fubon-api-mcp-server/issues) 回報。
