"""
Tests for reports_service.py - Reports and order status services.

This module tests report-related MCP tools including order reports,
filled reports, event reports, and order status.
"""

from unittest.mock import MagicMock

import pytest

from fubon_mcp import config
from fubon_mcp.reports_service import (
    get_all_reports,
    get_event_reports,
    get_filled_reports,
    get_order_changed_reports,
    get_order_reports,
    get_order_results,
)


class TestReportsServices:
    """Test reports service functions."""

    def test_get_order_results_success(self, mock_sdk, mock_accounts):
        """Test successful order results retrieval."""
        config.sdk = mock_sdk
        config.accounts = mock_accounts

        # Mock API response
        mock_result = MagicMock()
        mock_result.is_success = True
        mock_result.data = [
            {
                "order_no": "12345",
                "symbol": "2330",
                "quantity": 1000,
                "price": 500.0,
                "status": "Filled"
            }
        ]
        mock_sdk.stock.get_order_results.return_value = mock_result

        result = get_order_results.fn({"account": "12345678"})

        print(f"DEBUG: Result = {result}")
        print(f"DEBUG: config.accounts = {config.accounts}")
        print(f"DEBUG: config.accounts.data = {config.accounts.data if hasattr(config.accounts, 'data') else 'NO DATA'}")
        
        assert result["status"] == "success"
        assert len(result["data"]) == 1
        assert result["data"][0]["order_no"] == "12345"
        mock_sdk.stock.get_order_results.assert_called_once()

    def test_get_order_results_account_not_found(self, mock_accounts):
        """Test order results retrieval with invalid account."""
        config.accounts = mock_accounts

        result = get_order_results.fn({"account": "99999999"})

        assert result["status"] == "error"
        assert "account 99999999 not found" in result["message"]

    def test_get_order_reports_success(self, mock_sdk):
        """Test successful order reports retrieval."""
        from fubon_mcp import callbacks
        
        # Set up test data in callbacks module
        callbacks.latest_order_reports = [
            {
                "order_no": "12345",
                "timestamp": "2024-01-01 09:00:00",
                "action": "Buy"
            }
        ]

        result = get_order_reports.fn({"limit": 10})

        assert result["status"] == "success"
        assert len(result["data"]) == 1
        assert result["data"][0]["order_no"] == "12345"

    def test_get_order_changed_reports_success(self, mock_sdk):
        """Test successful order changed reports retrieval."""
        from fubon_mcp import callbacks
        
        callbacks.latest_order_changed_reports = [
            {
                "order_no": "12345",
                "change_type": "Price",
                "old_value": 500.0,
                "new_value": 505.0
            }
        ]

        result = get_order_changed_reports.fn({"limit": 5})

        assert result["status"] == "success"
        assert len(result["data"]) == 1
        assert result["data"][0]["change_type"] == "Price"

    def test_get_filled_reports_success(self, mock_sdk):
        """Test successful filled reports retrieval."""
        from fubon_mcp import callbacks
        
        callbacks.latest_filled_reports = [
            {
                "order_no": "12345",
                "fill_price": 500.0,
                "fill_quantity": 1000,
                "fill_time": "2024-01-01 09:00:00"
            }
        ]

        result = get_filled_reports.fn({"limit": 20})

        assert result["status"] == "success"
        assert len(result["data"]) == 1
        assert result["data"][0]["fill_price"] == 500.0

    def test_get_event_reports_success(self, mock_sdk):
        """Test successful event reports retrieval."""
        from fubon_mcp import callbacks
        
        callbacks.latest_event_reports = [
            {
                "event_type": "OrderFilled",
                "order_no": "12345",
                "timestamp": "2024-01-01 09:00:00"
            }
        ]

        result = get_event_reports.fn({"limit": 15})

        assert result["status"] == "success"
        assert len(result["data"]) == 1
        assert result["data"][0]["event_type"] == "OrderFilled"

    def test_get_all_reports_success(self, mock_sdk):
        """Test successful all reports retrieval."""
        from fubon_mcp import callbacks
        
        # Set up test data for all report types
        callbacks.latest_order_reports = [{"type": "order", "order_no": "12345"}]
        callbacks.latest_order_changed_reports = [{"type": "changed", "order_no": "12346"}]
        callbacks.latest_filled_reports = [{"type": "filled", "order_no": "12347"}]
        callbacks.latest_event_reports = [{"type": "event", "order_no": "12348"}]

        result = get_all_reports.fn({})

        assert result["status"] == "success"
        assert "order_reports" in result["data"]
        assert "filled_reports" in result["data"]
        assert "event_reports" in result["data"]
        assert len(result["data"]["order_reports"]) == 1
        assert len(result["data"]["filled_reports"]) == 1
        assert len(result["data"]["event_reports"]) == 1

    def test_reports_api_failure(self, mock_sdk):
        """Test reports retrieval with empty callbacks."""
        from fubon_mcp import callbacks
        
        # Ensure callbacks are empty
        callbacks.latest_order_reports = []

        result = get_order_reports.fn({"limit": 10})

        assert result["status"] == "success"
        assert len(result["data"]) == 0

    def test_reports_sdk_not_initialized(self):
        """Test reports when callbacks are empty (normal case without SDK initialization)."""
        from fubon_mcp import callbacks
        
        # Reports functions don't need SDK, they read from callbacks
        callbacks.latest_order_reports = []

        result = get_order_reports.fn({"limit": 10})

        assert result["status"] == "success"
        assert len(result["data"]) == 0


class TestReportsServiceIntegration:
    """Test reports service integration."""

    def test_all_reports_functions_importable(self):
        """Test that all reports service functions can be imported."""
        from fubon_mcp.reports_service import (
            get_all_reports,
            get_event_reports,
            get_filled_reports,
            get_order_changed_reports,
            get_order_reports,
            get_order_results,
        )

        # Test that functions are MCP FunctionTools with .fn attribute
        assert hasattr(get_order_results, 'fn')
        assert hasattr(get_order_reports, 'fn')
        assert hasattr(get_order_changed_reports, 'fn')
        assert hasattr(get_filled_reports, 'fn')
        assert hasattr(get_event_reports, 'fn')
        assert hasattr(get_all_reports, 'fn')
        
        # Test that .fn is callable
        assert callable(get_order_results.fn)
        assert callable(get_order_reports.fn)
        assert callable(get_order_changed_reports.fn)
        assert callable(get_filled_reports.fn)
        assert callable(get_event_reports.fn)
        assert callable(get_all_reports.fn)

    def test_reports_service_module_structure(self):
        """Test reports_service module has expected structure."""
        import fubon_mcp.reports_service as reports_module

        # Check for expected functions
        expected_functions = [
            'get_order_results',
            'get_order_reports',
            'get_order_changed_reports',
            'get_filled_reports',
            'get_event_reports',
            'get_all_reports'
        ]

        for func_name in expected_functions:
            assert hasattr(reports_module, func_name), f"Reports service module missing function: {func_name}"
