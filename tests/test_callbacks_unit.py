"""
Unit tests for callbacks.py module.
"""

from unittest.mock import MagicMock, patch

from fubon_mcp.callbacks import (
    latest_event_reports,
    latest_filled_reports,
    latest_order_changed_reports,
    latest_order_reports,
    on_event,
    on_filled,
    on_order,
    on_order_changed,
)


class TestOnOrder:
    """Test on_order callback function."""

    @patch("fubon_mcp.callbacks.datetime")
    @patch("sys.stderr", new_callable=MagicMock)
    def test_on_order_success(self, mock_stderr, mock_datetime):
        """Test successful order callback processing."""
        mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T10:00:00"

        # Clear global list
        global latest_order_reports  # noqa: F824 - Global variable used in tests
        latest_order_reports.clear()

        order_data = {"order_no": "123", "status": "pending"}
        on_order(order_data)

        assert len(latest_order_reports) == 1
        assert latest_order_reports[0]["timestamp"] == "2023-01-01T10:00:00"
        assert latest_order_reports[0]["data"] == order_data

    @patch("sys.stderr", new_callable=MagicMock)
    def test_on_order_exception_handling(self, mock_stderr):
        """Test order callback exception handling."""
        # Clear global list
        global latest_order_reports  # noqa: F824 - Global variable used in tests
        latest_order_reports.clear()

        # Pass invalid data that might cause exception
        on_order(None)

        # Should still work and add to list
        assert len(latest_order_reports) == 1

    @patch("sys.stderr", new_callable=MagicMock)
    def test_on_order_list_limit(self, mock_stderr):
        """Test that order reports list is limited to 10 items."""
        global latest_order_reports  # noqa: F824 - Global variable used in tests
        latest_order_reports.clear()

        # Add 12 items
        for i in range(12):
            on_order({"order_no": f"order_{i}"})

        assert len(latest_order_reports) == 10
        # First item should be removed (oldest)
        assert latest_order_reports[0]["data"]["order_no"] == "order_2"


class TestOnOrderChanged:
    """Test on_order_changed callback function."""

    @patch("fubon_mcp.callbacks.datetime")
    @patch("sys.stderr", new_callable=MagicMock)
    def test_on_order_changed_success(self, mock_stderr, mock_datetime):
        """Test successful order changed callback processing."""
        mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T10:00:00"

        global latest_order_changed_reports  # noqa: F824 - Global variable used in tests
        latest_order_changed_reports.clear()

        order_changed_data = {"order_no": "123", "change_type": "price_update"}
        on_order_changed(order_changed_data)

        assert len(latest_order_changed_reports) == 1
        assert latest_order_changed_reports[0]["timestamp"] == "2023-01-01T10:00:00"
        assert latest_order_changed_reports[0]["data"] == order_changed_data

    @patch("sys.stderr", new_callable=MagicMock)
    def test_on_order_changed_list_limit(self, mock_stderr):
        """Test that order changed reports list is limited to 10 items."""
        global latest_order_changed_reports  # noqa: F824 - Global variable used in tests
        latest_order_changed_reports.clear()

        for i in range(12):
            on_order_changed({"order_no": f"changed_{i}"})

        assert len(latest_order_changed_reports) == 10


class TestOnFilled:
    """Test on_filled callback function."""

    @patch("fubon_mcp.callbacks.datetime")
    @patch("sys.stderr", new_callable=MagicMock)
    def test_on_filled_success(self, mock_stderr, mock_datetime):
        """Test successful filled callback processing."""
        mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T10:00:00"

        global latest_filled_reports  # noqa: F824 - Global variable used in tests
        latest_filled_reports.clear()

        filled_data = {"order_no": "123", "filled_qty": 100, "filled_price": 50.0}
        on_filled(filled_data)

        assert len(latest_filled_reports) == 1
        assert latest_filled_reports[0]["timestamp"] == "2023-01-01T10:00:00"
        assert latest_filled_reports[0]["data"] == filled_data

    @patch("sys.stderr", new_callable=MagicMock)
    def test_on_filled_list_limit(self, mock_stderr):
        """Test that filled reports list is limited to 10 items."""
        global latest_filled_reports  # noqa: F824 - Global variable used in tests
        latest_filled_reports.clear()

        for i in range(12):
            on_filled({"order_no": f"filled_{i}"})

        assert len(latest_filled_reports) == 10


class TestOnEvent:
    """Test on_event callback function."""

    @patch("fubon_mcp.callbacks.datetime")
    @patch("sys.stderr", new_callable=MagicMock)
    def test_on_event_success(self, mock_stderr, mock_datetime):
        """Test successful event callback processing."""
        mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T10:00:00"

        global latest_event_reports  # noqa: F824 - Global variable used in tests
        latest_event_reports.clear()

        event_data = {"event_type": "connection", "status": "connected"}
        on_event(event_data)

        assert len(latest_event_reports) == 1
        assert latest_event_reports[0]["timestamp"] == "2023-01-01T10:00:00"
        assert latest_event_reports[0]["data"] == event_data

    @patch("sys.stderr", new_callable=MagicMock)
    def test_on_event_list_limit(self, mock_stderr):
        """Test that event reports list is limited to 10 items."""
        global latest_event_reports  # noqa: F824 - Global variable used in tests
        latest_event_reports.clear()

        for i in range(12):
            on_event({"event_type": f"event_{i}"})

        assert len(latest_event_reports) == 10


class TestGlobalLists:
    """Test global report lists initialization."""

    def test_global_lists_initialization(self):
        """Test that global lists are properly initialized."""
        assert isinstance(latest_order_reports, list)
        assert isinstance(latest_order_changed_reports, list)
        assert isinstance(latest_filled_reports, list)
        assert isinstance(latest_event_reports, list)

    def test_global_lists_thread_safety(self):
        """Test that global lists operations are thread-safe."""
        import threading

        global latest_order_reports  # noqa: F824 - Global variable used in tests
        latest_order_reports.clear()

        results = []

        def add_orders():
            for i in range(5):
                on_order({"order_no": f"thread_{threading.current_thread().name}_{i}"})
                results.append(len(latest_order_reports))

        threads = []
        for i in range(3):
            t = threading.Thread(target=add_orders)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # List is limited to 10 items, so we should have exactly 10 items
        # (3 threads * 5 orders = 15, but limited to 10)
        assert len(latest_order_reports) == 10
        # Verify that we have items from different threads
        thread_names = set()
        for report in latest_order_reports:
            order_no = report["data"]["order_no"]
            # Extract thread name from order_no like "thread_Thread-1 (add_orders)_4"
            thread_part = order_no.split("_")[1]  # Gets "Thread-1"
            thread_names.add(thread_part)

        # Should have items from multiple threads
        assert len(thread_names) >= 2
