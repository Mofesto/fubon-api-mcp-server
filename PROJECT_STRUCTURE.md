# 專案結構說明

## 目錄結構

```
fubon-api-mcp-server/
├── .github/              # GitHub Actions CI/CD 配置
├── assets/               # 資源文件 (圖片、QR Code等)
├── data/                 # 運行時數據目錄 (gitignore)
├── examples/             # 使用範例
├── fubon_mcp/            # 核心源代碼
├── log/                  # 日誌文件目錄 (gitignore)
├── scripts/              # 自動化腳本
│   ├── version_config.json      # 版本和配置管理
│   ├── release.ps1              # 發布流程腳本
│   ├── update_version.ps1       # 版本更新腳本
│   └── generate_release_notes.ps1  # 發布說明生成腳本
├── tests/                # 測試文件
├── vscode-extension/     # VS Code 擴展源代碼
├── wheels/               # 私有包輪子
└── [配置文件]            # pyproject.toml, setup.py 等

## 核心文件

- **README.md**: 專案主要文檔
- **INSTALL.md**: 安裝指南
- **CHANGELOG.md**: 變更日誌
- **CONTRIBUTING.md**: 貢獻指南
- **SECURITY.md**: 安全政策
- **CODE_OF_CONDUCT.md**: 行為準則
- **pyproject.toml**: Python 專案配置
- **setup.py**: 打包配置
- **requirements.txt**: 依賴清單

## 開發工作流

### 版本更新
```powershell
.\scripts\update_version.ps1 -Version "x.y.z"
```

### 發布新版本
```powershell
.\scripts\release.ps1 -BumpType [major|minor|patch]
```

### 運行測試
```powershell
pytest
```

### 安裝開發環境
```powershell
pip install -e .[dev]
```

## 自動忽略的文件/目錄

以下內容會被 git 忽略(見 `.gitignore`):
- `__pycache__/`, `*.pyc`: Python 編譯文件
- `dist/`, `build/`, `*.egg-info/`: 構建產物
- `.coverage`, `htmlcov/`: 測試覆蓋率報告
- `log/`, `data/`: 運行時生成的日誌和數據
- `.venv/`, `.env`: 虛擬環境和敏感配置
- `fubon_mcp/_version.py`: 自動生成的版本文件

## 版本管理

本專案使用 `setuptools-scm` 從 Git 標籤動態生成版本號。

版本配置集中管理於 `scripts/version_config.json`，自動化腳本會同步更新所有相關文件。
