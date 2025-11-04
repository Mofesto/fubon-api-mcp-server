"""
Trading service module for Fubon API MCP Server.

This module contains MCP tools for trading operations including
order placement, modification, cancellation, and batch operations.
"""

import concurrent.futures
from typing import Any, Dict, Optional

from .config import accounts, mcp, sdk
from . import config
from .models import BatchPlaceOrderArgs, CancelOrderArgs, ModifyPriceArgs, ModifyQuantityArgs, PlaceOrderArgs
from .utils import validate_and_get_account

# =============================================================================
# Order Management Helper Functions
# =============================================================================


def _find_target_order(order_results: Any, order_no: str) -> Optional[Any]:
    """Find target order from order results"""
    if hasattr(order_results, "data") and order_results.data:
        for order in order_results.data:
            if getattr(order, "order_no", None) == order_no:
                return order
    return None  # Explicit return for mypy


def _create_modify_object(target_order: Any, modify_value: Any, modify_type: str) -> Optional[Any]:
    """Create modification object"""
    if modify_type not in ("quantity", "price"):
        raise ValueError(f"Unsupported modification type: {modify_type}")

    if config.sdk is None or config.sdk.stock is None:
        raise ValueError("SDK not initialized or stock module not available")

    if modify_type == "quantity":
        return config.sdk.stock.make_modify_quantity_obj(target_order, modify_value)
    elif modify_type == "price":
        return config.sdk.stock.make_modify_price_obj(target_order, str(modify_value))
    else:
        # This should never happen due to the check above, but keep for type checkers
        raise ValueError(f"Unsupported modification type: {modify_type}")


def _execute_modify_operation(account_obj: Any, modify_obj: Any, modify_type: str) -> Any:
    """Execute modification operation"""
    if modify_type not in ("quantity", "price"):
        raise ValueError(f"Unsupported modification type: {modify_type}")

    if config.sdk is None or config.sdk.stock is None:
        raise ValueError("SDK not initialized or stock module not available")

    if modify_type == "quantity":
        return config.sdk.stock.modify_quantity(account_obj, modify_obj)
    elif modify_type == "price":
        return config.sdk.stock.modify_price(account_obj, modify_obj)
    else:
        # This should never happen due to the check above, but mypy needs it
        raise ValueError(f"Unsupported modification type: {modify_type}")


def _modify_order(account: str, order_no: str, modify_value: Any, modify_type: str) -> Dict[str, Any]:
    """
    Generic order modification function

    Args:
        account (str): Account number
        order_no (str): Order number
        modify_value: Modification value (quantity or price)
        modify_type (str): Modification type 'quantity' or 'price'
    """
    try:
        # Validate and get account object
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # Check if SDK is initialized
        if not config.sdk or not config.sdk.stock:
            return {"status": "error", "data": None, "message": "SDK not initialized or stock module not available"}

        # Get order results
        order_results = config.sdk.stock.get_order_results(account_obj)
        if not (order_results and hasattr(order_results, "is_success") and order_results.is_success):
            return {"status": "error", "data": None, "message": f"Unable to get order results for account {account}"}

        # Find target order
        target_order = _find_target_order(order_results, order_no)
        if not target_order:
            return {"status": "error", "data": None, "message": f"Order number {order_no} not found"}

        # Create and execute modification
        modify_obj = _create_modify_object(target_order, modify_value, modify_type)
        result = _execute_modify_operation(account_obj, modify_obj, modify_type)

        if result and hasattr(result, "is_success") and result.is_success:
            value_desc = f"quantity to {modify_value}" if modify_type == "quantity" else f"price to {modify_value}"
            return {
                "status": "success",
                "data": result.data if hasattr(result, "data") else result,
                "message": f"Successfully modified order {order_no} {value_desc}",
            }
        else:
            return {"status": "error", "data": None, "message": f"Failed to modify order {order_no} {modify_type}"}

    except Exception as modify_error:
        return {"status": "error", "data": None, "message": f"Error modifying {modify_type}: {str(modify_error)}"}


# =============================================================================
# Order Conversion Helper Functions
# =============================================================================


def _convert_order_data_to_enums(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert order data to enum values"""
    try:
        from fubon_neo.constant import (  # type: ignore[import-not-found, unused-ignore]
            BSAction,
            MarketType,
            OrderType,
            PriceType,
            TimeInForce,
        )

        buy_sell_str = order_data.get("buy_sell", "Buy")
        buy_sell_enum = BSAction.Buy if buy_sell_str == "Buy" else BSAction.Sell

        market_type_str = order_data.get("market_type", "Common")
        market_type_enum = getattr(MarketType, market_type_str, MarketType.Common)

        price_type_str = order_data.get("price_type", "Limit")
        price_type_enum = getattr(PriceType, price_type_str, PriceType.Limit)

        time_in_force_str = order_data.get("time_in_force", "ROD")
        time_in_force_enum = getattr(TimeInForce, time_in_force_str, TimeInForce.ROD)

        order_type_str = order_data.get("order_type", "Stock")
        order_type_enum = getattr(OrderType, order_type_str, OrderType.Stock)

        return {
            "buy_sell": buy_sell_enum,
            "market_type": market_type_enum,
            "price_type": price_type_enum,
            "time_in_force": time_in_force_enum,
            "order_type": order_type_enum,
        }
    except ImportError:
        # Fallback for unit tests or environments without fubon_neo installed
        # Return simple string-based values while preserving expected keys
        return {
            "buy_sell": order_data.get("buy_sell", "Buy"),
            "market_type": order_data.get("market_type", "Common"),
            "price_type": order_data.get("price_type", "Limit"),
            "time_in_force": order_data.get("time_in_force", "ROD"),
            "order_type": order_data.get("order_type", "Stock"),
        }


def _create_order_object(order_data: Dict[str, Any], enums: Dict[str, Any]) -> Any:
    """Create order object

    Requires fubon_neo.sdk.Order to be available at runtime.
    """
    from fubon_neo.sdk import Order  # type: ignore[import-not-found, unused-ignore]

    return Order(
        buy_sell=enums["buy_sell"],
        symbol=order_data.get("symbol", ""),
        price=str(order_data.get("price", 0.0)),  # Convert price to string
        quantity=order_data.get("quantity", 0),
        market_type=enums["market_type"],
        price_type=enums["price_type"],
        time_in_force=enums["time_in_force"],
        order_type=enums["order_type"],
        user_def=order_data.get("user_def"),
    )


def _place_single_order(account_obj: Any, order_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process single order placement"""
    try:
        # First, convert inputs to enums and build the order; propagate conversion errors to caller
        enums = _convert_order_data_to_enums(order_data)
        try:
            order = _create_order_object(order_data, enums)
        except ImportError:
            return {
                "order_data": order_data,
                "result": None,
                "success": False,
                "error": "Dependency fubon_neo not installed or unavailable",
            }

        # Now check if SDK is initialized before placing the order
        if not config.sdk or not config.sdk.stock:
            return {
                "order_data": order_data,
                "result": None,
                "success": False,
                "error": "SDK not initialized or stock module not available",
            }

        # Determine whether to use non-blocking mode
        is_non_blocking = order_data.get("is_non_blocking", False)

        # Place order
        result = config.sdk.stock.place_order(account_obj, order, is_non_blocking)

        return {"order_data": order_data, "result": result, "success": True, "error": None}
    except Exception as e:
        return {"order_data": order_data, "result": None, "success": False, "error": str(e)}


def _execute_batch_orders(account_obj: Any, orders: list[Dict[str, Any]], max_workers: int) -> list[Dict[str, Any]]:
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_order = {executor.submit(_place_single_order, account_obj, order_data): order_data for order_data in orders}

        # Wait for all tasks to complete
        for future in concurrent.futures.as_completed(future_to_order):
            result = future.result()
            results.append(result)

    return results


def _summarize_batch_results(results: list[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize batch order results"""
    successful_orders = [r for r in results if r["success"]]
    failed_orders = [r for r in results if not r["success"]]

    return {
        "total_orders": len(results),
        "successful_orders": len(successful_orders),
        "failed_orders": len(failed_orders),
        "successful_orders_detail": successful_orders,
        "failed_orders_detail": failed_orders,
        "results": results,
    }


# =============================================================================
# MCP Trading Tools
# =============================================================================


@mcp.tool()
def place_order(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Place buy/sell stock order

    Args:
        account (str): Account number
        symbol (str): Stock symbol
        quantity (int): Quantity
        price (float): Price
        buy_sell (str): 'Buy' or 'Sell'
        market_type (str): Market type, default "Common"
        price_type (str): Price type, default "Limit"
        time_in_force (str): Time in force, default "ROD"
        order_type (str): Order type, default "Stock"
        user_def (str): User-defined field, optional
        is_non_blocking (bool): Whether to use non-blocking mode, default False
    """
    try:
        validated_args = PlaceOrderArgs(**args)
        account = validated_args.account
        symbol = validated_args.symbol
        quantity = validated_args.quantity
        price = validated_args.price
        buy_sell = validated_args.buy_sell
        market_type = validated_args.market_type
        price_type = validated_args.price_type
        time_in_force = validated_args.time_in_force
        order_type = validated_args.order_type
        user_def = validated_args.user_def
        is_non_blocking = validated_args.is_non_blocking

        # Check if accounts were successfully retrieved
        if not config.accounts or not hasattr(config.accounts, "is_success") or not config.accounts.is_success:
            return {
                "status": "error",
                "data": None,
                "message": "Account authentication failed, please check if credentials have expired",
            }

        # Find corresponding account object
        account_obj = None
        if hasattr(config.accounts, "data") and config.accounts.data:
            for acc in config.accounts.data:
                if getattr(acc, "account", None) == account:
                    account_obj = acc
                    break

        if not account_obj:
            return {"status": "error", "data": None, "message": f"Account {account} not found"}

        # Check if SDK is initialized
        if not config.sdk or not config.sdk.stock:
            return {"status": "error", "data": None, "message": "SDK not initialized or stock module not available"}

        try:
            from fubon_neo.constant import (  # type: ignore[import-not-found, unused-ignore]
                BSAction,
                MarketType,
                OrderType,
                PriceType,
                TimeInForce,
            )
            from fubon_neo.sdk import Order  # type: ignore[import-not-found, unused-ignore]
        except ImportError:
            return {
                "status": "error",
                "data": None,
                "message": "Dependency fubon_neo not installed or unavailable",
            }

        # Convert strings to corresponding enum values
        buy_sell_enum = BSAction.Buy if buy_sell == "Buy" else BSAction.Sell
        market_type_enum = getattr(MarketType, market_type, MarketType.Common)
        price_type_enum = getattr(PriceType, price_type, PriceType.Limit)
        time_in_force_enum = getattr(TimeInForce, time_in_force, TimeInForce.ROD)
        order_type_enum = getattr(OrderType, order_type, OrderType.Stock)

        order = Order(
            buy_sell=buy_sell_enum,
            symbol=symbol,
            price=str(price),  # Convert price to string
            quantity=quantity,
            market_type=market_type_enum,
            price_type=price_type_enum,
            time_in_force=time_in_force_enum,
            order_type=order_type_enum,
            user_def=user_def,
        )

        # Place order using blocking or non-blocking mode
        result = config.sdk.stock.place_order(account_obj, order, is_non_blocking)

        mode_desc = "non-blocking" if is_non_blocking else "blocking"
        return {
            "status": "success",
            "data": result,
            "message": f"Successfully placed {mode_desc} order: {buy_sell} {symbol} {quantity} shares",
        }
    except Exception as e:
        return {"status": "error", "data": None, "message": f"Order placement failed: {str(e)}"}


@mcp.tool()
def modify_quantity(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Modify order quantity

    Args:
        account (str): Account number
        order_no (str): Order number
        new_quantity (int): New quantity
    """
    try:
        validated_args = ModifyQuantityArgs(**args)
        account = validated_args.account
        order_no = validated_args.order_no
        new_quantity = validated_args.new_quantity

        return _modify_order(account, order_no, new_quantity, "quantity")

    except Exception as e:
        return {"status": "error", "data": None, "message": f"Quantity modification failed: {str(e)}"}


@mcp.tool()
def modify_price(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Modify order price

    Args:
        account (str): Account number
        order_no (str): Order number
        new_price (float): New price
    """
    try:
        validated_args = ModifyPriceArgs(**args)
        account = validated_args.account
        order_no = validated_args.order_no
        new_price = validated_args.new_price

        return _modify_order(account, order_no, new_price, "price")

    except Exception as e:
        return {"status": "error", "data": None, "message": f"Price modification failed: {str(e)}"}


@mcp.tool()
def cancel_order(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cancel order

    Args:
        account (str): Account number
        order_no (str): Order number
    """
    try:
        validated_args = CancelOrderArgs(**args)
        account = validated_args.account
        order_no = validated_args.order_no

        # Validate and get account object
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # Check if SDK is initialized
        if not config.sdk or not config.sdk.stock:
            return {"status": "error", "data": None, "message": "SDK not initialized or stock module not available"}

        # Get order results
        order_results = config.sdk.stock.get_order_results(account_obj)
        if not (order_results and hasattr(order_results, "is_success") and order_results.is_success):
            return {"status": "error", "data": None, "message": f"Unable to get order results for account {account}"}

        # Find target order
        target_order = _find_target_order(order_results, order_no)
        if not target_order:
            return {"status": "error", "data": None, "message": f"Order number {order_no} not found"}

        # Cancel order
        result = config.sdk.stock.cancel_order(account_obj, target_order)
        if result and hasattr(result, "is_success") and result.is_success:
            return {
                "status": "success",
                "data": result.data if hasattr(result, "data") else result,
                "message": f"Successfully cancelled order {order_no}",
            }
        else:
            return {"status": "error", "data": None, "message": f"Failed to cancel order {order_no}"}

    except Exception as e:
        return {"status": "error", "data": None, "message": f"Order cancellation failed: {str(e)}"}


@mcp.tool()
def batch_place_order(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Place multiple orders in parallel

    Args:
        account (str): Account number
        orders (List[Dict]): List of order parameter dictionaries
            Supported parameters:
            - symbol (str): Stock symbol
            - quantity (int): Quantity
            - price (float): Price
            - buy_sell (str): 'Buy' or 'Sell'
            - market_type (str): Market type, default "Common"
            - price_type (str): Price type, default "Limit"
            - time_in_force (str): Time in force, default "ROD"
            - order_type (str): Order type, default "Stock"
            - user_def (str): User-defined field, optional
            - is_non_blocking (bool): Whether to use non-blocking mode, default False
        max_workers (int): Maximum parallel workers, default 10
    """
    try:
        validated_args = BatchPlaceOrderArgs(**args)
        account = validated_args.account
        orders = validated_args.orders
        max_workers = validated_args.max_workers

        if not orders:
            return {"status": "error", "data": None, "message": "Order list cannot be empty"}

        # Validate and get account object
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # Execute batch orders
        results = _execute_batch_orders(account_obj, orders, max_workers)
        summary = _summarize_batch_results(results)

        return {
            "status": "success",
            "data": summary,
            "message": f"Batch order completed: {summary['total_orders']} total, {summary['successful_orders']} successful, {summary['failed_orders']} failed",
        }

    except Exception as e:
        return {"status": "error", "data": None, "message": f"Batch order failed: {str(e)}"}
