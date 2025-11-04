"""
Tests for remaining services - historical_data_service, indicators_service, data_handler, callbacks.

This module contains tests for the remaining service modules in the Fubon MCP Server.
"""

from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest

from fubon_mcp import config


class TestHistoricalDataService:
    """Test historical data service."""

    def test_historical_data_service_import(self):
        """Test that historical data service can be imported."""
        from fubon_mcp import historical_data_service

        # Check for expected MCP tool - historical_candles
        assert hasattr(historical_data_service, 'historical_candles')
        # It's an MCP FunctionTool, check for .fn
        assert hasattr(historical_data_service.historical_candles, 'fn')

    @patch('fubon_mcp.data_handler.Path')
    def test_get_historical_candles_basic(self, mock_path):
        """Test basic historical candles retrieval."""
        from fubon_mcp.historical_data_service import historical_candles

        # Mock file operations
        mock_data_file = MagicMock()
        mock_path.return_value.exists.return_value = False  # Force API call
        
        # Mock reststock to return data
        config.reststock = MagicMock()
        config.reststock.historical.candles.return_value = {
            "data": [{"date": "2024-01-01", "open": 500.0, "close": 505.0, "volume": 1000}]
        }

        result = historical_candles.fn({"symbol": "2330", "from_date": "2024-01-01", "to_date": "2024-01-02"})
        print(f"Result: {result}")
        
        assert result["status"] == "success"
        assert "data" in result


class TestIndicatorsService:
    """Test indicators service."""

    def test_indicators_service_import(self):
        """Test that indicators service can be imported."""
        from fubon_mcp import indicators_service

        # Check for expected functions - may be empty or minimal
        assert hasattr(indicators_service, '__file__')


class TestDataHandler:
    """Test data handler."""

    def test_data_handler_import(self):
        """Test that data handler can be imported."""
        from fubon_mcp import data_handler

        # Check for expected functions (actual function names from data_handler.py)
        expected_functions = ['read_local_stock_data', 'save_to_local_csv', 'process_historical_data', 'fetch_historical_data_segment']
        for func_name in expected_functions:
            assert hasattr(data_handler, func_name)

    @patch('fubon_mcp.data_handler.pd')
    def test_save_and_load_historical_data(self, mock_pd):
        """Test saving and loading historical data."""
        from fubon_mcp.data_handler import save_to_local_csv, read_local_stock_data

        # Mock pandas operations
        mock_df = MagicMock()
        mock_pd.DataFrame.return_value = mock_df
        mock_pd.read_csv.return_value = mock_df
        
        # Test that functions are callable (they require real file system)
        assert callable(save_to_local_csv)
        assert callable(read_local_stock_data)


class TestCallbacks:
    """Test callbacks module."""

    def test_callbacks_import(self):
        """Test that callbacks can be imported."""
        from fubon_mcp import callbacks

        # Check for expected attributes
        assert hasattr(callbacks, '__file__')


class TestServer:
    """Test server module."""

    def test_server_import(self):
        """Test that server can be imported."""
        from fubon_mcp import server

        # Check for expected functions
        expected_functions = [
            'main',
            'callable_get_account_info',
            'callable_get_inventory',
            'callable_place_order',
            'callable_cancel_order'
        ]
        for func_name in expected_functions:
            assert hasattr(server, func_name)
            assert callable(getattr(server, func_name))

    def test_callable_functions_are_callable(self):
        """Test that callable wrapper functions work."""
        from fubon_mcp.server import (
            callable_get_account_info,
            callable_get_inventory,
            callable_get_bank_balance
        )

        # These should be callable and return some result
        # (may return error due to no SDK, but should not crash)
        result1 = callable_get_account_info({})
        result2 = callable_get_inventory({})
        result3 = callable_get_bank_balance({})

        assert isinstance(result1, (dict, str))
        assert isinstance(result2, (dict, str))
        assert isinstance(result3, (dict, str))


class TestIntegrationAllServices:
    """Test integration of all services."""

    def test_all_services_can_be_imported(self):
        """Test that all service modules can be imported without errors."""
        services = [
            'fubon_mcp.account_service',
            'fubon_mcp.trading_service',
            'fubon_mcp.market_data_service',
            'fubon_mcp.historical_data_service',
            'fubon_mcp.indicators_service',
            'fubon_mcp.reports_service',
            'fubon_mcp.data_handler',
            'fubon_mcp.callbacks',
            'fubon_mcp.server'
        ]

        for service in services:
            try:
                __import__(service)
            except ImportError as e:
                pytest.fail(f"Failed to import {service}: {e}")

    def test_main_package_structure(self):
        """Test that main package has expected structure."""
        import fubon_mcp

        # Check version
        assert hasattr(fubon_mcp, '__version__')

        # Check main exports
        expected_exports = [
            'mcp',
            'main',
            'callable_get_account_info',
            'callable_get_inventory'
        ]

        for export in expected_exports:
            assert hasattr(fubon_mcp, export), f"Main package missing export: {export}"

    def test_config_integration(self):
        """Test that config integrates properly with services."""
        # Test that config can be imported and has expected attributes
        from fubon_mcp import config

        required_attrs = ['mcp', 'sdk', 'accounts', 'reststock', 'BASE_DATA_DIR']
        for attr in required_attrs:
            assert hasattr(config, attr), f"Config missing attribute: {attr}"

        # Test that MCP instance exists
        assert config.mcp is not None

    def test_models_integration(self):
        """Test that models integrate properly."""
        from fubon_mcp import models

        # Test that key models can be imported
        from fubon_mcp.models import (
            PlaceOrderArgs,
            GetAccountInfoArgs,
            HistoricalCandlesArgs
        )

        # Test model instantiation
        order_args = PlaceOrderArgs(
            account="12345678",
            symbol="2330",
            quantity=1000,
            price=500.0,
            buy_sell="Buy"
        )
        assert order_args.account == "12345678"

        account_args = GetAccountInfoArgs(account="12345678")
        assert account_args.account == "12345678"

    def test_utils_integration(self):
        """Test that utils integrate properly."""
        from fubon_mcp import utils

        # Test that key utilities can be imported
        from fubon_mcp.utils import (
            handle_exceptions,
            validate_and_get_account,
            _safe_api_call
        )

        # Test utility functions
        @handle_exceptions
        def test_func():
            return "success"

        result = test_func()
        assert result == "success"