# MyPy 類型檢查實施指南

## 階段 1: 基礎設置 ✅ 已完成
- ✅ 已安裝 pandas-stubs
- ✅ 寬鬆配置已設置
- ✅ 基本警告已啟用

## 階段 2: 修復核心模塊 ✅ 進行中
已修復的文件:
- ✅ `__init__.py` - 添加 setuptools_scm 類型忽略
- ✅ `utils.py` - 添加完整類型註解
- ✅ `callbacks.py` - 添加回調函數類型註解
- ✅ `server.py` - 添加 callable wrapper 函數類型註解
- ✅ `config.py` - 添加配置變數類型註解
- ✅ `data_handler.py` - 添加數據處理函數類型註解
- ✅ `account_service.py` - 添加帳戶服務函數類型註解

剩餘需要修復的文件:
- ❌ `*_service.py` - 其他服務模塊 (market_data_service, trading_service, reports_service, indicators_service, historical_data_service)

## 階段 3: 啟用隱式可選類型檢查
```bash
# 在 pyproject.toml 中設置:
# no_implicit_optional = true
```

## 階段 4: 啟用函數類型檢查
```bash
# 在 pyproject.toml 中設置:
# disallow_untyped_defs = true
# disallow_incomplete_defs = true
```

## 階段 5: 完整嚴格檢查
```bash
# 啟用所有檢查:
# check_untyped_defs = true
# disallow_untyped_decorators = true
```