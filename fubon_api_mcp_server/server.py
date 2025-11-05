"""
FastMCP serve entry for Fubon API MCP Server.

This module registers all MCP tools against the shared FastMCP instance
and then boots the same initialization flow as `server.main()`, finally
serving over stdio. Use this as an alternative entrypoint:

    python -m fubon_api_mcp_server.server

Optional flags:
- --check: validate tool registration and exit
"""

from __future__ import annotations

import argparse
import sys
from typing import Callable, Dict

from .config import mcp
from . import config as config_module

# Import tool functions from services
from .account_service import (
    get_account_info,
    get_bank_balance,
    get_inventory,
    get_settlement_info,
    get_unrealized_pnl,
)
from .historical_data_service import historical_candles
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
from .trading_service import (
    batch_place_order,
    cancel_order,
    modify_price,
    modify_quantity,
    place_order,
)


def _tools_registry() -> Dict[str, Callable]:
    """Return the mapping of tool names to callables."""
    return {
        # Account
        "get_account_info": get_account_info,
        "get_inventory": get_inventory,
        "get_bank_balance": get_bank_balance,
        "get_settlement_info": get_settlement_info,
        "get_unrealized_pnl": get_unrealized_pnl,
        # Trading
        "place_order": place_order,
        "modify_price": modify_price,
        "modify_quantity": modify_quantity,
        "cancel_order": cancel_order,
        "batch_place_order": batch_place_order,
        # Reports
        "get_order_results": get_order_results,
        "get_order_reports": get_order_reports,
        "get_order_changed_reports": get_order_changed_reports,
        "get_filled_reports": get_filled_reports,
        "get_event_reports": get_event_reports,
        "get_all_reports": get_all_reports,
        # Market data
        "get_realtime_quotes": get_realtime_quotes,
        "get_intraday_tickers": get_intraday_tickers,
        "get_intraday_ticker": get_intraday_ticker,
        "get_intraday_quote": get_intraday_quote,
        "get_intraday_candles": get_intraday_candles,
        "get_intraday_trades": get_intraday_trades,
        "get_intraday_volumes": get_intraday_volumes,
        "get_snapshot_quotes": get_snapshot_quotes,
        "get_snapshot_movers": get_snapshot_movers,
        "get_snapshot_actives": get_snapshot_actives,
        "get_historical_stats": get_historical_stats,
        # Historical
        "historical_candles": historical_candles,
    }


# Create callable aliases for backward compatibility and testing
callable_get_account_info = get_account_info
callable_get_inventory = get_inventory
callable_get_bank_balance = get_bank_balance
callable_get_settlement_info = get_settlement_info
callable_get_unrealized_pnl = get_unrealized_pnl
callable_place_order = place_order
callable_modify_price = modify_price
callable_modify_quantity = modify_quantity
callable_cancel_order = cancel_order
callable_batch_place_order = batch_place_order
callable_get_order_results = get_order_results
callable_get_order_reports = get_order_reports
callable_get_order_changed_reports = get_order_changed_reports
callable_get_filled_reports = get_filled_reports
callable_get_event_reports = get_event_reports
callable_get_all_reports = get_all_reports
callable_get_realtime_quotes = get_realtime_quotes
callable_get_intraday_tickers = get_intraday_tickers
callable_get_intraday_ticker = get_intraday_ticker
callable_get_intraday_quote = get_intraday_quote
callable_get_intraday_candles = get_intraday_candles
callable_get_intraday_trades = get_intraday_trades
callable_get_intraday_volumes = get_intraday_volumes
callable_get_snapshot_quotes = get_snapshot_quotes
callable_get_snapshot_movers = get_snapshot_movers
callable_get_snapshot_actives = get_snapshot_actives
callable_get_historical_stats = get_historical_stats
callable_historical_candles = historical_candles


def register_tools() -> None:
    """Register all tools with FastMCP without modifying original functions.

    We apply `mcp.tool(name=...)` decorator at runtime so we do not
    alter the imported callables or tests. If a function appears to be
    already decorated (has attribute `_mcp_tool_registered`), we skip it.
    """
    for name, fn in _tools_registry().items():
        try:
            # Avoid double registration if called multiple times
            if getattr(fn, "_mcp_tool_registered", False):
                continue
            decorated = mcp.tool(name=name)(fn)
            # Mark the original function to prevent duplicate registration
            try:
                setattr(fn, "_mcp_tool_registered", True)
                # Preserve .fn compatibility if missing
                if not hasattr(fn, "fn"):
                    setattr(fn, "fn", fn)
            except Exception:
                pass
            # Keep reference to decorated to avoid GC (not strictly required)
            globals()[f"_mcp_tool_{name}"] = decorated
        except Exception as e:
            print(f"[serve] Failed to register tool {name}: {e}", file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="fubon-mcp-serve", add_help=True)
    parser.add_argument("--check", action="store_true", help="only validate registration and exit")
    args = parser.parse_args(argv)

    # Register tools before server initialization/run
    register_tools()

    # Initialize SDK and login if not already done
    if not config_module.sdk:
        from fubon_neo.sdk import FubonSDK
        config_module.sdk = FubonSDK()
        
        # Login and get accounts
        if config_module.username and config_module.password and config_module.pfx_path:
            try:
                config_module.accounts = config_module.sdk.login(
                    config_module.username, 
                    config_module.password, 
                    config_module.pfx_path, 
                    config_module.pfx_password or ""
                )
                print(f"SDK login successful, accounts loaded: {len(config_module.accounts.data) if config_module.accounts and hasattr(config_module.accounts, 'data') else 0}")
            except Exception as e:
                print(f"SDK login failed: {e}")
                config_module.accounts = None
        else:
            print("Missing credentials for SDK login")
            config_module.accounts = None
    elif not config_module.accounts and config_module.username and config_module.password and config_module.pfx_path:
        # Re-login if accounts is None but SDK exists
        try:
            config_module.accounts = config_module.sdk.login(
                config_module.username, 
                config_module.password, 
                config_module.pfx_path, 
                config_module.pfx_password or ""
            )
            print(f"SDK re-login successful, accounts loaded: {len(config_module.accounts.data) if config_module.accounts and hasattr(config_module.accounts, 'data') else 0}")
        except Exception as e:
            print(f"SDK re-login failed: {e}")
            config_module.accounts = None

    if args.check:
        # Print a short summary and exit
        print("FastMCP tools registered:")
        for k in sorted(_tools_registry().keys()):
            print(f" - {k}")
        return

    # Delegate boot and run to server.main (performs SDK login, callbacks, mcp.run())
    mcp.run()


if __name__ == "__main__":
    main()
