"""
Reports service module for Fubon API MCP Server.

This module contains MCP tools for retrieving various reports including
order reports, filled reports, and event notifications.
"""

from typing import Dict

from . import callbacks
from . import config
from .config import mcp
from .models import (
    GetEventReportsArgs,
    GetFilledReportsArgs,
    GetOrderChangedReportsArgs,
    GetOrderReportsArgs,
    GetOrderResultsArgs,
)
from .utils import validate_and_get_account

# =============================================================================
# MCP Report Tools
# =============================================================================


@mcp.tool()
def get_order_results(args: Dict) -> Dict:
    """
    Get order results for order and fill status confirmation

    Args:
        account (str): Account number
    """
    try:
        validated_args = GetOrderResultsArgs(**args)
        account = validated_args.account

        # Validate and get account object
        account_obj, error = validate_and_get_account(account)
        if error:
            return {"status": "error", "data": None, "message": error}

        # Check if SDK is initialized
        if not config.sdk or not config.sdk.stock:
            return {"status": "error", "data": None, "message": "SDK not initialized or stock module not available"}

        # Get order results
        order_results = config.sdk.stock.get_order_results(account_obj)
        if order_results and hasattr(order_results, "is_success") and order_results.is_success:
            return {
                "status": "success",
                "data": order_results.data if hasattr(order_results, "data") else order_results,
                "message": f"Successfully retrieved order results for account {account}",
            }
        else:
            return {"status": "error", "data": None, "message": f"Unable to get order results for account {account}"}

    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get order results: {str(e)}"}


@mcp.tool()
def get_order_reports(args: Dict) -> Dict:
    """
    Get latest order reports

    Args:
        limit (int): Number of latest records to return, default 10
    """
    try:
        validated_args = GetOrderReportsArgs(**args)
        limit = validated_args.limit

        reports = callbacks.latest_order_reports[-limit:] if callbacks.latest_order_reports else []

        return {
            "status": "success",
            "data": reports,
            "count": len(reports),
            "message": f"Successfully retrieved latest {len(reports)} order reports",
        }
    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get order reports: {str(e)}"}


@mcp.tool()
def get_order_changed_reports(args: Dict) -> Dict:
    """
    Get latest order change reports

    Args:
        limit (int): Number of latest records to return, default 10
    """
    try:
        validated_args = GetOrderChangedReportsArgs(**args)
        limit = validated_args.limit

        reports = callbacks.latest_order_changed_reports[-limit:] if callbacks.latest_order_changed_reports else []

        return {
            "status": "success",
            "data": reports,
            "count": len(reports),
            "message": f"Successfully retrieved latest {len(reports)} order change reports",
        }
    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get order change reports: {str(e)}"}


@mcp.tool()
def get_filled_reports(args: Dict) -> Dict:
    """
    Get latest fill reports

    Args:
        limit (int): Number of latest records to return, default 10
    """
    try:
        validated_args = GetFilledReportsArgs(**args)
        limit = validated_args.limit

        reports = callbacks.latest_filled_reports[-limit:] if callbacks.latest_filled_reports else []

        return {
            "status": "success",
            "data": reports,
            "count": len(reports),
            "message": f"Successfully retrieved latest {len(reports)} fill reports",
        }
    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get fill reports: {str(e)}"}


@mcp.tool()
def get_event_reports(args: Dict) -> Dict:
    """
    Get latest event notifications

    Args:
        limit (int): Number of latest records to return, default 10
    """
    try:
        validated_args = GetEventReportsArgs(**args)
        limit = validated_args.limit

        reports = callbacks.latest_event_reports[-limit:] if callbacks.latest_event_reports else []

        return {
            "status": "success",
            "data": reports,
            "count": len(reports),
            "message": f"Successfully retrieved latest {len(reports)} event notifications",
        }
    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get event reports: {str(e)}"}


@mcp.tool()
def get_all_reports(args: Dict) -> Dict:
    """
    Get all types of active reports

    Args:
        limit (int): Number of latest records per type to return, default 5
    """
    try:
        validated_args = GetOrderReportsArgs(**args)  # Reuse same parameter class
        limit = validated_args.limit

        all_reports = {
            "order_reports": callbacks.latest_order_reports[-limit:] if callbacks.latest_order_reports else [],
            "order_changed_reports": callbacks.latest_order_changed_reports[-limit:] if callbacks.latest_order_changed_reports else [],
            "filled_reports": callbacks.latest_filled_reports[-limit:] if callbacks.latest_filled_reports else [],
            "event_reports": callbacks.latest_event_reports[-limit:] if callbacks.latest_event_reports else [],
        }

        total_count = sum(len(reports) for reports in all_reports.values())

        return {
            "status": "success",
            "data": all_reports,
            "total_count": total_count,
            "message": f"Successfully retrieved all types of active reports, total {total_count} records",
        }
    except Exception as e:
        return {"status": "error", "data": None, "message": f"Failed to get all reports: {str(e)}"}
