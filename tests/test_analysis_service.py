"""Tests for the Fubon-backed, read-only analysis service."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest

from fubon_api_mcp_server.analysis_service import AnalysisService
from fubon_api_mcp_server.quant_analysis import InsufficientDataError, build_return_matrix, calculate_var_metrics


def market_history(symbol: str, days: int = 280, **_kwargs) -> pd.DataFrame:
    symbol_shift = sum(ord(character) for character in symbol) % 17
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    trend = np.linspace(80 + symbol_shift, 120 + symbol_shift, days)
    cycle = np.sin(np.arange(days) / (7 + symbol_shift % 3)) * (1.5 + symbol_shift / 20)
    close = trend + cycle
    return pd.DataFrame(
        {
            "date": dates,
            "open": close - 0.4,
            "high": close + 1.2,
            "low": close - 1.1,
            "close": close,
            "volume": 1000 + (np.arange(days) % 20) * 35 + symbol_shift,
        }
    )


@pytest.fixture
def service():
    mcp = Mock()
    sdk = Mock()
    return AnalysisService(mcp, sdk, ["test-account"], Mock(), Mock())


@pytest.fixture
def portfolio():
    return {
        "inventory": [
            {
                "stock_no": "2330",
                "quantity": 1000,
                "market_price": 100,
                "market_value": 100000,
                "unrealized_pnl": 5000,
            },
            {
                "stock_no": "2454",
                "quantity": 500,
                "market_price": 100,
                "market_value": 50000,
                "unrealized_pnl": -1000,
            },
        ],
        "as_of": "2026-08-06T09:00:00+08:00",
    }


@pytest.mark.parametrize("method", ["historical", "parametric", "monte_carlo"])
@patch("fubon_api_mcp_server.analysis_service.validate_and_get_account")
def test_var_uses_observed_returns(mock_validate, service, portfolio, method):
    mock_validate.return_value = (Mock(), None)
    with (
        patch.object(service, "_get_portfolio_data", return_value=portfolio),
        patch.object(service, "_get_stock_history", side_effect=market_history),
    ):
        result = service.calculate_portfolio_var(
            {
                "account": "test-account",
                "method": method,
                "lookback_days": 252,
                "simulations": 2000,
            }
        )

    assert result["status"] == "success"
    assert result["data"]["portfolio_value"] == 150000
    assert result["data"]["var_estimate"] >= 0
    assert result["data"]["cvar_estimate"] >= result["data"]["var_estimate"]
    assert result["data"]["coverage"]["observations"] >= 60
    assert result["data"]["data_source"] == "fubon_accounting+fubon_marketdata"


@patch("fubon_api_mcp_server.analysis_service.validate_and_get_account")
def test_var_rejects_empty_portfolio(mock_validate, service):
    mock_validate.return_value = (Mock(), None)
    empty = {"inventory": [], "as_of": "2026-08-06T09:00:00+08:00"}
    with patch.object(service, "_get_portfolio_data", return_value=empty):
        result = service.calculate_portfolio_var({"account": "test-account"})
    assert result["status"] == "error"
    assert result["message"].startswith("insufficient_data:")


@patch("fubon_api_mcp_server.analysis_service.validate_and_get_account")
def test_stress_test_uses_only_explicit_shocks(mock_validate, service, portfolio):
    mock_validate.return_value = (Mock(), None)
    with patch.object(service, "_get_portfolio_data", return_value=portfolio):
        result = service.run_portfolio_stress_test(
            {
                "account": "test-account",
                "scenarios": [
                    {
                        "name": "explicit shock",
                        "equity_change": -0.2,
                        "symbol_changes": {"2454": -0.1},
                    }
                ],
            }
        )

    scenario = result["data"]["stress_test_results"][0]
    assert result["status"] == "success"
    assert scenario["total_projected_change"] == pytest.approx(-25000)
    assert result["data"]["assumption_source"] == "caller_supplied_price_shocks"


@patch("fubon_api_mcp_server.analysis_service.validate_and_get_account")
def test_stress_test_rejects_obsolete_rate_sensitivity_shape(mock_validate, service, portfolio):
    mock_validate.return_value = (Mock(), None)
    with patch.object(service, "_get_portfolio_data", return_value=portfolio):
        result = service.run_portfolio_stress_test(
            {"account": "test-account", "scenarios": [{"name": "rate_hike", "rate_increase": 0.02}]}
        )
    assert result["status"] == "error"
    assert "equity_change" in result["message"]


@patch("fubon_api_mcp_server.analysis_service.validate_and_get_account")
def test_stress_test_rejects_out_of_range_symbol_shock(mock_validate, service, portfolio):
    mock_validate.return_value = (Mock(), None)
    with patch.object(service, "_get_portfolio_data", return_value=portfolio):
        result = service.run_portfolio_stress_test(
            {
                "account": "test-account",
                "scenarios": [{"name": "invalid", "equity_change": -0.2, "symbol_changes": {"2330": -1.1}}],
            }
        )
    assert result["status"] == "error"
    assert "symbol_changes" in result["message"]


@patch("fubon_api_mcp_server.analysis_service.validate_and_get_account")
def test_optimization_uses_historical_mean_and_covariance(mock_validate, service, portfolio):
    mock_validate.return_value = (Mock(), None)
    with (
        patch.object(service, "_get_portfolio_data", return_value=portfolio),
        patch.object(service, "_get_stock_history", side_effect=market_history),
    ):
        result = service.optimize_portfolio_allocation(
            {
                "account": "test-account",
                "optimization_method": "min_volatility",
                "lookback_days": 252,
                "max_weight": 0.8,
            }
        )

    assert result["status"] == "success"
    assert sum(result["data"]["optimized_weights"].values()) == pytest.approx(1.0)
    assert max(result["data"]["optimized_weights"].values()) <= 0.8 + 1e-8
    assert set(result["data"]["asset_expected_returns"]) == {"2330", "2454"}
    assert "annualized_covariance" in result["data"]


@patch("fubon_api_mcp_server.analysis_service.validate_and_get_account")
def test_attribution_reports_source_backed_contributions(mock_validate, service, portfolio):
    mock_validate.return_value = (Mock(), None)
    fills = [
        {"date": "2026/08/01", "stock_no": "2330", "buy_sell": "Buy", "filled_qty": 10, "filled_price": 100},
        {"date": "2026/08/02", "stock_no": "2330", "buy_sell": "Sell", "filled_qty": 5, "filled_price": 110},
    ]
    with (
        patch.object(service, "_fetch_filled_history", return_value=fills),
        patch.object(service, "_get_portfolio_data", return_value=portfolio),
        patch.object(service, "_get_stock_history", side_effect=market_history),
    ):
        result = service.calculate_performance_attribution({"account": "test-account", "benchmark": "IX0001", "period": "1M"})

    assert result["status"] == "success"
    contribution = result["data"]["fill_cash_flow_contribution"][0]
    assert contribution["net_trading_cash_flow"] == pytest.approx(-450)
    assert "portfolio_return" in result["data"]["unavailable_metrics"]
    assert "total_portfolio_return" not in result["data"]


def test_filled_history_is_split_into_thirty_day_read_queries(service):
    service.sdk.stock.filled_history.return_value = SimpleNamespace(is_success=True, data=[], message=None)
    service._fetch_filled_history(Mock(), pd.Timestamp("2026-01-01").date(), pd.Timestamp("2026-03-05").date())
    calls = service.sdk.stock.filled_history.call_args_list
    assert len(calls) == 3
    assert calls[0].kwargs["start_date"] == "20260101"
    assert calls[0].kwargs["end_date"] == "20260130"
    assert calls[-1].kwargs["end_date"] == "20260305"


def test_filled_history_retries_bounded_rate_limit(service):
    limited = SimpleNamespace(is_success=False, data=None, message="業務系統流量控管")
    success = SimpleNamespace(is_success=True, data=[], message=None)
    service.sdk.stock.filled_history.side_effect = [limited, limited, success]

    with patch("fubon_api_mcp_server.analysis_service.time.sleep") as sleep:
        result = service._fetch_filled_history(Mock(), pd.Timestamp("2026-01-01").date(), pd.Timestamp("2026-01-02").date())

    assert result == []
    assert service.sdk.stock.filled_history.call_count == 3
    assert [call.args[0] for call in sleep.call_args_list] == [1.0, 2.0]


def test_accounting_query_uses_same_bounded_rate_limit_retry(service):
    query = Mock(
        side_effect=[
            RuntimeError("業務系統流量控管"),
            SimpleNamespace(is_success=True, data=[], message=None),
        ]
    )

    with patch("fubon_api_mcp_server.analysis_service.time.sleep") as sleep:
        result = service._query_records_with_retry(query, "庫存")

    assert result == []
    assert query.call_count == 2
    sleep.assert_called_once_with(1.0)


def test_statistical_spreads_use_requested_symbols(service):
    with patch.object(service, "_get_stock_history", side_effect=market_history):
        result = service.detect_arbitrage_opportunities(
            {
                "symbols": ["2330", "2454", "2317"],
                "arbitrage_types": ["statistical"],
                "lookback_days": 252,
            }
        )
    assert result["status"] == "success"
    assert len(result["data"]["statistical_pairs"]) == 3
    assert {item["left_symbol"] for item in result["data"]["statistical_pairs"]} <= {"2330", "2454", "2317"}
    assert "potential_profit" not in result["data"]["statistical_pairs"][0]


def test_futures_calendar_spread_uses_requested_contracts(service):
    with patch.object(service, "_get_futopt_history", side_effect=market_history):
        result = service.detect_arbitrage_opportunities(
            {
                "arbitrage_types": ["futures_calendar"],
                "futures_pairs": [{"near_symbol": "TXFQ6", "far_symbol": "TXFU6"}],
                "lookback_days": 252,
            }
        )
    assert result["status"] == "success"
    spread = result["data"]["futures_calendar_spreads"][0]
    assert spread["near_symbol"] == "TXFQ6"
    assert spread["far_symbol"] == "TXFU6"
    assert "z_score" in spread


def test_sentiment_uses_explicit_symbols_and_real_components(service):
    with patch.object(service, "_get_stock_history", side_effect=market_history):
        result = service.generate_market_sentiment_index(
            {"symbols": ["2330", "2454"], "index_components": ["technical", "volume"], "lookback_period": 60}
        )
    assert result["status"] == "success"
    assert result["data"]["data_source"] == "fubon_marketdata"
    assert len(result["data"]["symbols"]) == 2
    assert "options" not in result["data"]
    assert "news" not in result["data"]


def test_sentiment_rejects_unsupported_components(service):
    result = service.generate_market_sentiment_index(
        {"symbols": ["2330"], "index_components": ["news"], "lookback_period": 60}
    )
    assert result["status"] == "error"
    assert "news" in result["message"]


def test_sentiment_fails_closed_when_history_is_missing(service):
    with patch.object(service, "_get_stock_history", side_effect=InsufficientDataError("正式行情不足")):
        result = service.generate_market_sentiment_index({"symbols": ["2330"]})
    assert result["status"] == "error"
    assert result["message"] == "insufficient_data: 正式行情不足"


def test_analyze_stock_uses_fubon_history(service):
    with patch.object(service, "_get_stock_history", side_effect=market_history):
        result = service.analyze_stock({"symbol": "2330"})
    assert result["status"] == "success"
    assert result["data"]["data_source"] == "fubon_marketdata"
    assert result["data"]["latest_market_date"]


def test_stock_history_parses_fubon_response_and_checks_freshness(service):
    frame = market_history("2330", 80)
    service.reststock.historical.candles.return_value = {"data": frame.to_dict("records")}

    result = service._get_stock_history("2330", 60)

    assert len(result) == 61
    assert result["date"].is_monotonic_increasing
    call = service.reststock.historical.candles.call_args
    assert call.kwargs["symbol"] == "2330"
    assert "from" in call.kwargs and "to" in call.kwargs


def test_portfolio_data_uses_only_accounting_and_quote_queries(service):
    account_obj = Mock()
    service.sdk.accounting.inventories.return_value = SimpleNamespace(
        is_success=True,
        data=[SimpleNamespace(stock_no="2330", today_qty=1000, odd=SimpleNamespace(today_qty=0))],
        message=None,
    )
    service.sdk.accounting.unrealized_gains_and_loses.return_value = SimpleNamespace(
        is_success=True,
        data=[
            SimpleNamespace(
                stock_no="2330",
                today_qty=1000,
                cost_price=90,
                unrealized_profit=10000,
                unrealized_loss=0,
            )
        ],
        message=None,
    )
    service.reststock.intraday.quote.return_value = {"lastPrice": 100}

    result = service._get_portfolio_data(account_obj, "redacted")

    assert result["inventory"][0]["market_value"] == 100000
    assert result["inventory"][0]["cost_price"] == 90
    service.sdk.accounting.inventories.assert_called_once_with(account=account_obj)
    service.sdk.accounting.unrealized_gains_and_loses.assert_called_once_with(account=account_obj)
    service.reststock.intraday.quote.assert_called_once_with(symbol="2330")


def test_quant_calculations_reject_short_series():
    short = pd.Series(np.linspace(-0.01, 0.01, 10))
    with pytest.raises(InsufficientDataError):
        calculate_var_metrics(short, 100000, 0.95, 1, "historical", 1000)


def test_return_matrix_requires_all_requested_symbols():
    def loader(symbol, _lookback):
        return market_history(symbol, 280) if symbol == "2330" else pd.DataFrame()

    with pytest.raises(InsufficientDataError, match="2454"):
        build_return_matrix(["2330", "2454"], 252, loader)


class GuardedStockClient:
    WRITE_METHODS = {
        "place_order",
        "cancel_order",
        "modify_price",
        "modify_quantity",
        "batch_place_order",
        "condition_order",
    }

    def __init__(self, stock_client):
        self._stock_client = stock_client

    def __getattr__(self, name):
        if name in self.WRITE_METHODS:
            raise AssertionError(f"唯讀整合測試禁止存取交易寫入方法: {name}")
        return getattr(self._stock_client, name)


class GuardedSDK:
    def __init__(self, sdk):
        self.accounting = sdk.accounting
        self.stock = GuardedStockClient(sdk.stock)


@pytest.mark.integration
@pytest.mark.live_readonly
class TestLiveReadOnlyAnalysis:
    @pytest.fixture(scope="class")
    def live_service(self):
        if os.getenv("RUN_FUBON_LIVE_READONLY") != "1":
            pytest.skip("設定 RUN_FUBON_LIVE_READONLY=1 才會執行真實帳號唯讀測試")

        from dotenv import load_dotenv
        from fubon_neo.sdk import FubonSDK

        load_dotenv()
        required = ["FUBON_USERNAME", "FUBON_PASSWORD", "FUBON_PFX_PATH"]
        if not all(os.getenv(name) for name in required):
            pytest.skip("缺少真實 API 登入環境變數")

        sdk = FubonSDK()
        login = sdk.login(
            os.environ["FUBON_USERNAME"],
            os.environ["FUBON_PASSWORD"],
            os.environ["FUBON_PFX_PATH"],
            os.getenv("FUBON_PFX_PASSWORD", ""),
        )
        if not login or not login.is_success or not login.data:
            pytest.skip("富邦 SDK 登入失敗")

        sdk.init_realtime()
        account_obj = login.data[0]
        reststock = sdk.marketdata.rest_client.stock
        restfutopt = sdk.marketdata.rest_client.futopt
        analysis = AnalysisService(Mock(), GuardedSDK(sdk), [account_obj.account], reststock, restfutopt)
        yield analysis, account_obj
        sdk.logout()

    def test_live_market_sentiment_query(self, live_service):
        analysis, _ = live_service
        result = analysis.generate_market_sentiment_index(
            {"symbols": ["2330"], "index_components": ["technical", "volume"], "lookback_period": 60}
        )
        assert result["status"] == "success", result["message"]
        assert result["data"]["data_source"] == "fubon_marketdata"
        assert result["data"]["symbols"][0]["observations"] >= 30

    def test_live_account_var_is_success_or_explicitly_insufficient(self, live_service):
        analysis, account_obj = live_service
        with patch("fubon_api_mcp_server.analysis_service.validate_and_get_account", return_value=(account_obj, None)):
            result = analysis.calculate_portfolio_var({"account": "redacted", "lookback_days": 60})
        assert result["status"] in {"success", "error"}
        if result["status"] == "error":
            assert result["message"].startswith("insufficient_data:")

    def test_live_stock_analysis_and_statistical_spread(self, live_service):
        analysis, _ = live_service
        stock_result = analysis.analyze_stock({"symbol": "2330"})
        spread_result = analysis.detect_arbitrage_opportunities(
            {
                "symbols": ["2330", "2454"],
                "arbitrage_types": ["statistical"],
                "lookback_days": 60,
            }
        )
        assert stock_result["status"] == "success", stock_result["message"]
        assert spread_result["status"] == "success", spread_result["message"]
        assert spread_result["data"]["coverage"]["statistical"]["observations"] >= 60

    def test_live_optimization_with_explicit_symbols(self, live_service):
        analysis, account_obj = live_service
        with patch("fubon_api_mcp_server.analysis_service.validate_and_get_account", return_value=(account_obj, None)):
            result = analysis.optimize_portfolio_allocation(
                {
                    "account": "redacted",
                    "symbols": ["2330", "2454"],
                    "optimization_method": "min_volatility",
                    "lookback_days": 60,
                }
            )
        assert result["status"] == "success", result["message"]
        assert sum(result["data"]["optimized_weights"].values()) == pytest.approx(1.0)

    def test_live_stress_and_attribution_are_success_or_explicitly_insufficient(self, live_service):
        analysis, account_obj = live_service
        with patch("fubon_api_mcp_server.analysis_service.validate_and_get_account", return_value=(account_obj, None)):
            stress = analysis.run_portfolio_stress_test(
                {
                    "account": "redacted",
                    "scenarios": [{"name": "explicit_minus_10_percent", "equity_change": -0.1}],
                }
            )
            attribution = analysis.calculate_performance_attribution(
                {"account": "redacted", "benchmark": "IX0001", "period": "1M"}
            )

        for result in [stress, attribution]:
            assert result["status"] in {"success", "error"}
            if result["status"] == "error":
                assert result["message"].startswith("insufficient_data:")
