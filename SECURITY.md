# Security Policy

## 🔒 Security Overview

富邦 MCP 伺服器專案重視安全性。我們致力於確保我們的代碼和依賴項的安全性，並及時回應安全問題。

## 🚨 Reporting Security Vulnerabilities

如果您發現安全漏洞，請**不要**在公開的 GitHub Issues 中回報。請通過以下方式私下聯絡我們：

### 📧 聯絡方式

- **Email**: security@fubon.com
- **PGP Key**: [下載 PGP 公鑰](https://github.com/mofesto/fubon-api-mcp-server/security/pgp-key.asc)

### 📝 回報格式

請在安全回報中包含以下資訊：

- 漏洞描述
- 重現步驟
- 影響範圍
- 建議修復方案
- 您的聯絡資訊（用於跟進）

## 🛡️ Security Measures

### 依賴項安全檢查

我們使用以下工具確保依賴項的安全性：

- **Safety**: 檢查已知的安全漏洞
- **Bandit**: Python 代碼安全檢查
- **Dependabot**: 自動更新依賴項

### 代碼安全實踐

- 輸入驗證和清理
- SQL 注入防護
- XSS 防護
- 敏感資訊處理
- 安全的隨機數生成

## ⏰ Response Timeline

我們致力於在收到安全回報後的時間內回應：

- **初始回應**: 24 小時內
- **漏洞確認**: 72 小時內
- **修復發佈**: 視漏洞嚴重程度而定，通常在 1-4 週內

## 🏷️ Vulnerability Classification

我們使用以下嚴重程度分類：

- **Critical**: 立即威脅，需緊急修復
- **High**: 重大影響，需優先修復
- **Medium**: 中等影響，計劃修復
- **Low**: 輕微影響，低優先級修復

## 📋 Security Updates

### 獲取安全更新

- 訂閱 GitHub Security Advisories
- 關注專案的 Release 頁面
- 定期更新依賴項

### 安全更新流程

1. 發現安全問題
2. 評估影響範圍
3. 開發修復方案
4. 測試修復效果
5. 發佈安全更新
6. 通知用戶

## 🔐 Best Practices for Users

### 環境安全

- 使用虛擬環境隔離依賴項
- 定期更新 Python 和依賴項
- 使用強密碼和憑證管理

### 配置安全

- 不要將敏感資訊提交到版本控制
- 使用環境變數管理憑證
- 限制檔案系統權限

### 網路安全

- 使用 HTTPS 進行 API 通信
- 驗證 SSL 憑證
- 避免在不安全的網路中使用

## 📜 Security Hall of Fame

我們感謝所有幫助提升專案安全性的貢獻者。安全研究員的名字將被添加到此處（如果他們同意）。

## 📞 Contact

如有安全相關問題，請聯絡：security@fubon.com

---

**注意**: 此安全政策適用於富邦 MCP 伺服器專案本身。不涵蓋富邦證券的整體系統安全性。