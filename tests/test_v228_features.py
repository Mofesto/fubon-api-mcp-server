from types import SimpleNamespace
from unittest.mock import Mock, patch

from fubon_api_mcp_server import server
from fubon_api_mcp_server.market_data_service import MarketDataService
from fubon_api_mcp_server.trading_service import TradingService
from fubon_api_mcp_server.utils import validate_and_get_account, validate_user_def


class DummyMCP:
    def tool(self):
        def decorator(function):
            return function

        return decorator


def make_market_service(tmp_path):
    corporate_actions = SimpleNamespace(
        capital_changes=Mock(),
        dividends=Mock(),
        listing_applicants=Mock(),
    )
    historical = SimpleNamespace(candles=Mock())
    reststock = SimpleNamespace(corporate_actions=corporate_actions, historical=historical)
    return MarketDataService(DummyMCP(), tmp_path, reststock, None, None), reststock


def test_capital_changes_uses_v228_endpoint_and_keeps_wire_shape(tmp_path):
    service, reststock = make_market_service(tmp_path)
    response = {"data": [{"symbol": "2330", "actionType": "capital_reduction", "effectiveDate": "2026-08-01"}]}
    reststock.corporate_actions.capital_changes.return_value = response

    result = service.get_capital_changes({"start_date": "2026-01-01", "end_date": "2026-12-31", "sort": "asc"})

    assert result == {"status": "success", "data": response, "message": "成功獲取資本變動資料"}
    reststock.corporate_actions.capital_changes.assert_called_once_with(
        start_date="2026-01-01", end_date="2026-12-31", sort="asc"
    )


def test_dividends_and_listing_applicants_use_expected_parameters(tmp_path):
    service, reststock = make_market_service(tmp_path)
    reststock.corporate_actions.dividends.return_value = {"data": []}
    reststock.corporate_actions.listing_applicants.return_value = {"data": []}

    dividends = service.get_dividends({"start_date": "2026-01-01", "end_date": "2026-01-31"})
    listings = service.get_listing_applicants({"start_date": "2026-01-01", "end_date": "2026-01-31", "sort": "desc"})

    assert dividends["status"] == "success"
    assert listings["status"] == "success"
    reststock.corporate_actions.dividends.assert_called_once_with(start_date="2026-01-01", end_date="2026-01-31")
    reststock.corporate_actions.listing_applicants.assert_called_once_with(
        start_date="2026-01-01", end_date="2026-01-31", sort="desc"
    )


def test_corporate_actions_report_sdk_errors_as_business_errors(tmp_path):
    service, reststock = make_market_service(tmp_path)
    reststock.corporate_actions.dividends.side_effect = RuntimeError("HTTP 429")

    result = service.get_dividends({"start_date": "2026-01-01", "end_date": "2026-01-31"})

    assert result["status"] == "error"
    assert "HTTP 429" in result["message"]


def test_corporate_actions_do_not_treat_error_envelope_as_success(tmp_path):
    service, reststock = make_market_service(tmp_path)
    reststock.corporate_actions.dividends.return_value = {
        "statusCode": 429,
        "message": "Rate limit exceeded",
    }

    result = service.get_dividends({"start_date": "2026-01-01", "end_date": "2026-01-31"})

    assert result["status"] == "error"
    assert "Rate limit exceeded" in result["message"]


def test_adjusted_historical_candles_bypass_legacy_cache_and_forward_options(tmp_path):
    service, reststock = make_market_service(tmp_path)
    reststock.historical.candles.return_value = {
        "data": [
            {"date": "2026-01-02", "open": 101, "high": 103, "low": 100, "close": 102, "volume": 1000},
            {"date": "2026-01-01", "open": 99, "high": 101, "low": 98, "close": 100, "volume": 900},
        ]
    }

    with (
        patch.object(service, "_ensure_fresh_data") as ensure_fresh,
        patch.object(service, "_read_local_stock_data") as read_cache,
        patch.object(service, "_save_to_local_db") as save_cache,
    ):
        result = service.historical_candles(
            {
                "symbol": "2330",
                "from_date": "2026-01-01",
                "to_date": "2026-01-02",
                "timeframe": "D",
                "adjusted": True,
                "fields": "open,high,low,close,volume",
                "sort": "asc",
            }
        )

    assert result["status"] == "success"
    ensure_fresh.assert_not_called()
    read_cache.assert_not_called()
    save_cache.assert_not_called()
    assert reststock.historical.candles.call_args.kwargs == {
        "symbol": "2330",
        "from": "2026-01-01",
        "to": "2026-01-02",
        "timeframe": "D",
        "adjusted": "true",
        "fields": "open,high,low,close,volume",
        "sort": "asc",
    }
    assert result["data"][0]["date"] == "2026-01-01"


def test_historical_cache_compatibility_is_explicit():
    assert MarketDataService._historical_cache_compatible(None, None, None)
    assert MarketDataService._historical_cache_compatible(False, "D", None)
    assert not MarketDataService._historical_cache_compatible(True, "D", None)
    assert not MarketDataService._historical_cache_compatible(False, "5", None)
    assert not MarketDataService._historical_cache_compatible(False, "D", "close")


def test_user_def_accepts_only_one_to_ten_ascii_alphanumeric_characters():
    assert validate_user_def(None) is None
    assert validate_user_def("Abc123") == "Abc123"

    for invalid in ("", "abc-123", "中文", "a" * 11, 123):
        try:
            validate_user_def(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected invalid user_def: {invalid!r}")


def test_invalid_user_def_never_reaches_sdk_order_api(tmp_path):
    sdk = Mock()
    service = TradingService(DummyMCP(), sdk, ["C04"], tmp_path, Mock(), Mock())

    result = service.place_order(
        {
            "account": "C04",
            "buy_sell": "Buy",
            "symbol": "2330",
            "price": "100",
            "quantity": 1,
            "user_def": "bad-value",
        }
    )

    assert result["status"] == "error"
    assert "user_def" in result["message"]
    sdk.stock.place_order.assert_not_called()


def test_valid_user_def_is_passed_to_sdk_order(tmp_path):
    sdk = Mock()
    sdk.stock.place_order.return_value = SimpleNamespace(is_success=True, data={"order_no": "ORDER-1"})
    service = TradingService(DummyMCP(), sdk, ["C04"], tmp_path, Mock(), Mock())

    with patch(
        "fubon_api_mcp_server.trading_service.validate_and_get_account",
        return_value=(SimpleNamespace(account="C04"), None),
    ):
        result = service.place_order(
            {
                "account": "C04",
                "buy_sell": "Buy",
                "symbol": "2330",
                "price": "100",
                "quantity": 1,
                "user_def": "FromPy8",
            }
        )

    assert result["status"] == "success"
    sent_order = sdk.stock.place_order.call_args.kwargs["order"]
    assert 'user_def: "FromPy8"' in repr(sent_order)


def test_v228_api_key_login_uses_web_certificate(tmp_path):
    sdk = Mock()
    sdk.apikey_login.return_value = SimpleNamespace(
        is_success=True,
        data=[SimpleNamespace(account="C04")],
    )

    env = {
        "FUBON_API_KEY": "test_api_key_1234567890",
        "FUBON_API_SECRET": None,
        "FUBON_USERNAME": "personal-id",
        "FUBON_PASSWORD": None,
        "FUBON_PFX_PATH": str(tmp_path / "web-cert.pfx"),
        "FUBON_PFX_PASSWORD": "cert-pass",
    }

    with (
        patch("dotenv.load_dotenv"),
        patch("os.getenv", side_effect=lambda key, default=None: env.get(key, default)),
        patch("fubon_neo.sdk.FubonSDK", return_value=sdk),
        patch("fubon_api_mcp_server.utils.config_module") as config,
    ):
        config.sdk = None
        account, error = validate_and_get_account("C04")

    assert error is None
    assert account.account == "C04"
    sdk.apikey_login.assert_called_once_with(
        "personal-id", "test_api_key_1234567890", str(tmp_path / "web-cert.pfx"), "cert-pass"
    )


def test_server_state_wires_v228_api_key_login():
    sdk = Mock()
    sdk.apikey_login.return_value = SimpleNamespace(
        is_success=True,
        data=[SimpleNamespace(account="C04")],
    )
    sdk.marketdata.rest_client.stock = Mock()
    sdk.marketdata.rest_client.futopt = Mock()

    state = server.MCPServerState()
    with patch("fubon_api_mcp_server.server.FubonSDK", return_value=sdk):
        assert state.initialize_sdk("personal-id", "", "web-cert.pfx", "cert-pass", api_key="api-key")

    sdk.apikey_login.assert_called_once_with("personal-id", "api-key", "web-cert.pfx", "cert-pass")
    sdk.login.assert_not_called()
    state.logout()
