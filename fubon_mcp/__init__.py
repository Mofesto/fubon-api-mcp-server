"""
富邦證券 Model Context Protocol (MCP) 服務器包

此包提供完整的富邦證券交易和數據服務，通過 MCP 協議與 AI 助手集成。

主要功能:
- 股票歷史數據查詢（支援本地快取）
- 即時行情數據獲取
- 股票交易下單（買賣、改價、改量、取消）
- 帳戶資訊查詢（資金餘額、庫存、損益）
- 主動回報監聽（委託、成交、事件通知）
- 批量並行下單功能

使用方式:
    from fubon_mcp import main
    main()  # 啟動 MCP 服務器

或通過命令行:
    python -m fubon_mcp.server

環境變數:
- FUBON_USERNAME: 富邦證券帳號
- FUBON_PASSWORD: 登入密碼
- FUBON_PFX_PATH: PFX 憑證檔案路徑
- FUBON_PFX_PASSWORD: PFX 憑證密碼（可選）
- FUBON_DATA_DIR: 本地數據儲存目錄（可選）

作者: Jimmy Cui
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

try:
    from ._version import version as __version__
except ImportError:
    try:
        from setuptools_scm import get_version  # type: ignore[import-not-found]

        __version__ = get_version()
    except ImportError:
        __version__ = "unknown"

__author__ = "Jimmy Cui"

# 匯入主要組件
from .server import (  # Callable wrapper functions for testing
    callable_batch_place_order,
    callable_cancel_order,
    callable_get_account_info,
    callable_get_all_reports,
    callable_get_bank_balance,
    callable_get_event_reports,
    callable_get_filled_reports,
    callable_get_historical_stats,
    callable_get_intraday_candles,
    callable_get_intraday_quote,
    callable_get_intraday_ticker,
    callable_get_intraday_tickers,
    callable_get_intraday_trades,
    callable_get_intraday_volumes,
    callable_get_inventory,
    callable_get_order_changed_reports,
    callable_get_order_reports,
    callable_get_order_results,
    callable_get_realtime_quotes,
    callable_get_settlement_info,
    callable_get_snapshot_actives,
    callable_get_snapshot_movers,
    callable_get_snapshot_quotes,
    callable_get_unrealized_pnl,
    callable_modify_price,
    callable_modify_quantity,
    callable_place_order,
    main,
    mcp,
)

# 定義包的公開介面
__all__ = [
    "mcp",
    "main",
    # Callable wrapper functions
    "callable_get_account_info",
    "callable_get_inventory",
    "callable_get_bank_balance",
    "callable_get_settlement_info",
    "callable_get_unrealized_pnl",
    "callable_place_order",
    "callable_modify_price",
    "callable_modify_quantity",
    "callable_cancel_order",
    "callable_batch_place_order",
    "callable_get_order_results",
    "callable_get_order_reports",
    "callable_get_order_changed_reports",
    "callable_get_filled_reports",
    "callable_get_event_reports",
    "callable_get_all_reports",
    "callable_get_realtime_quotes",
    "callable_get_intraday_tickers",
    "callable_get_intraday_ticker",
    "callable_get_intraday_quote",
    "callable_get_intraday_candles",
    "callable_get_intraday_trades",
    "callable_get_intraday_volumes",
    "callable_get_snapshot_quotes",
    "callable_get_snapshot_movers",
    "callable_get_snapshot_actives",
    "callable_get_historical_stats",
]
