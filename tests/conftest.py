"""
Pytest configuration and fixtures for fubon_api_mcp_server tests.
"""

from unittest.mock import MagicMock, Mock

import pytest


@pytest.fixture
def mock_accounts():
    """Mock accounts object for testing."""
    mock_accounts = Mock()
    mock_accounts.is_success = True
    mock_accounts.data = [
        Mock(account="123456", name="Test User", branch_no="001", account_type="stock"),
        Mock(account="789012", name="Test User 2", branch_no="002", account_type="stock"),
    ]
    return mock_accounts


@pytest.fixture
def mock_sdk():
    """Mock SDK object for testing."""
    mock_sdk = Mock()
    mock_sdk.marketdata = Mock()
    mock_sdk.marketdata.rest_client = Mock()
    mock_sdk.marketdata.rest_client.stock = Mock()
    mock_sdk.accounting = Mock()
    mock_sdk.stock = Mock()
    return mock_sdk


@pytest.fixture
def mock_server_globals(mock_accounts, mock_sdk):
    """Mock global variables in server.py for testing."""
    from unittest.mock import patch

    with (
        patch("fubon_api_mcp_server.server.accounts", mock_accounts),
        patch("fubon_api_mcp_server.server.sdk", mock_sdk),
        patch("fubon_api_mcp_server.server.reststock", mock_sdk.marketdata.rest_client.stock),
    ):
        yield


@pytest.fixture
def mock_restfutopt():
    """Mock restfutopt object for futures/options testing."""
    mock_restfutopt = Mock()
    mock_restfutopt.intraday = Mock()
    return mock_restfutopt


@pytest.fixture
def mock_server_globals_futopt(mock_accounts, mock_sdk, mock_restfutopt):
    """Mock global variables in server.py for futures/options testing."""
    from unittest.mock import patch

    with (
        patch("fubon_api_mcp_server.server.accounts", mock_accounts),
        patch("fubon_api_mcp_server.server.sdk", mock_sdk),
        patch("fubon_api_mcp_server.server.reststock", mock_sdk.marketdata.rest_client.stock),
        patch("fubon_api_mcp_server.server.restfutopt", mock_restfutopt),
    ):
        yield


@pytest.fixture
def sample_order_data():
    """Sample order data for testing."""
    return {
        "account": "123456",
        "symbol": "2330",
        "quantity": 1000,
        "price": 500.0,
        "buy_sell": "Buy",
        "market_type": "Common",
        "price_type": "Limit",
        "time_in_force": "ROD",
        "order_type": "Stock",
    }


@pytest.fixture
def sample_batch_orders():
    """Sample batch orders data for testing."""
    return [
        {"symbol": "2330", "quantity": 1000, "price": 500.0, "buy_sell": "Buy"},
        {"symbol": "2454", "quantity": 2000, "price": 800.0, "buy_sell": "Sell"},
    ]


@pytest.fixture
def sample_historical_data():
    """Sample historical data for testing."""
    import pandas as pd

    return pd.DataFrame(
        {
            "date": pd.date_range("2023-01-01", periods=5),
            "open": [100, 101, 102, 103, 104],
            "high": [105, 106, 107, 108, 109],
            "low": [95, 96, 97, 98, 99],
            "close": [102, 103, 104, 105, 106],
            "volume": [1000000, 1100000, 1200000, 1300000, 1400000],
        }
    )
