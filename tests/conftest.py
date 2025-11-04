"""
Pytest configuration and shared fixtures for Fubon API MCP Server tests.

This module contains pytest configuration, shared fixtures, and test utilities
used across all test modules.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from fubon_mcp import config


@pytest.fixture(scope="session")
def temp_data_dir():
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture(scope="session")
def mock_sdk():
    """Create a mock SDK instance for testing."""
    sdk = MagicMock()
    sdk.stock = MagicMock()
    sdk.login = MagicMock()
    sdk.get_accounts = MagicMock()
    sdk.reststock = MagicMock()
    return sdk


@pytest.fixture(scope="session")
def mock_accounts():
    """Create mock account data for testing."""
    accounts = MagicMock()
    accounts.is_success = True
    accounts.data = [
        MagicMock(
            name="Test Account 1",
            branch_no="123",
            account="12345678",
            account_type="Stock"
        ),
        MagicMock(
            name="Test Account 2",
            branch_no="456",
            account="87654321",
            account_type="Stock"
        )
    ]
    return accounts


@pytest.fixture(scope="session")
def mock_reststock():
    """Create mock REST stock client for testing."""
    reststock = MagicMock()
    
    # Mock the nested structure used by the actual API
    reststock.intraday = MagicMock()
    reststock.intraday.tickers = MagicMock()
    reststock.intraday.ticker = MagicMock()
    reststock.intraday.quote = MagicMock()
    reststock.intraday.candles = MagicMock()
    reststock.intraday.trades = MagicMock()
    reststock.intraday.volumes = MagicMock()
    
    reststock.snapshot = MagicMock()
    reststock.snapshot.quotes = MagicMock()
    reststock.snapshot.movers = MagicMock()
    reststock.snapshot.actives = MagicMock()
    
    reststock.historical = MagicMock()
    reststock.historical.stats = MagicMock()
    
    return reststock


@pytest.fixture(autouse=True)
def reset_config(temp_data_dir, mock_sdk, mock_accounts, mock_reststock):
    """Reset global configuration before each test."""
    # Reset config module
    config.sdk = mock_sdk
    config.accounts = mock_accounts
    config.reststock = mock_reststock
    config.BASE_DATA_DIR = temp_data_dir

    # Set environment variables for testing
    os.environ["FUBON_USERNAME"] = "test_user"
    os.environ["FUBON_PASSWORD"] = "test_pass"
    os.environ["FUBON_PFX_PATH"] = str(temp_data_dir / "test.pfx")
    os.environ["FUBON_DATA_DIR"] = str(temp_data_dir)

    yield

    # Clean up environment variables
    for key in ["FUBON_USERNAME", "FUBON_PASSWORD", "FUBON_PFX_PATH", "FUBON_DATA_DIR"]:
        if key in os.environ:
            del os.environ[key]


@pytest.fixture
def sample_order_data():
    """Sample order data for testing."""
    return {
        "account": "12345678",
        "symbol": "2330",
        "quantity": 1000,
        "price": 500.0,
        "buy_sell": "Buy",
        "market_type": "Common",
        "price_type": "Limit",
        "time_in_force": "ROD",
        "order_type": "Stock"
    }


@pytest.fixture
def sample_account_data():
    """Sample account data for testing."""
    return {
        "account": "12345678",
        "name": "Test Account",
        "branch_no": "123",
        "account_type": "Stock"
    }


@pytest.fixture
def sample_market_data():
    """Sample market data for testing."""
    return {
        "symbol": "2330",
        "market": "TSE",
        "price": 500.0,
        "volume": 1000000,
        "change": 5.0,
        "change_percent": 1.0
    }


# Custom pytest markers
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


# Test utilities
class MockResponse:
    """Mock API response object."""

    def __init__(self, data=None, is_success=True, error_message=None):
        self.data = data
        self.is_success = is_success
        self.error_message = error_message


def create_mock_result(data=None, is_success=True):
    """Create a mock API result object."""
    result = MagicMock()
    result.data = data
    result.is_success = is_success
    return result