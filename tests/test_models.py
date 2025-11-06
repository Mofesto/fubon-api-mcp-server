"""
Tests for models in server.py.
"""

import pytest
from pydantic import ValidationError

from fubon_api_mcp_server.server import (
    BatchPlaceOrderArgs,
    CancelOrderArgs,
    GetAccountInfoArgs,
    GetBankBalanceArgs,
    GetEventReportsArgs,
    GetFilledReportsArgs,
    GetHistoricalStatsArgs,
    GetIntradayCandlesArgs,
    GetIntradayQuoteArgs,
    GetIntradayTickerArgs,
    GetIntradayTickersArgs,
    GetIntradayTradesArgs,
    GetIntradayVolumesArgs,
    GetInventoryArgs,
    GetOrderChangedReportsArgs,
    GetOrderReportsArgs,
    GetOrderResultsArgs,
    GetRealtimeQuotesArgs,
    GetSettlementArgs,
    GetSnapshotActivesArgs,
    GetSnapshotMoversArgs,
    GetSnapshotQuotesArgs,
    GetUnrealizedPnLArgs,
    HistoricalCandlesArgs,
    ModifyPriceArgs,
    ModifyQuantityArgs,
    PlaceOrderArgs,
)


class TestAccountArgs:
    """Test account-related argument models."""

    def test_get_account_info_args_valid(self):
        """Test GetAccountInfoArgs with valid data."""
        args = GetAccountInfoArgs(account="")
        assert args.account == ""

        args = GetAccountInfoArgs(account="123456")
        assert args.account == "123456"

    def test_get_bank_balance_args_valid(self):
        """Test GetBankBalanceArgs with valid data."""
        args = GetBankBalanceArgs(account="123456")
        assert args.account == "123456"

    def test_get_inventory_args_valid(self):
        """Test GetInventoryArgs with valid data."""
        args = GetInventoryArgs(account="123456")
        assert args.account == "123456"

    def test_get_settlement_args_valid(self):
        """Test GetSettlementArgs with valid data."""
        args = GetSettlementArgs(account="123456")
        assert args.account == "123456"
        assert args.days == "0d"

        args = GetSettlementArgs(account="123456", days="1d")
        assert args.days == "1d"

    def test_get_unrealized_pnl_args_valid(self):
        """Test GetUnrealizedPnLArgs with valid data."""
        args = GetUnrealizedPnLArgs(account="123456")
        assert args.account == "123456"


class TestMarketDataArgs:
    """Test market data-related argument models."""

    def test_get_intraday_tickers_args_valid(self):
        """Test GetIntradayTickersArgs with valid data."""
        args = GetIntradayTickersArgs(market="TSE")
        assert args.market == "TSE"

    def test_get_intraday_ticker_args_valid(self):
        """Test GetIntradayTickerArgs with valid data."""
        args = GetIntradayTickerArgs(symbol="2330")
        assert args.symbol == "2330"
        assert args.type is None

        args = GetIntradayTickerArgs(symbol="2330", type="oddlot")
        assert args.symbol == "2330"
        assert args.type == "oddlot"

    def test_get_intraday_quote_args_valid(self):
        """Test GetIntradayQuoteArgs with valid data."""
        args = GetIntradayQuoteArgs(symbol="2330")
        assert args.symbol == "2330"

    def test_get_intraday_candles_args_valid(self):
        """Test GetIntradayCandlesArgs with valid data."""
        args = GetIntradayCandlesArgs(symbol="2330")
        assert args.symbol == "2330"

    def test_get_intraday_trades_args_valid(self):
        """Test GetIntradayTradesArgs with valid data."""
        args = GetIntradayTradesArgs(symbol="2330")
        assert args.symbol == "2330"
        assert args.type is None
        assert args.offset is None
        assert args.limit is None

        # Test with optional parameters
        args = GetIntradayTradesArgs(symbol="2330", type="oddlot", offset=0, limit=100)
        assert args.symbol == "2330"
        assert args.type == "oddlot"
        assert args.offset == 0
        assert args.limit == 100

    def test_get_intraday_volumes_args_valid(self):
        """Test GetIntradayVolumesArgs with valid data."""
        args = GetIntradayVolumesArgs(symbol="2330")
        assert args.symbol == "2330"

    def test_get_snapshot_quotes_args_valid(self):
        """Test GetSnapshotQuotesArgs with valid data."""
        args = GetSnapshotQuotesArgs(market="TSE")
        assert args.market == "TSE"

    def test_get_snapshot_movers_args_valid(self):
        """Test GetSnapshotMoversArgs with valid data."""
        args = GetSnapshotMoversArgs(market="TSE")
        assert args.market == "TSE"

    def test_get_snapshot_actives_args_valid(self):
        """Test GetSnapshotActivesArgs with valid data."""
        args = GetSnapshotActivesArgs(market="TSE")
        assert args.market == "TSE"

    def test_get_historical_stats_args_valid(self):
        """Test GetHistoricalStatsArgs with valid data."""
        args = GetHistoricalStatsArgs(symbol="2330")
        assert args.symbol == "2330"

    def test_get_realtime_quotes_args_valid(self):
        """Test GetRealtimeQuotesArgs with valid data."""
        args = GetRealtimeQuotesArgs(symbol="2330")
        assert args.symbol == "2330"


class TestTradingArgs:
    """Test trading-related argument models."""

    def test_place_order_args_valid(self):
        """Test PlaceOrderArgs with valid data."""
        args = PlaceOrderArgs(account="123456", symbol="2330", quantity=1000, price=500.0, buy_sell="Buy")
        assert args.account == "123456"
        assert args.symbol == "2330"
        assert args.quantity == 1000
        assert args.price == 500.0
        assert args.buy_sell == "Buy"
        assert args.market_type == "Common"
        assert args.price_type == "Limit"
        assert args.time_in_force == "ROD"
        assert args.order_type == "Stock"

    def test_cancel_order_args_valid(self):
        """Test CancelOrderArgs with valid data."""
        args = CancelOrderArgs(account="123456", order_no="12345")
        assert args.account == "123456"
        assert args.order_no == "12345"

    def test_modify_price_args_valid(self):
        """Test ModifyPriceArgs with valid data."""
        args = ModifyPriceArgs(account="123456", order_no="12345", new_price=505.0)
        assert args.account == "123456"
        assert args.order_no == "12345"
        assert args.new_price == 505.0

    def test_modify_quantity_args_valid(self):
        """Test ModifyQuantityArgs with valid data."""
        args = ModifyQuantityArgs(account="123456", order_no="12345", new_quantity=1500)
        assert args.account == "123456"
        assert args.order_no == "12345"
        assert args.new_quantity == 1500

    def test_batch_place_order_args_valid(self):
        """Test BatchPlaceOrderArgs with valid data."""
        orders = [{"symbol": "2330", "quantity": 1000, "price": 500.0, "buy_sell": "Buy"}]
        args = BatchPlaceOrderArgs(account="123456", orders=orders)
        assert args.account == "123456"
        assert len(args.orders) == 1
        assert args.max_workers == 10


class TestReportsArgs:
    """Test reports-related argument models."""

    def test_get_order_results_args_valid(self):
        """Test GetOrderResultsArgs with valid data."""
        args = GetOrderResultsArgs(account="123456")
        assert args.account == "123456"

    def test_get_order_reports_args_valid(self):
        """Test GetOrderReportsArgs with valid data."""
        args = GetOrderReportsArgs()
        assert args.limit == 10

        args = GetOrderReportsArgs(limit=5)
        assert args.limit == 5

    def test_get_order_changed_reports_args_valid(self):
        """Test GetOrderChangedReportsArgs with valid data."""
        args = GetOrderChangedReportsArgs()
        assert args.limit == 10

    def test_get_filled_reports_args_valid(self):
        """Test GetFilledReportsArgs with valid data."""
        args = GetFilledReportsArgs()
        assert args.limit == 10

    def test_get_event_reports_args_valid(self):
        """Test GetEventReportsArgs with valid data."""
        args = GetEventReportsArgs()
        assert args.limit == 10

    def test_get_all_reports_args_valid(self):
        """Test GetAllReportsArgs with valid data."""
        args = GetOrderReportsArgs(limit=5)  # GetAllReportsArgs reuses this
        assert args.limit == 5


class TestHistoricalArgs:
    """Test historical data-related argument models."""

    def test_historical_candles_args_valid(self):
        """Test HistoricalCandlesArgs with valid data."""
        args = HistoricalCandlesArgs(symbol="2330", from_date="2023-01-01", to_date="2023-12-31")
        assert args.symbol == "2330"
        assert args.from_date == "2023-01-01"
        assert args.to_date == "2023-12-31"


class TestValidationErrors:
    """Test validation errors for invalid inputs."""

    def test_get_account_info_args_invalid_account_type(self):
        """Test GetAccountInfoArgs with invalid account type."""
        with pytest.raises(ValidationError):
            GetAccountInfoArgs(account=123)  # Should be string

    def test_place_order_args_missing_required(self):
        """Test PlaceOrderArgs with missing required fields."""
        with pytest.raises(ValidationError):
            PlaceOrderArgs(account="123456")  # Missing required fields

    def test_modify_price_args_negative_price(self):
        """Test ModifyPriceArgs with negative price."""
        with pytest.raises(ValidationError):
            ModifyPriceArgs(account="123456", order_no="12345", new_price=-100.0)

    def test_batch_place_order_args_empty_orders(self):
        """Test BatchPlaceOrderArgs with empty orders list."""
        args = BatchPlaceOrderArgs(account="123456", orders=[])
        assert args.orders == []
