# MyPy 類型檢查實施指南

## 階段 1: 基礎設置 (當前狀態)
- ✅ 已安裝 pandas-stubs
- ✅ 寬鬆配置已設置
- ✅ 基本警告已啟用

## 階段 2: 啟用隱式可選類型檢查
```bash
# 在 pyproject.toml 中設置:
# no_implicit_optional = true
```

需要修復的常見問題:
- 將 `def func(arg=None)` 改為 `def func(arg: Optional[Type] = None)`
- 添加必要的 `from typing import Optional`

## 階段 3: 啟用函數類型檢查
```bash
# 在 pyproject.toml 中設置:
# disallow_untyped_defs = true
# disallow_incomplete_defs = true
```

需要修復的問題:
- 為所有函數添加類型註解
- 修復 None 屬性訪問問題
- 解決不可達代碼問題

## 階段 4: 完整嚴格檢查
```bash
# 啟用所有檢查:
# check_untyped_defs = true
# disallow_untyped_decorators = true
```

## 優先修復文件順序
1. `fubon_mcp/__init__.py` - 簡單的版本處理
2. `fubon_mcp/utils.py` - 工具函數
3. `fubon_mcp/callbacks.py` - 回調函數
4. `fubon_mcp/server.py` - MCP 服務器接口
5. 其他服務文件 (market_data_service.py, trading_service.py 等)

## 常用類型註解模式
```python
from typing import Optional, Dict, List, Any, Union
from fubon_neo.sdk import FubonSDK  # 假設的類型

def get_market_data(symbol: str, sdk: Optional[FubonSDK] = None) -> Dict[str, Any]:
    if sdk is None:
        return {}
    # 使用 sdk.marketdata 等
    return sdk.marketdata.get(symbol)
```

## 測試驗證
每次階段完成後運行:
```bash
python validate_ci.py  # 確保 CI 仍然通過
python -m mypy fubon_mcp  # 檢查類型錯誤
```