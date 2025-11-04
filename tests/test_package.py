"""
Basic tests for the Fubon API MCP Server package.

This module contains basic tests to ensure the package can be imported
and initialized correctly.
"""

import pytest

from fubon_mcp import __version__


class TestPackageBasics:
    """Test basic package functionality."""

    def test_package_version(self):
        """Test that package has a version."""
        assert __version__ is not None
        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_package_imports(self):
        """Test that main package components can be imported."""
        # Test main imports
        from fubon_mcp import mcp, main

        assert mcp is not None
        assert callable(main)

    def test_config_import(self):
        """Test that config module can be imported."""
        from fubon_mcp import config

        assert hasattr(config, 'mcp')
        assert hasattr(config, 'BASE_DATA_DIR')

    def test_models_import(self):
        """Test that models module can be imported."""
        from fubon_mcp import models

        # Test that key models exist
        assert hasattr(models, 'PlaceOrderArgs')
        assert hasattr(models, 'GetAccountInfoArgs')

    def test_utils_import(self):
        """Test that utils module can be imported."""
        from fubon_mcp import utils

        assert hasattr(utils, 'handle_exceptions')
        assert hasattr(utils, 'validate_and_get_account')

    def test_services_import(self):
        """Test that service modules can be imported."""
        services = [
            'fubon_mcp.account_service',
            'fubon_mcp.trading_service',
            'fubon_mcp.market_data_service',
            'fubon_mcp.reports_service'
        ]

        for service in services:
            try:
                __import__(service)
            except ImportError as e:
                pytest.fail(f"Failed to import {service}: {e}")


class TestPackageIntegration:
    """Test package-level integration."""

    def test_callable_functions_exist(self):
        """Test that all callable wrapper functions exist."""
        from fubon_mcp import (
            callable_get_account_info,
            callable_get_inventory,
            callable_get_bank_balance,
            callable_place_order,
            callable_cancel_order
        )

        # Test that they are callable
        assert callable(callable_get_account_info)
        assert callable(callable_get_inventory)
        assert callable(callable_get_bank_balance)
        assert callable(callable_place_order)
        assert callable(callable_cancel_order)

    def test_mcp_tools_registration(self):
        """Test that MCP tools are properly registered."""
        from fubon_mcp import mcp

        # MCP instance should exist
        assert mcp is not None

        # Should have tool registration capability
        assert hasattr(mcp, 'tool')