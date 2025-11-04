# Fubon API MCP Server - VS Code Extension

[![VS Code Extension](https://img.shields.io/visual-studio-marketplace/v/mofesto.fubon-api-mcp-server?label=VS%20Code%20Extension)](https://marketplace.visualstudio.com/items?itemName=mofesto.fubon-api-mcp-server)
[![VS Code Extension Downloads](https://img.shields.io/visual-studio-marketplace/d/mofesto.fubon-api-mcp-server)](https://marketplace.visualstudio.com/items?itemName=mofesto.fubon-api-mcp-server)
[![VS Code Extension Rating](https://img.shields.io/visual-studio-marketplace/r/mofesto.fubon-api-mcp-server)](https://marketplace.visualstudio.com/items?itemName=mofesto.fubon-api-mcp-server)

富邦證券 MCP Server 的 VS Code Extension，提供完整的台股交易功能與市場數據查詢。

**Extension ID**: `mofesto.fubon-api-mcp-server`  
**Publisher**: mofesto  
**Version**: 1.8.6

## ✨ 功能特點

- 🚀 **一鍵啟動**: 在 VS Code 中直接啟動 Fubon MCP Server
- 🔧 **便捷配置**: 透過 VS Code 設定管理連線資訊
- 📊 **即時日誌**: 內建輸出面板顯示 server 運行狀態
- 🔄 **快速重啟**: 支援 server 的啟動、停止、重啟操作
- 🔒 **安全輸入**: 密碼輸入不會被儲存在設定檔中

## 📋 安裝需求

- VS Code 1.80.0 或更高版本
- Python 3.10 或更高版本
- fubon-api-mcp-server Python 套件

## 🚀 快速開始

### 1. 安裝 Extension

#### 方式一：從 Marketplace 安裝（推薦）

**Extension ID**: `mofesto.fubon-api-mcp-server`

1. 打開 VS Code
2. 按 `Ctrl+Shift+X` (或 `Cmd+Shift+X`) 打開擴展面板
3. 搜尋 "Fubon API MCP Server"
4. 找到 Publisher 為 **mofesto** 的擴展
5. 點擊 "Install" 按鈕

或直接訪問 Marketplace：  
https://marketplace.visualstudio.com/items?itemName=mofesto.fubon-api-mcp-server

#### 方式二：手動安裝 VSIX

從 [GitHub Releases](https://github.com/Mofesto/fubon-api-mcp-server/releases) 下載 `.vsix` 檔案：

```bash
# 在 VS Code 中：
# Extensions 面板 > ... (更多操作) > Install from VSIX...
# 選擇下載的 .vsix 檔案
```

### 2. 安裝 Python 套件

```bash
pip install fubon-api-mcp-server
```

### 3. 配置 Extension

按 `Ctrl+,` (或 `Cmd+,`) 打開設定，搜尋 "Fubon MCP"：

- **Fubon Mcp: Username**: 您的富邦證券帳號
- **Fubon Mcp: Pfx Path**: PFX 憑證檔案的完整路徑
- **Fubon Mcp: Data Dir**: 本地數據儲存目錄 (選填)
- **Fubon Mcp: Auto Start**: VS Code 啟動時自動啟動 server (選填)

### 4. 啟動 Server

按 `Ctrl+Shift+P` (或 `Cmd+Shift+P`) 打開命令面板，輸入：

- `Fubon MCP: Start Fubon MCP Server` - 啟動 server
- `Fubon MCP: Stop Fubon MCP Server` - 停止 server
- `Fubon MCP: Restart Fubon MCP Server` - 重啟 server
- `Fubon MCP: Show Fubon MCP Server Logs` - 顯示日誌

## ⚙️ 設定項目

| 設定項目 | 類型 | 預設值 | 說明 |
|---------|------|--------|------|
| `fubon-mcp.username` | string | "" | 富邦證券帳號 |
| `fubon-mcp.pfxPath` | string | "" | PFX 憑證檔案路徑 |
| `fubon-mcp.dataDir` | string | "./data" | 本地數據儲存目錄 |
| `fubon-mcp.autoStart` | boolean | false | 自動啟動 server |

## 📖 使用範例

### 在 settings.json 中配置

```json
{
  "fubon-mcp.username": "A123456789",
  "fubon-mcp.pfxPath": "C:\\Users\\YourName\\cert.pfx",
  "fubon-mcp.dataDir": "D:\\FubonData",
  "fubon-mcp.autoStart": false
}
```

### 命令面板操作

1. **啟動 Server**: `Ctrl+Shift+P` → "Fubon MCP: Start"
2. **輸入密碼**: 彈出對話框輸入帳號密碼和憑證密碼
3. **檢視日誌**: `Ctrl+Shift+P` → "Fubon MCP: Show Logs"
4. **停止 Server**: `Ctrl+Shift+P` → "Fubon MCP: Stop"

## 🔒 安全性說明

- ✅ 帳號密碼**不會儲存**在設定檔中
- ✅ 每次啟動時需要重新輸入密碼
- ✅ 密碼輸入框使用遮罩保護
- ✅ 密碼僅存在於 server 運行期間的記憶體中

## 🐛 故障排查

### Server 無法啟動

1. 確認 Python 環境正確: `python --version`
2. 確認套件已安裝: `pip list | grep fubon-api-mcp-server`
3. 檢查設定檔路徑是否正確
4. 查看輸出面板的錯誤訊息

### 連線失敗

1. 確認富邦證券帳號和密碼正確
2. 確認 PFX 憑證檔案有效
3. 確認網路連線正常
4. 查看 server 日誌了解詳細錯誤

### 找不到 Python

Extension 使用系統預設的 `python` 命令。如需指定 Python 路徑：

1. 確保 Python 在系統 PATH 中
2. 或修改 `extension.js` 中的 `spawn('python', ...)` 為完整路徑

## 📚 相關資源
- **VS Code Marketplace**: https://marketplace.visualstudio.com/items?itemName=mofesto.fubon-api-mcp-server

- **PyPI 套件**: https://pypi.org/project/fubon-api-mcp-server/
- **GitHub 專案**: https://github.com/Mofesto/fubon-api-mcp-server
- **問題回報**: https://github.com/Mofesto/fubon-api-mcp-server/issues
- **富邦 API 文檔**: https://www.fbs.com.tw/TradeAPI/docs/

## 🤝 貢獻

歡迎提交 Pull Request 或回報問題！

## ☕ 支持專案

如果這個 Extension 對您有幫助，歡迎請我喝杯咖啡支持開發！

<div align="center">
  <img src="../assets/images/support-qrcode.png" alt="Buy me a coffee" width="200"/>
  <p><i>掃描 QR Code 支持專案</i></p>
</div>

### 開發者資訊

- **Extension ID**: `mofesto.fubon-api-mcp-server`
- **Publisher**: mofesto
- **Repository**: https://github.com/Mofesto/fubon-api-mcp-server
- **Marketplace**: https://marketplace.visualstudio.com/publishers/mofesto


## 📄 授權

MIT License

## ⚠️ 免責聲明

- 本 extension 非富邦證券官方產品
- 使用本軟體需自行承擔風險
- 請遵守相關金融法規和平台使用條款

---

**開發者**: Mofesto.Cui  
**Publisher**: mofesto  
**Extension ID**: mofesto.fubon-api-mcp-server  
**版本**: 1.8.6  
**最後更新**: 2025-11-04
