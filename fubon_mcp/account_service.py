"""
Account service module for Fubon API MCP Server.

This module contains MCP tools related to account management,
including balance, inventory, settlement, and financial information.
"""

from typing import Any, Dict

from . import config as config_module  # 導入 config 模組
from .config import mcp
from .models import GetAccountInfoArgs, GetBankBalanceArgs, GetInventoryArgs, GetSettlementArgs, GetUnrealizedPnLArgs
from .utils import _safe_api_call, validate_and_get_account

# =============================================================================
# Account Information Functions
# =============================================================================


def _get_all_accounts_basic_info() -> Dict:
    """Get basic information for all accounts"""
    # Check if accounts were successfully retrieved
    if (
        not config_module.accounts
        or not hasattr(config_module.accounts, "is_success")
        or not config_module.accounts.is_success
    ):
        return {
            "status": "error",
            "data": None,
            "message": "Account authentication failed, please check if credentials have expired",
        }

    account_list = []
    if hasattr(config_module.accounts, "data") and config_module.accounts.data:
        for acc in config_module.accounts.data:
            account_info = {
                "name": getattr(acc, "name", "N/A"),
                "branch_no": getattr(acc, "branch_no", "N/A"),
                "account": getattr(acc, "account", "N/A"),
                "account_type": getattr(acc, "account_type", "N/A"),
            }
            account_list.append(account_info)

    return {
        "status": "success",
        "data": account_list,
        "message": f"Successfully retrieved {len(account_list)} accounts basic info. For detailed financial info, please specify account number.",
    }


def _get_basic_account_info(account_obj: Any) -> Dict[str, Any]:
    """Get basic account information"""
    return {
        "basic_info": {
            "name": getattr(account_obj, "name", "N/A"),
            "branch_no": getattr(account_obj, "branch_no", "N/A"),
            "account": getattr(account_obj, "account", "N/A"),
            "account_type": getattr(account_obj, "account_type", "N/A"),
        }
    }


def _get_account_financial_info(account_obj: Any) -> Dict[str, Any]:
    """Get account financial information"""
    info = {}

    # Check if SDK is initialized
    if not config_module.sdk or not config_module.sdk.accounting:
        return {"error": "SDK not initialized or accounting module not available"}

    # Assert SDK is available for type checker
    assert config_module.sdk is not None and config_module.sdk.accounting is not None

    # Get bank balance
    info["bank_balance"] = _safe_api_call(
        lambda: config_module.sdk.accounting.bank_remain(account_obj), "Failed to get bank balance"  # type: ignore[union-attr]
    )

    # Get unrealized P&L
    info["unrealized_pnl"] = _safe_api_call(
        lambda: config_module.sdk.accounting.unrealized_gains_and_loses(account_obj), "Failed to get unrealized P&L"  # type: ignore[union-attr]
    )

    # Get settlement info (today)
    info["settlement_today"] = _safe_api_call(
        lambda: config_module.sdk.accounting.query_settlement(account_obj, "0d"), "Failed to get settlement info"  # type: ignore[union-attr]
    )

    return info


@mcp.tool()
def get_account_info(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get account information including balance, inventory, P&L, etc.

    Args:
        account (str): Account number. If empty, returns basic info for all accounts
    """
    try:
        validated_args = GetAccountInfoArgs(**args)
        account = validated_args.account

        # If no account specified, return basic info for all accounts
        if not account:
            return _get_all_accounts_basic_info()

        # Validate and get account object
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # Get detailed account information
        account_details = _get_basic_account_info(account_obj)
        account_details.update(_get_account_financial_info(account_obj))

        return {
            "status": "success",
            "data": account_details,
            "message": f"Successfully retrieved detailed info for account {account}",
        }

    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get account info: {str(e)}"}


@mcp.tool()
def get_inventory(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get account inventory information

    Args:
        account (str): Account number
    """
    try:
        validated_args = GetInventoryArgs(**args)
        account = validated_args.account

        # Validate and get account object
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # Check if SDK is initialized
        if not config_module.sdk or not config_module.sdk.accounting:
            return {"status": "error", "data": None, "message": "SDK not initialized or accounting module not available"}

        # Get inventory information
        inventory = config_module.sdk.accounting.inventories(account_obj)
        if inventory and hasattr(inventory, "is_success") and inventory.is_success:
            return {
                "status": "success",
                "data": inventory.data if hasattr(inventory, "data") else inventory,
                "message": f"Successfully retrieved inventory for account {account}",
            }
        else:
            return {"status": "error", "data": None, "message": f"Unable to get inventory for account {account}"}

    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get inventory: {str(e)}"}


@mcp.tool()
def get_unrealized_pnl(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get unrealized P&L information

    Args:
        account (str): Account number
    """
    try:
        validated_args = GetUnrealizedPnLArgs(**args)
        account = validated_args.account

        # Validate and get account object
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # Check if SDK is initialized
        if not config_module.sdk or not config_module.sdk.accounting:
            return {"status": "error", "data": None, "message": "SDK not initialized or accounting module not available"}

        # Get unrealized P&L
        unrealized_pnl = config_module.sdk.accounting.unrealized_gains_and_loses(account_obj)
        if unrealized_pnl and hasattr(unrealized_pnl, "is_success") and unrealized_pnl.is_success:
            return {
                "status": "success",
                "data": unrealized_pnl.data if hasattr(unrealized_pnl, "data") else unrealized_pnl,
                "message": f"Successfully retrieved unrealized P&L for account {account}",
            }
        else:
            return {"status": "error", "data": None, "message": f"Unable to get unrealized P&L for account {account}"}

    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get unrealized P&L: {str(e)}"}


@mcp.tool()
def get_settlement_info(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get settlement information (receivables/payables)

    Args:
        account (str): Account number
        days (str): Query days, default "0d" (today), options "1d", "2d", "3d"
    """
    try:
        validated_args = GetSettlementArgs(**args)
        account = validated_args.account
        days = validated_args.days

        # Validate and get account object
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # Check if SDK is initialized
        if not config_module.sdk or not config_module.sdk.accounting:
            return {"status": "error", "data": None, "message": "SDK not initialized or accounting module not available"}

        # Get settlement information
        settlement = config_module.sdk.accounting.query_settlement(account_obj, days)
        if settlement and hasattr(settlement, "is_success") and settlement.is_success:
            return {
                "status": "success",
                "data": settlement.data if hasattr(settlement, "data") else settlement,
                "message": f"Successfully retrieved {days} settlement info for account {account}",
            }
        else:
            return {"status": "error", "data": None, "message": f"Unable to get settlement info for account {account}"}

    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get settlement info: {str(e)}"}


@mcp.tool()
def get_bank_balance(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get account bank balance (funds balance)

    Args:
        account (str): Account number
    """
    try:
        validated_args = GetBankBalanceArgs(**args)
        account = validated_args.account

        # Validate and get account object
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # Check if SDK is initialized
        if not config_module.sdk or not config_module.sdk.accounting:
            return {"status": "error", "data": None, "message": "SDK not initialized or accounting module not available"}

        # Get bank balance information
        bank_balance = config_module.sdk.accounting.bank_remain(account_obj)
        if bank_balance and hasattr(bank_balance, "is_success") and bank_balance.is_success:
            return {
                "status": "success",
                "data": bank_balance.data if hasattr(bank_balance, "data") else bank_balance,
                "message": f"Successfully retrieved bank balance for account {account}",
            }
        else:
            return {"status": "error", "data": None, "message": f"Unable to get bank balance for account {account}"}

    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get bank balance: {str(e)}"}
