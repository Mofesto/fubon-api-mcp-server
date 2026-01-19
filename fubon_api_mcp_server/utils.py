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


def validate_api_key_credentials(api_key: str, secret_key: str) -> Tuple[bool, str]:
    """
    Validate API-Key credentials format and non-empty values.

    Args:
        api_key (str): Fubon API Key
        secret_key (str): Fubon API Secret

    Returns:
        tuple: (is_valid, error_message)
            - (True, "") if credentials are valid
            - (False, error_message) if validation fails

    Error messages are bilingual (English + Traditional Chinese 繁體中文)
    """
    # Check if API-Key is empty or None
    if not api_key or not isinstance(api_key, str) or not api_key.strip():
        return False, "API Key is required / 需要 API 金鑰"

    # Check if Secret is empty or None
    if not secret_key or not isinstance(secret_key, str) or not secret_key.strip():
        return False, "API Secret is required / 需要 API 祕密"

    # Basic format validation (API keys are typically alphanumeric with hyphens)
    if len(api_key.strip()) < 10:
        return False, "Invalid API Key format (too short) / 無效的 API 金鑰格式 (太短)"

    if len(secret_key.strip()) < 10:
        return False, "Invalid API Secret format (too short) / 無效的 API 祕密格式 (太短)"

    # All checks passed
    return True, ""


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

            # Detect authentication method: API-Key vs Traditional PFX
            api_key = os.getenv("FUBON_API_KEY")
            api_secret = os.getenv("FUBON_API_SECRET")
            username = os.getenv("FUBON_USERNAME")
            password = os.getenv("FUBON_PASSWORD")
            pfx_path = os.getenv("FUBON_PFX_PATH")
            pfx_password = os.getenv("FUBON_PFX_PASSWORD", "")

            sdk = FubonSDK()

            # Attempt API-Key authentication if credentials are present
            if api_key and api_secret:
                logger.debug("Using API-Key authentication (SDK v2.2.7+)")
                # Validate API-Key credentials
                is_valid, error_msg = validate_api_key_credentials(api_key, api_secret)
                if not is_valid:
                    return None, error_msg

                # API-Key login (SDK v2.2.7+ method signature)
                # Note: Actual method name/signature depends on SDK v2.2.7 documentation
                # This is a placeholder - adjust based on actual SDK API
                try:
                    accounts = sdk.login(api_key=api_key, secret_key=api_secret)
                except TypeError:
                    # Fallback if SDK doesn't support keyword args or method doesn't exist yet
                    return None, "API-Key authentication not supported by installed SDK version / SDK 版本不支援 API 金鑰驗證"

            # Otherwise use traditional PFX authentication
            elif username and password and pfx_path:
                logger.debug("Using traditional PFX authentication")
                accounts = sdk.login(username, password, pfx_path, pfx_password)

            else:
                return (
                    None,
                    "No valid credentials found. Provide either (FUBON_API_KEY + FUBON_API_SECRET) or (FUBON_USERNAME + FUBON_PASSWORD + FUBON_PFX_PATH) / 未找到有效憑證。請提供 (FUBON_API_KEY + FUBON_API_SECRET) 或 (FUBON_USERNAME + FUBON_PASSWORD + FUBON_PFX_PATH)",
                )

            if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
                return (
                    None,
                    "Account authentication failed, please check if credentials have expired / 帳戶驗證失敗，請檢查憑證是否已過期",
                )

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


# =============================================================================
# Certificate Export (SDK v2.2.7+ Feature)
# =============================================================================


def export_certificate(password: str, output_path: str) -> Tuple[bool, str]:
    """
    Export certificate to file (SDK v2.2.7+ feature).

    This function wraps the SDK's certificate export capability, which exports
    the user's web certificate in PKCS#12 (.pfx) format. The exported certificate
    can be used for authentication in other applications or environments.

    Args:
        password (str): Password to protect the exported certificate
        output_path (str): Absolute path where certificate will be saved (e.g., "/path/to/cert.pfx")

    Returns:
        tuple: (success, message)
            - (True, "Certificate exported successfully / 憑證匯出成功") if export succeeds
            - (False, error_message) if export fails

    Error messages are bilingual (English + Traditional Chinese 繁體中文)

    Example:
        >>> success, msg = export_certificate("MySecurePassword", "/tmp/exported.pfx")
        >>> if success:
        ...     print("Certificate exported successfully")
        ... else:
        ...     print(f"Export failed: {msg}")

    References:
        - specs/001-sdk-v2.2.7-upgrade/tasks.md: T022
        - specs/001-sdk-v2.2.7-upgrade/research.md: Certificate export format (PKCS#12)
    """
    try:
        # Validate password
        if not password or not isinstance(password, str) or not password.strip():
            return False, "Certificate export failed: invalid password / 憑證匯出失敗: 密碼無效"

        # Check SDK initialization
        if config_module.sdk is None:
            return False, "SDK not initialized / SDK 未初始化"

        # Check if output path directory exists
        from pathlib import Path

        output_file = Path(output_path)
        if not output_file.parent.exists():
            return False, "Export path is not writable / 匯出路徑不可寫入"

        # Call SDK export function
        try:
            result = config_module.sdk.export_certificate(password=password)
        except AttributeError:
            return (
                False,
                "Certificate export not supported by installed SDK version / SDK 版本不支援憑證匯出功能",
            )
        except Exception as e:
            return False, f"Certificate export failed: {str(e)} / 憑證匯出失敗: {str(e)}"

        # Check if export succeeded
        if not result or not hasattr(result, "is_success") or not result.is_success:
            error_msg = getattr(result, "message", "Unknown error")
            return False, f"Certificate export failed: {error_msg} / 憑證匯出失敗: {error_msg}"

        # Write certificate data to file
        try:
            cert_data = result.data
            if not cert_data:
                return False, "Certificate export failed: no data returned / 憑證匯出失敗: 未返回數據"

            # Write binary data (PKCS#12 format)
            with open(output_path, "wb") as f:
                f.write(cert_data)

            return True, "Certificate exported successfully / 憑證匯出成功"

        except IOError as e:
            return False, f"Export path is not writable: {str(e)} / 匯出路徑不可寫入: {str(e)}"
        except Exception as e:
            return False, f"Failed to write certificate file: {str(e)} / 寫入憑證檔案失敗: {str(e)}"

    except Exception as e:
        return False, f"Certificate export error: {str(e)} / 憑證匯出錯誤: {str(e)}"
