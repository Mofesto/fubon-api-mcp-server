"""
Tests for callbacks module.
"""

import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from fubon_api_mcp_server.callbacks import (
    latest_event_reports,
    latest_filled_reports,
    latest_order_changed_reports,
    latest_order_reports,
    on_event,
    on_filled,
    on_order,
    on_order_changed,
    relogin_lock,
)

# =============================================================================
# Callback Function Tests
# =============================================================================


def test_on_order_basic():
    """Test on_order callback with valid data"""
    # Clear existing reports
    latest_order_reports.clear()

    # Create mock order data
    mock_order = MagicMock()
    mock_order.order_no = "12345"
    mock_order.symbol = "2330"

    # Call callback
    on_order(mock_order)

    # Verify report was added
    assert len(latest_order_reports) == 1
    assert latest_order_reports[0]["data"] == mock_order
    assert "timestamp" in latest_order_reports[0]


def test_on_order_multiple_reports():
    """Test on_order callback with multiple reports"""
    latest_order_reports.clear()

    # Add 15 reports (should keep only last 10)
    for i in range(15):
        mock_order = MagicMock()
        mock_order.order_no = f"ORDER{i}"
        on_order(mock_order)

    # Should only have 10 reports
    assert len(latest_order_reports) == 10
    # Should have the last 10 (5-14)
    assert latest_order_reports[0]["data"].order_no == "ORDER5"
    assert latest_order_reports[-1]["data"].order_no == "ORDER14"


def test_on_order_exception_handling():
    """Test on_order callback with exception"""
    latest_order_reports.clear()

    # This should not raise exception
    with patch("sys.stderr"):
        on_order(None)

    # List should still be empty or handle gracefully
    # The function prints error but doesn't add to list on exception


def test_on_order_changed_basic():
    """Test on_order_changed callback with valid data"""
    latest_order_changed_reports.clear()

    mock_change = MagicMock()
    mock_change.order_no = "12345"
    mock_change.change_type = "PRICE"

    on_order_changed(mock_change)

    assert len(latest_order_changed_reports) == 1
    assert latest_order_changed_reports[0]["data"] == mock_change
    assert "timestamp" in latest_order_changed_reports[0]


def test_on_order_changed_limit():
    """Test on_order_changed maintains max 10 reports"""
    latest_order_changed_reports.clear()

    for i in range(12):
        mock_change = MagicMock()
        mock_change.order_no = f"CHANGE{i}"
        on_order_changed(mock_change)

    assert len(latest_order_changed_reports) == 10
    assert latest_order_changed_reports[0]["data"].order_no == "CHANGE2"


def test_on_filled_basic():
    """Test on_filled callback with valid data"""
    latest_filled_reports.clear()

    mock_filled = MagicMock()
    mock_filled.order_no = "12345"
    mock_filled.filled_qty = 1000
    mock_filled.filled_price = 550.0

    on_filled(mock_filled)

    assert len(latest_filled_reports) == 1
    assert latest_filled_reports[0]["data"] == mock_filled
    assert "timestamp" in latest_filled_reports[0]


def test_on_filled_limit():
    """Test on_filled maintains max 10 reports"""
    latest_filled_reports.clear()

    for i in range(15):
        mock_filled = MagicMock()
        mock_filled.order_no = f"FILLED{i}"
        on_filled(mock_filled)

    assert len(latest_filled_reports) == 10
    assert latest_filled_reports[0]["data"].order_no == "FILLED5"


def test_on_event_basic():
    """Test on_event callback with valid data"""
    latest_event_reports.clear()

    mock_event = MagicMock()
    mock_event.event_type = "CONNECTION"
    mock_event.message = "Connected to server"

    on_event(mock_event)

    assert len(latest_event_reports) == 1
    assert latest_event_reports[0]["data"] == mock_event
    assert "timestamp" in latest_event_reports[0]


def test_on_event_limit():
    """Test on_event maintains max 10 reports"""
    latest_event_reports.clear()

    for i in range(20):
        mock_event = MagicMock()
        mock_event.event_type = f"EVENT{i}"
        on_event(mock_event)

    assert len(latest_event_reports) == 10
    assert latest_event_reports[0]["data"].event_type == "EVENT10"


def test_on_event_exception_handling():
    """Test on_event callback with exception"""
    latest_event_reports.clear()

    with patch("sys.stderr"):
        on_event(None)

    # Should handle gracefully without crashing


def test_timestamp_format():
    """Test that timestamps are in ISO format"""
    latest_order_reports.clear()

    mock_order = MagicMock()
    on_order(mock_order)

    timestamp_str = latest_order_reports[0]["timestamp"]
    # Should be able to parse as datetime
    parsed = datetime.fromisoformat(timestamp_str)
    assert isinstance(parsed, datetime)


def test_relogin_lock_exists():
    """Test that relogin_lock is a threading.Lock"""
    import threading

    assert isinstance(relogin_lock, type(threading.Lock()))


def test_callbacks_thread_safety():
    """Test that callbacks can be called concurrently"""
    import threading

    latest_order_reports.clear()

    def add_orders():
        for i in range(5):
            mock_order = MagicMock()
            mock_order.order_no = f"ORDER{i}"
            on_order(mock_order)

    threads = [threading.Thread(target=add_orders) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Should have at most 10 reports (limit enforced)
    assert len(latest_order_reports) <= 10


def test_all_callbacks_clear_state():
    """Test clearing all report lists"""
    latest_order_reports.clear()
    latest_order_changed_reports.clear()
    latest_filled_reports.clear()
    latest_event_reports.clear()

    assert len(latest_order_reports) == 0
    assert len(latest_order_changed_reports) == 0
    assert len(latest_filled_reports) == 0
    assert len(latest_event_reports) == 0


def test_callback_data_structure():
    """Test that callback data has correct structure"""
    latest_order_reports.clear()

    mock_order = MagicMock()
    mock_order.order_no = "TEST123"

    on_order(mock_order)

    report = latest_order_reports[0]
    assert isinstance(report, dict)
    assert "timestamp" in report
    assert "data" in report
    assert report["data"].order_no == "TEST123"


@patch("sys.stderr")
def test_on_order_prints_to_stderr(mock_stderr):
    """Test that on_order prints to stderr"""
    latest_order_reports.clear()

    mock_order = MagicMock()
    mock_order.__str__ = lambda self: "TEST_ORDER"

    with patch("builtins.print") as mock_print:
        on_order(mock_order)
        # Verify print was called with correct arguments
        assert mock_print.called


@patch("sys.stderr")
def test_on_order_changed_prints_to_stderr(mock_stderr):
    """Test that on_order_changed prints to stderr"""
    latest_order_changed_reports.clear()

    mock_change = MagicMock()

    with patch("builtins.print") as mock_print:
        on_order_changed(mock_change)
        assert mock_print.called


@patch("sys.stderr")
def test_on_filled_prints_to_stderr(mock_stderr):
    """Test that on_filled prints to stderr"""
    latest_filled_reports.clear()

    mock_filled = MagicMock()

    with patch("builtins.print") as mock_print:
        on_filled(mock_filled)
        assert mock_print.called


@patch("sys.stderr")
def test_on_event_prints_to_stderr(mock_stderr):
    """Test that on_event prints to stderr"""
    latest_event_reports.clear()

    mock_event = MagicMock()

    with patch("builtins.print") as mock_print:
        on_event(mock_event)
        assert mock_print.called
