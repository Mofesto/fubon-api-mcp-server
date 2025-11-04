"""
Utility functions for Fubon API MCP Server.

This module contains shared utility functions used across different
services, including account validation, error handling, and API calls.
"""

import functools
import sys
import traceback
from typing import Any, Callable, Optional, Tuple, Union

from . import config as config_module

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
            print(error_text, file=sys.stderr)

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
    # Check if accounts were successfully retrieved
    if (
        not config_module.accounts
        or not hasattr(config_module.accounts, "is_success")
        or not config_module.accounts.is_success
    ):
        return None, "Account authentication failed, please check if credentials have expired"

    # Find the corresponding account object
    account_obj = None
    if hasattr(config_module.accounts, "data") and config_module.accounts.data:
        for acc in config_module.accounts.data:
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
