"""
Utility functions for Fubon API MCP Server.

This module contains shared utility functions used across different
services, including account validation, error handling, and API calls.
"""

import functools
import logging
import traceback
from typing import Any, Callable, List, Optional, Tuple, Union

from . import config as config_module

logger = logging.getLogger(__name__)

# =============================================================================
# Error Handling Decorator
# =============================================================================


def handle_exceptions(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Exception handling decorator.

    Adds global exception handling to functions. When a function execution
    encounters an exception, it captures and outputs detailed error information
    to stderr.

    Args:
        func: The function to decorate

    Returns:
        wrapper: The decorated function
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as exp:
            # Extract the full traceback
            tb_lines = traceback.format_exc().splitlines()

            # Find the index of the line related to the original function
            func_line_index = next((i for i, line in enumerate(tb_lines) if func.__name__ in line), -1)

            # Highlight the specific part in the traceback where the exception occurred
            relevant_tb = "\n".join(tb_lines[func_line_index:])  # Include traceback from the function name

            error_text = f"{func.__name__} exception: {exp}\nTraceback (most recent call last):\n{relevant_tb}"
            logger.exception(error_text)

            # For Jupyter environments, don't exit
            # os._exit(-1)

    return wrapper


# =============================================================================
# Account Validation Functions
# =============================================================================


def validate_and_get_account(account: str) -> Tuple[Optional[Any], Optional[str]]:
    """
    Validate account and return account object.

    Args:
        account (str): Account number

    Returns:
        tuple: (account_obj, error_message) - If successful, account_obj is the account object, error_message is None
               If failed, account_obj is None, error_message is the error message
    """
    try:
        import os
        from pathlib import Path

        from dotenv import load_dotenv
        from fubon_neo.sdk import FubonSDK

        # Load .env file from the project root
        project_root = Path(__file__).parent.parent
        env_path = project_root / ".env"
        load_dotenv(env_path)

        # Check if SDK is already initialized
        if config_module.sdk is None:
            logger.debug("Initializing SDK and logging in for account validation...")
            # Get credentials from environment
            username = os.getenv("FUBON_USERNAME")
            password = os.getenv("FUBON_PASSWORD")
            pfx_path = os.getenv("FUBON_PFX_PATH")
            pfx_password = os.getenv("FUBON_PFX_PASSWORD", "")

            if not username or not password or not pfx_path:
                return None, "Account authentication failed, please check if credentials have expired"

            sdk = FubonSDK()
            # Login and get accounts
            accounts = sdk.login(username, password, pfx_path, pfx_password)

            if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
                return None, "Account authentication failed, please check if credentials have expired"

            # Store in config_module for reuse
            config_module.sdk = sdk
            config_module.accounts = accounts
        else:
            logger.debug("Reusing existing SDK for account validation...")
            accounts = config_module.accounts

        # Note: reststock is initialized only when needed for market data operations

    except Exception as e:
        return None, f"Account authentication failed: {str(e)}"

    # Find the corresponding account object
    account_obj = None
    if hasattr(accounts, "data") and accounts.data:
        for acc in accounts.data:
            if getattr(acc, "account", None) == account:
                account_obj = acc
                break

    if not account_obj:
        return None, f"account {account} not found"

    return account_obj, None


def get_order_by_no(account_obj: Any, order_no: str) -> Tuple[Optional[Any], Optional[str]]:
    """
    Get order object by order number.

    Args:
        account_obj: Account object
        order_no (str): Order number

    Returns:
        tuple: (order_obj, error_message) - If successful, order_obj is the order object, error_message is None
               If failed, order_obj is None, error_message is the error message
    """
    try:
        if not config_module.sdk or not config_module.sdk.stock:
            return None, "SDK not initialized or stock module not available"

        order_results = config_module.sdk.stock.get_order_results(account_obj)
        if not (order_results and hasattr(order_results, "is_success") and order_results.is_success):
            return None, "Unable to get account order results"

        # Find the corresponding order
        target_order = None
        if hasattr(order_results, "data") and order_results.data:
            for order in order_results.data:
                if getattr(order, "order_no", None) == order_no:
                    target_order = order
                    break

        if not target_order:
            return None, f"Order number {order_no} not found"

        return target_order, None
    except Exception as e:
        return None, f"Error getting order results: {str(e)}"


# =============================================================================
# API Call Helper
# =============================================================================


def _safe_api_call(api_func: Callable[[], Any], error_prefix: str) -> Union[Any, str, None]:
    """
    Safely call API function with error handling.

    Args:
        api_func: The API function to call
        error_prefix (str): Prefix for error messages

    Returns:
        The API result data or error message string
    """
    try:
        result = api_func()
        if result and hasattr(result, "is_success") and result.is_success:
            return result.data
        else:
            return None
    except Exception as e:
        return f"{error_prefix}: {str(e)}"


def normalize_item(item: Any, keys: List[str]) -> dict:
    """
    Normalize an SDK object or a dict into a plain dict with requested keys.

    Args:
        item: SDK object or dict
        keys: list of attribute names to extract

    Returns:
        dict: key -> value (defaults: numeric-like fields -> 0, others -> empty string)

    Numeric-like detection uses substrings: price, quantity, value, cost, profit, loss, amount
    """
    result = {}

    def _default_for(k: str):
        if any(x in k for x in ("price", "quantity", "value", "cost", "profit", "loss", "amount")):
            return 0
        return ""

    if isinstance(item, dict):
        for k in keys:
            v = item.get(k, None)
            # Treat explicit None as missing
            result[k] = v if v is not None else _default_for(k)
        return result

    # SDK object: use getattr
    for k in keys:
        v = getattr(item, k, None)
        result[k] = v if v is not None else _default_for(k)

    return result
