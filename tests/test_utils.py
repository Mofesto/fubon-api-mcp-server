"""
Test utility functions from server.py.
"""

from unittest.mock import MagicMock, Mock, patch

from fubon_api_mcp_server.server import (
    _convert_order_data_to_enums,
    _create_order_object,
    _find_target_order,
    _safe_api_call,
    get_order_by_no,
    process_historical_data,
    read_local_stock_data,
    save_to_local_csv,
    validate_and_get_account,
)
from fubon_api_mcp_server.utils import _safe_api_call as utils_safe_api_call
from fubon_api_mcp_server.utils import get_order_by_no as utils_get_order_by_no
from fubon_api_mcp_server.utils import (
    handle_exceptions,
)
from fubon_api_mcp_server.utils import validate_and_get_account as utils_validate_and_get_account


class TestValidateAndGetAccount:
    """Test validate_and_get_account function."""

    def test_validate_and_get_account_success(self, mock_accounts, mock_server_globals):
        """Test successful account validation."""
        account_obj, error = validate_and_get_account("123456")
        assert account_obj is not None
        assert error is None
        assert account_obj.account == "123456"

    def test_validate_and_get_account_not_found(self, mock_accounts, mock_server_globals):
        """Test account not found."""
        account_obj, error = validate_and_get_account("999999")
        assert account_obj is None
        assert error == "找不到帳戶 999999"

    def test_validate_and_get_account_auth_failed(self, mock_server_globals):
        """Test authentication failure."""
        with patch("fubon_api_mcp_server.server.accounts", None):
            account_obj, error = validate_and_get_account("123456")
            assert account_obj is None
            assert "帳戶資訊未初始化" in error


class TestGetOrderByNo:
    """Test get_order_by_no function."""

    def test_get_order_by_no_success(self, mock_accounts, mock_sdk, mock_server_globals):
        """Test successful order retrieval."""
        mock_order = Mock()
        mock_order.order_no = "12345"

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [mock_order]

        mock_sdk.stock.get_order_results.return_value = mock_result

        order_obj, error = get_order_by_no(mock_accounts.data[0], "12345")
        assert order_obj is not None
        assert error is None
        assert order_obj.order_no == "12345"

    def test_get_order_by_no_not_found(self, mock_accounts, mock_sdk, mock_server_globals):
        """Test order not found."""
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = []

        mock_sdk.stock.get_order_results.return_value = mock_result

        order_obj, error = get_order_by_no(mock_accounts.data[0], "99999")
        assert order_obj is None
        assert error == "找不到委託單號 99999"


class TestSafeApiCall:
    """Test _safe_api_call function."""

    def test_safe_api_call_success(self, mock_sdk):
        """Test successful API call."""
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = {"test": "data"}

        def mock_api_func():
            return mock_result

        result = _safe_api_call(mock_api_func, "Test error")
        assert result == {"test": "data"}

    def test_safe_api_call_failure(self, mock_sdk):
        """Test failed API call."""

        def mock_api_func():
            raise Exception("API error")

        result = _safe_api_call(mock_api_func, "Test error")
        assert result == "Test error: API error"


class TestFindTargetOrder:
    """Test _find_target_order function."""

    def test_find_target_order_success(self):
        """Test successful order finding."""
        mock_order = Mock()
        mock_order.order_no = "12345"

        mock_result = Mock()
        mock_result.data = [mock_order]

        order = _find_target_order(mock_result, "12345")
        assert order is not None
        assert order.order_no == "12345"

    def test_find_target_order_not_found(self):
        """Test order not found."""
        mock_result = Mock()
        mock_result.data = []

        order = _find_target_order(mock_result, "99999")
        assert order is None


class TestConvertOrderDataToEnums:
    """Test _convert_order_data_to_enums function."""

    def test_convert_order_data_to_enums(self):
        """Test enum conversion."""
        order_data = {
            "buy_sell": "Buy",
            "market_type": "Common",
            "price_type": "Limit",
            "time_in_force": "ROD",
            "order_type": "Stock",
        }

        enums = _convert_order_data_to_enums(order_data)
        assert enums["buy_sell"] is not None
        assert enums["market_type"] is not None
        assert enums["price_type"] is not None
        assert enums["time_in_force"] is not None
        assert enums["order_type"] is not None


class TestCreateOrderObject:
    """Test _create_order_object function."""

    def test_create_order_object(self):
        """Test order object creation."""
        order_data = {"symbol": "2330", "quantity": 1000, "price": 500.0, "user_def": "test"}

        # Use real enums instead of mocks
        from fubon_neo.constant import BSAction, MarketType, OrderType, PriceType, TimeInForce

        enums = {
            "buy_sell": BSAction.Buy,
            "market_type": MarketType.Common,
            "price_type": PriceType.Limit,
            "time_in_force": TimeInForce.ROD,
            "order_type": OrderType.Stock,
        }

        order = _create_order_object(order_data, enums)
        assert order is not None


class TestProcessHistoricalData:
    """Test process_historical_data function."""

    def test_process_historical_data(self, sample_historical_data):
        """Test historical data processing."""
        processed = process_historical_data(sample_historical_data)
        assert "vol_value" in processed.columns
        assert "price_change" in processed.columns
        assert "change_ratio" in processed.columns


class TestReadLocalStockData:
    """Test read_local_stock_data function."""

    def test_read_local_stock_data_not_exists(self):
        """Test reading non-existent file."""
        result = read_local_stock_data("NONEXISTENT")
        assert result is None

    @patch("pathlib.Path.exists")
    @patch("pandas.read_csv")
    def test_read_local_stock_data_exists(self, mock_read_csv, mock_exists):
        """Test reading existing file."""
        import pandas as pd

        mock_exists.return_value = True
        mock_df = pd.DataFrame({"date": ["2023-01-01"], "close": [100]})
        mock_read_csv.return_value = mock_df

        result = read_local_stock_data("2330")
        assert result is not None


class TestSaveToLocalCsv:
    """Test save_to_local_csv function."""

    @patch("os.path.exists")
    @patch("pandas.DataFrame.to_csv")
    @patch("shutil.move")
    def test_save_to_local_csv(self, mock_move, mock_to_csv, mock_exists):
        """Test saving CSV data."""
        import pandas as pd

        mock_exists.return_value = False

        test_data = [{"date": "2023-01-01", "close": 100}]
        save_to_local_csv("2330", test_data)

        mock_to_csv.assert_called_once()
        mock_move.assert_called_once()


class TestHandleExceptions:
    """Test handle_exceptions decorator."""

    def test_handle_exceptions_success(self):
        """Test decorator with successful function."""

        @handle_exceptions
        def test_func():
            return "success"

        result = test_func()
        assert result == "success"

    def test_handle_exceptions_failure(self, capsys):
        """Test decorator with exception."""

        @handle_exceptions
        def test_func():
            raise ValueError("test error")

        result = test_func()
        assert result is None

        captured = capsys.readouterr()
        assert "test_func exception: test error" in captured.err
        assert "Traceback" in captured.err


class TestUtilsValidateAndGetAccount:
    """Test validate_and_get_account from utils.py."""

    @patch("dotenv.load_dotenv")
    @patch("fubon_neo.sdk.FubonSDK")
    @patch.dict(
        "os.environ",
        {
            "FUBON_USERNAME": "test_user",
            "FUBON_PASSWORD": "test_pass",
            "FUBON_PFX_PATH": "test.pfx",
            "FUBON_PFX_PASSWORD": "test_pfx_pass",
        },
    )
    def test_utils_validate_and_get_account_success(self, mock_sdk_class, mock_load_dotenv):
        """Test successful account validation in utils."""
        mock_sdk = Mock()
        mock_accounts = Mock()
        mock_accounts.is_success = True
        mock_accounts.data = [Mock(account="123456")]
        mock_sdk.login.return_value = mock_accounts
        mock_sdk_class.return_value = mock_sdk

        account_obj, error = utils_validate_and_get_account("123456")
        assert account_obj is not None
        assert error is None
        assert account_obj.account == "123456"

    @patch("dotenv.load_dotenv")
    @patch.dict("os.environ", {}, clear=True)
    def test_utils_validate_and_get_account_missing_env(self, mock_load_dotenv):
        """Test missing environment variables."""
        account_obj, error = utils_validate_and_get_account("123456")
        assert account_obj is None
        assert "Account authentication failed" in error


class TestUtilsGetOrderByNo:
    """Test get_order_by_no from utils.py."""

    @patch("fubon_api_mcp_server.utils.config_module")
    def test_utils_get_order_by_no_success(self, mock_config):
        """Test successful order retrieval in utils."""
        mock_order = Mock()
        mock_order.order_no = "12345"

        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = [mock_order]

        mock_sdk = Mock()
        mock_sdk.stock.get_order_results.return_value = mock_result
        mock_config.sdk = mock_sdk

        mock_account = Mock()
        order_obj, error = utils_get_order_by_no(mock_account, "12345")
        assert order_obj is not None
        assert error is None
        assert order_obj.order_no == "12345"

    @patch("fubon_api_mcp_server.utils.config_module")
    def test_utils_get_order_by_no_sdk_not_init(self, mock_config):
        """Test SDK not initialized."""
        mock_config.sdk = None
        mock_account = Mock()
        order_obj, error = utils_get_order_by_no(mock_account, "12345")
        assert order_obj is None
        assert "SDK not initialized" in error


class TestUtilsSafeApiCall:
    """Test _safe_api_call from utils.py."""

    def test_utils_safe_api_call_success(self):
        """Test successful API call in utils."""
        mock_result = Mock()
        mock_result.is_success = True
        mock_result.data = {"test": "data"}

        def mock_api_func():
            return mock_result

        result = utils_safe_api_call(mock_api_func, "Test error")
        assert result == {"test": "data"}

    def test_utils_safe_api_call_failure(self):
        """Test failed API call in utils."""

        def mock_api_func():
            raise Exception("API error")

        result = utils_safe_api_call(mock_api_func, "Test error")
        assert result == "Test error: API error"
