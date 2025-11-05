"""
Callback functions for Fubon API MCP Server.

This module contains WebSocket callback functions and global report storage
for handling real-time updates from the Fubon API.
"""

import sys
import threading
from datetime import datetime
from typing import Any, Dict, List

# =============================================================================
# Global Report Data Storage (Thread-safe)
# =============================================================================

# Latest order reports (keep max 10)
latest_order_reports: List[Dict[str, Any]] = []  # Stored by SDK callback functions

# Latest order change reports (keep max 10)
latest_order_changed_reports: List[Dict[str, Any]] = []  # Stored by SDK callback functions

# Latest filled reports (keep max 10)
latest_filled_reports: List[Dict[str, Any]] = []  # Stored by SDK callback functions

# Latest event reports (keep max 10)
latest_event_reports: List[Dict[str, Any]] = []  # Stored by SDK callback functions

# Global lock to avoid duplicate reconnections
relogin_lock = threading.Lock()


# =============================================================================
# WebSocket Callback Functions
# =============================================================================


def on_order(order_data: Any) -> None:
    """
    Order report event callback function.

    Called by SDK when new orders are created or status changes.
    Received order data is added to global latest_order_reports list,
    limited to max 10 records.

    Args:
        order_data: Order-related data object with order details
    """
    global latest_order_reports  # noqa: F824 - Global variable used for callback storage
    try:
        # Add timestamp to data
        timestamped_data = {"timestamp": datetime.now().isoformat(), "data": order_data}
        latest_order_reports.append(timestamped_data)

        # Limit list length, keep max 10 records
        if len(latest_order_reports) > 10:
            latest_order_reports.pop(0)

        print(f"Received order report: {order_data}", file=sys.stderr)
    except Exception as e:
        print(f"Error processing order report: {str(e)}", file=sys.stderr)


def on_order_changed(order_changed_data: Any) -> None:
    """
    Order change report event callback function.

    Called by SDK when orders are modified.
    Received order change data is added to global latest_order_changed_reports list,
    limited to max 10 records.

    Args:
        order_changed_data: Order change-related data object
    """
    global latest_order_changed_reports  # noqa: F824 - Global variable used for callback storage
    try:
        # Add timestamp to data
        timestamped_data = {"timestamp": datetime.now().isoformat(), "data": order_changed_data}
        latest_order_changed_reports.append(timestamped_data)

        # Limit list length, keep max 10 records
        if len(latest_order_changed_reports) > 10:
            latest_order_changed_reports.pop(0)

        print(f"Received order change report: {order_changed_data}", file=sys.stderr)
    except Exception as e:
        print(f"Error processing order change report: {str(e)}", file=sys.stderr)


def on_filled(filled_data: Any) -> None:
    """
    Filled report event callback function.

    Called by SDK when orders are filled.
    Received filled data is added to global latest_filled_reports list,
    limited to max 10 records.

    Args:
        filled_data: Filled order data object
    """
    global latest_filled_reports  # noqa: F824 - Global variable used for callback storage
    try:
        # Add timestamp to data
        timestamped_data = {"timestamp": datetime.now().isoformat(), "data": filled_data}
        latest_filled_reports.append(timestamped_data)

        # Limit list length, keep max 10 records
        if len(latest_filled_reports) > 10:
            latest_filled_reports.pop(0)

        print(f"Received fill report: {filled_data}", file=sys.stderr)
    except Exception as e:
        print(f"Error processing fill report: {str(e)}", file=sys.stderr)


def on_event(event_data: Any) -> None:
    """
    Event notification callback function.

    Called by SDK for various events (connection status changes, errors, etc.).
    Received event data is added to global latest_event_reports list,
    limited to max 10 records.

    Args:
        event_data: Event-related data object with event type and details
    """
    global latest_event_reports  # noqa: F824 - Global variable used for callback storage
    try:
        # Add timestamp to data
        timestamped_data = {"timestamp": datetime.now().isoformat(), "data": event_data}
        latest_event_reports.append(timestamped_data)

        # Limit list length, keep max 10 records
        if len(latest_event_reports) > 10:
            latest_event_reports.pop(0)

        print(f"Received event notification: {event_data}", file=sys.stderr)
    except Exception as e:
        print(f"Error processing event notification: {str(e)}", file=sys.stderr)
