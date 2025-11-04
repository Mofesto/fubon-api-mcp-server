# 安裝指南 - Installation Guide

## 安裝方式

### 方式 A: VS Code Extension（推薦）

最簡單的安裝和使用方式是透過 VS Code Extension：

#### 1. 從 Marketplace 安裝

**Extension ID**: `mofesto.fubon-api-mcp-server`

```
1. 打開 VS Code
2. 按 Ctrl+Shift+X (或 Cmd+Shift+X) 打開擴展面板
3. 搜尋 "Fubon API MCP Server"
4. 找到 Publisher 為 "mofesto" 的擴展
5. 點擊 "Install" 按鈕
```

或直接訪問：https://marketplace.visualstudio.com/items?itemName=mofesto.fubon-api-mcp-server

#### 2. 安裝 Python 套件

Extension 需要 Python 套件支援：

```bash
pip install fubon-api-mcp-server
```

#### 3. 配置 Extension

按 `Ctrl+,` 打開設定，搜尋 "Fubon MCP"：
- **Username**: 您的富邦證券帳號
- **Pfx Path**: PFX 憑證檔案完整路徑
- **Data Dir**: 數據儲存目錄（選填）
- **Auto Start**: 自動啟動（選填）

#### 4. 使用 Extension

按 `Ctrl+Shift+P` 打開命令面板：
- `Fubon MCP: Start Fubon MCP Server` - 啟動服務
- `Fubon MCP: Stop Fubon MCP Server` - 停止服務
- `Fubon MCP: Restart Fubon MCP Server` - 重啟服務
- `Fubon MCP: Show Fubon MCP Server Logs` - 查看日誌

✅ **優點**: 一鍵操作、密碼安全輸入、即時日誌顯示

---

## 方式 B: Python Package 安裝

### 方法 1: 從 PyPI 安裝 (推薦)

```bash
pip install fubon-api-mcp-server
```

**注意**: 由於 `fubon_neo` 是富邦證券的私有套件，PyPI 版本可能無法直接安裝所有依賴。

### 方法 2: 從原始碼安裝 (包含私有套件)

```bash
# 1. Clone 專案
git clone https://github.com/Mofesto/fubon-api-mcp-server.git
cd fubon-api-mcp-server

# 2. 創建虛擬環境
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

# 3. 安裝依賴 (包含本地 wheel)
pip install -r requirements.txt

# 4. 安裝專案
pip install -e .
```

## fubon_neo 套件說明

### 什麼是 fubon_neo？

`fubon_neo` 是富邦證券提供的 Python SDK，用於存取富邦證券交易 API。

### 為什麼包含在專案中？

- **私有套件**: fubon_neo 不在 PyPI 上公開發布
- **CI/CD 需求**: GitHub Actions 需要能夠安裝此套件
- **便利性**: 使用者無需額外下載

### Wheel 文件位置

```
wheels/
├── fubon_neo-2.2.5-cp37-abi3-win_amd64.whl              # Windows
├── fubon_neo-2.2.5-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl  # Linux
├── fubon_neo-2.2.5-cp37-abi3-macosx_11_0_arm64.whl      # macOS ARM64 (M1/M2/M3/M4)
└── fubon_neo-2.2.5-cp37-abi3-macosx_10_12_x86_64.whl    # macOS Intel
```

### 支援的平台

| 平台 | 架構 | Python 版本 | 狀態 |
|------|------|-------------|------|
| **Windows** | AMD64 | 3.7+ | ✅ 完整支援 |
| **Linux** | x86_64 | 3.7+ | ✅ 完整支援 |
| **macOS** | ARM64 (Apple Silicon) | 3.7+ | ✅ 完整支援 |
| **macOS** | Intel (x86_64) | 3.7+ | ✅ 完整支援 |

### 自動平台選擇

使用 `requirements.txt` 安裝時會自動選擇正確的 wheel：

```bash
pip install -r requirements.txt
```

pip 會根據你的作業系統自動選擇：
- Windows: `fubon_neo-2.2.5-cp37-abi3-win_amd64.whl`
- Linux: `fubon_neo-2.2.5-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`
- macOS ARM64 (M1/M2/M3/M4): `fubon_neo-2.2.5-cp37-abi3-macosx_11_0_arm64.whl`
- macOS Intel: `fubon_neo-2.2.5-cp37-abi3-macosx_10_12_x86_64.whl`

## 開發者安裝

### 開發依賴

```bash
# 安裝完整的開發依賴
pip install -e ".[dev]"
```

包含的開發工具：
- pytest, pytest-cov, pytest-xdist, pytest-mock (測試)
- black, isort, flake8 (代碼格式化和檢查)
- mypy (型別檢查)
- bandit, safety (安全檢查)

### 文檔依賴

```bash
pip install -e ".[docs]"
```

## 疑難排解

### 問題: 找不到 fubon_neo

**解決方案 1**: 確認使用本地 wheel
```bash
# 自動選擇 (推薦)
pip install -r requirements.txt

# 或手動指定:
# Windows
pip install ./wheels/fubon_neo-2.2.5-cp37-abi3-win_amd64.whl

# Linux
pip install ./wheels/fubon_neo-2.2.5-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl

# macOS ARM64 (M1/M2/M3/M4)
pip install ./wheels/fubon_neo-2.2.5-cp37-abi3-macosx_11_0_arm64.whl

# macOS Intel
pip install ./wheels/fubon_neo-2.2.5-cp37-abi3-macosx_10_12_x86_64.whl
```

**解決方案 2**: 檢查平台相容性
```bash
# 檢查當前平台
python -c "import sys, platform; print(f'OS: {sys.platform}, Arch: {platform.machine()}')"

# Windows: 應顯示 OS: win32, Arch: AMD64
# Linux: 應顯示 OS: linux, Arch: x86_64
# macOS ARM64: 應顯示 OS: darwin, Arch: arm64
# macOS Intel: 應顯示 OS: darwin, Arch: x86_64
```

### 問題: Wheel 不相容

所有主流平台的 wheel 都已包含在專案中。如果仍遇到問題：

```bash
# 1. 確認您的平台
python -c "import sys, platform; print(f'Platform: {sys.platform}, Machine: {platform.machine()}')"

# 2. 確認 wheels 目錄完整
ls wheels/  # macOS/Linux
dir wheels\  # Windows

# 3. 嘗試重新安裝
pip install --force-reinstall -r requirements.txt
```

### 問題: CI/CD 失敗

GitHub Actions 會自動使用 wheels 目錄中的 wheel。如果失敗：

1. 確認 wheels 目錄已提交到 Git
2. 確認 requirements.txt 指向正確的 wheel 路徑
3. 檢查 GitHub Actions logs

## 授權和使用條款

**重要**: fubon_neo 是富邦證券的專有軟體

- ✅ **允許**: 已授權的富邦證券客戶使用
- ❌ **禁止**: 未經授權的分發和商業使用
- 📜 **授權**: 請參考富邦證券的使用條款

使用本軟體即表示您同意遵守富邦證券的服務條款。

## 更新 fubon_neo

當富邦證券發布新版本時：

```bash
# 1. 下載新版本的 wheel
# 2. 替換 wheels 目錄中的舊文件
# 3. 更新 requirements.txt 中的檔案名稱
# 4. 提交變更

git add wheels/ requirements.txt
git commit -m "chore: update fubon_neo to version X.X.X"
git push
```

## 取得協助

- **專案問題**: https://github.com/Mofesto/fubon-api-mcp-server/issues
- **VS Code Extension**: https://marketplace.visualstudio.com/items?itemName=mofesto.fubon-api-mcp-server
- **富邦 API**: https://www.fbs.com.tw/TradeAPI/docs/
- **文檔**: https://github.com/Mofesto/fubon-api-mcp-server#readme

---

**最後更新**: 2025-11-04
**當前版本**: 1.8.6
**Extension ID**: mofesto.fubon-api-mcp-server
**fubon_neo 版本**: 2.2.5
