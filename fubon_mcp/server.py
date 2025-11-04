"""
Fubon API MCP Server - Main Entry Point

This is the main entry point for the Fubon API MCP Server.
The server has been refactored into modular components for better maintainability.
"""

import sys
from typing import Any

from fastmcp import FastMCP  # noqa: F401 - Used for MCP tool registration

# Import all service modules to register MCP tools
from . import account_service  # noqa: F401 - Used for MCP tool registration
from . import historical_data_service  # noqa: F401 - Used for MCP tool registration
from . import indicators_service  # noqa: F401 - Used for MCP tool registration
from . import market_data_service  # noqa: F401 - Used for MCP tool registration
from . import reports_service  # noqa: F401 - Used for MCP tool registration
from . import trading_service  # noqa: F401 - Used for MCP tool registration

# Expose functions for backward compatibility with tests
from .account_service import get_account_info, get_bank_balance, get_inventory, get_settlement_info, get_unrealized_pnl

# Import callback functions
from .callbacks import (
    on_event,
    on_filled,
    on_order,
    on_order_changed,
)

# Import configuration and global variables
# Import MCP server instance from config
from .config import (  # noqa: F401 - Used for backward compatibility
    accounts,
    mcp,
    password,
    pfx_password,
    pfx_path,
    reststock,
    sdk,
    username,
)
from .market_data_service import (
    get_historical_stats,
    get_intraday_candles,
    get_intraday_quote,
    get_intraday_ticker,
    get_intraday_tickers,
    get_intraday_trades,
    get_intraday_volumes,
    get_realtime_quotes,
    get_snapshot_actives,
    get_snapshot_movers,
    get_snapshot_quotes,
)
from .reports_service import (
    get_all_reports,
    get_event_reports,
    get_filled_reports,
    get_order_changed_reports,
    get_order_reports,
    get_order_results,
)
from .trading_service import batch_place_order, cancel_order, modify_price, modify_quantity, place_order


# Create callable wrapper functions for testing
def callable_get_account_info(args: Any) -> Any:
    return get_account_info.fn(args)


def callable_get_inventory(args: Any) -> Any:
    return get_inventory.fn(args)


def callable_get_bank_balance(args: Any) -> Any:
    return get_bank_balance.fn(args)


def callable_get_settlement_info(args: Any) -> Any:
    return get_settlement_info.fn(args)


def callable_get_unrealized_pnl(args: Any) -> Any:
    return get_unrealized_pnl.fn(args)


def callable_place_order(args: Any) -> Any:
    return place_order.fn(args)


def callable_modify_price(args: Any) -> Any:
    return modify_price.fn(args)


def callable_modify_quantity(args: Any) -> Any:
    return modify_quantity.fn(args)


def callable_cancel_order(args: Any) -> Any:
    return cancel_order.fn(args)


def callable_batch_place_order(args: Any) -> Any:
    return batch_place_order.fn(args)


def callable_get_order_results(args: Any) -> Any:
    return get_order_results.fn(args)


def callable_get_order_reports(args: Any) -> Any:
    return get_order_reports.fn(args)


def callable_get_order_changed_reports(args: Any) -> Any:
    return get_order_changed_reports.fn(args)


def callable_get_filled_reports(args: Any) -> Any:
    return get_filled_reports.fn(args)


def callable_get_event_reports(args: Any) -> Any:
    return get_event_reports.fn(args)


def callable_get_all_reports(args: Any) -> Any:
    return get_all_reports.fn(args)


def callable_get_realtime_quotes(args: Any) -> Any:
    return get_realtime_quotes.fn(args)


def callable_get_intraday_tickers(args: Any) -> Any:
    return get_intraday_tickers.fn(args)


def callable_get_intraday_ticker(args: Any) -> Any:
    return get_intraday_ticker.fn(args)


def callable_get_intraday_quote(args: Any) -> Any:
    return get_intraday_quote.fn(args)


def callable_get_intraday_candles(args: Any) -> Any:
    return get_intraday_candles.fn(args)


def callable_get_intraday_trades(args: Any) -> Any:
    return get_intraday_trades.fn(args)


def callable_get_intraday_volumes(args: Any) -> Any:
    return get_intraday_volumes.fn(args)


def callable_get_snapshot_quotes(args: Any) -> Any:
    return get_snapshot_quotes.fn(args)


def callable_get_snapshot_movers(args: Any) -> Any:
    return get_snapshot_movers.fn(args)


def callable_get_snapshot_actives(args: Any) -> Any:
    return get_snapshot_actives.fn(args)


def callable_get_historical_stats(args: Any) -> Any:
    return get_historical_stats.fn(args)


def main() -> None:
    """
    應用程式主入口點函數。

    負責初始化富邦證券 SDK、進行身份認證、設定事件回調，
    並啟動 MCP 服務器。這個函數會在程式啟動時執行所有必要的初始化工作。

    初始化流程:
    1. 檢查必要的環境變數（用戶名、密碼、憑證路徑）
    2. 初始化富邦 SDK 實例
    3. 登入到富邦證券系統
    4. 初始化即時資料連線
    5. 設定所有主動回報事件回調函數
    6. 啟動 MCP 服務器

    環境變數需求:
    - FUBON_USERNAME: 富邦證券帳號
    - FUBON_PASSWORD: 登入密碼
    - FUBON_PFX_PATH: PFX 憑證檔案路徑
    - FUBON_PFX_PASSWORD: PFX 憑證密碼（可選）

    如果初始化失敗，程式會輸出錯誤訊息並以錯誤代碼退出。
    """
    from . import config

    try:
        # 檢查必要的環境變數
        if not all([username, password, pfx_path]):
            raise ValueError("FUBON_USERNAME, FUBON_PASSWORD, and FUBON_PFX_PATH environment variables are required")

        print("正在初始化富邦證券SDK...", file=sys.stderr)

        # 初始化 SDK 並登入
        from fubon_neo.sdk import FubonSDK

        config.sdk = FubonSDK()
        config.accounts = config.sdk.login(username, password, pfx_path, pfx_password or "")
        config.sdk.init_realtime()
        config.reststock = config.sdk.marketdata.rest_client.stock

        # 驗證登入是否成功
        if not config.accounts or not hasattr(config.accounts, "is_success") or not config.accounts.is_success:
            raise ValueError("登入失敗，請檢查憑證是否正確")

        # 設定主動回報事件回調函數
        config.sdk.set_on_order(on_order)
        config.sdk.set_on_order_changed(on_order_changed)
        config.sdk.set_on_filled(on_filled)
        config.sdk.set_on_event(on_event)

        print("富邦證券MCP server運行中...", file=sys.stderr)
        mcp.run()
    except Exception as e:
        print(f"啟動伺服器時發生錯誤: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
