"""
Tests for models.py - Pydantic model validation.

This module tests all Pydantic models used for parameter validation
in the Fubon API MCP Server.
"""

import pytest
from pydantic import ValidationError

from fubon_mcp.models import (
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
    GetOrderStatusArgs,
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


class TestHistoricalDataModels:
    """Test historical data related models."""

    def test_historical_candles_args_valid(self):
        """Test HistoricalCandlesArgs with valid data."""
        args = HistoricalCandlesArgs(
            symbol="2330",
            from_date="2024-01-01",
            to_date="2024-01-31"
        )
        assert args.symbol == "2330"
        assert args.from_date == "2024-01-01"
        assert args.to_date == "2024-01-31"

    def test_historical_candles_args_missing_required(self):
        """Test HistoricalCandlesArgs with missing required fields."""
        with pytest.raises(ValidationError):
            HistoricalCandlesArgs(symbol="2330", from_date="2024-01-01")
            # Missing to_date


class TestTradingModels:
    """Test trading related models."""

    def test_place_order_args_valid(self):
        """Test PlaceOrderArgs with valid data."""
        args = PlaceOrderArgs(
            account="12345678",
            symbol="2330",
            quantity=1000,
            price=500.0,
            buy_sell="Buy"
        )
        assert args.account == "12345678"
        assert args.symbol == "2330"
        assert args.quantity == 1000
        assert args.price == 500.0
        assert args.buy_sell == "Buy"
        assert args.market_type == "Common"  # default
        assert args.price_type == "Limit"    # default
        assert args.time_in_force == "ROD"   # default
        assert args.order_type == "Stock"    # default

    def test_place_order_args_invalid_buy_sell(self):
        """Test PlaceOrderArgs accepts any string for buy_sell (no validation)."""
        # Note: Current model doesn't restrict buy_sell values
        args = PlaceOrderArgs(
            account="12345678",
            symbol="2330",
            quantity=1000,
            price=500.0,
            buy_sell="Invalid"  # This is accepted as any string
        )
        assert args.buy_sell == "Invalid"

    def test_cancel_order_args_valid(self):
        """Test CancelOrderArgs with valid data."""
        args = CancelOrderArgs(account="12345678", order_no="12345")
        assert args.account == "12345678"
        assert args.order_no == "12345"

    def test_modify_price_args_valid(self):
        """Test ModifyPriceArgs with valid data."""
        args = ModifyPriceArgs(
            account="12345678",
            order_no="12345",
            new_price=505.0
        )
        assert args.account == "12345678"
        assert args.order_no == "12345"
        assert args.new_price == 505.0

    def test_modify_quantity_args_valid(self):
        """Test ModifyQuantityArgs with valid data."""
        args = ModifyQuantityArgs(
            account="12345678",
            order_no="12345",
            new_quantity=2000
        )
        assert args.account == "12345678"
        assert args.order_no == "12345"
        assert args.new_quantity == 2000

    def test_batch_place_order_args_valid(self):
        """Test BatchPlaceOrderArgs with valid data."""
        orders = [
            {
                "symbol": "2330",
                "quantity": 1000,
                "price": 500.0,
                "buy_sell": "Buy"
            }
        ]
        args = BatchPlaceOrderArgs(account="12345678", orders=orders)
        assert args.account == "12345678"
        assert len(args.orders) == 1
        assert args.max_workers == 10  # default


class TestAccountModels:
    """Test account related models."""

    def test_get_account_info_args_valid(self):
        """Test GetAccountInfoArgs with valid data."""
        args = GetAccountInfoArgs(account="12345678")
        assert args.account == "12345678"

    def test_get_inventory_args_valid(self):
        """Test GetInventoryArgs with valid data."""
        args = GetInventoryArgs(account="12345678")
        assert args.account == "12345678"

    def test_get_unrealized_pnl_args_valid(self):
        """Test GetUnrealizedPnLArgs with valid data."""
        args = GetUnrealizedPnLArgs(account="12345678")
        assert args.account == "12345678"

    def test_get_settlement_args_valid(self):
        """Test GetSettlementArgs with valid data."""
        args = GetSettlementArgs(account="12345678")
        assert args.account == "12345678"
        assert args.days == "0d"  # default

    def test_get_bank_balance_args_valid(self):
        """Test GetBankBalanceArgs with valid data."""
        args = GetBankBalanceArgs(account="12345678")
        assert args.account == "12345678"


class TestMarketDataModels:
    """Test market data related models."""

    def test_get_intraday_tickers_args_valid(self):
        """Test GetIntradayTickersArgs with valid data."""
        args = GetIntradayTickersArgs(market="TSE")
        assert args.market == "TSE"

    def test_get_intraday_ticker_args_valid(self):
        """Test GetIntradayTickerArgs with valid data."""
        args = GetIntradayTickerArgs(symbol="2330")
        assert args.symbol == "2330"

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


class TestOrderReportModels:
    """Test order and report related models."""

    def test_get_order_status_args_valid(self):
        """Test GetOrderStatusArgs with valid data."""
        args = GetOrderStatusArgs(account="12345678")
        assert args.account == "12345678"

    def test_get_order_reports_args_valid(self):
        """Test GetOrderReportsArgs with valid data."""
        args = GetOrderReportsArgs()
        assert args.limit == 10  # default

        args = GetOrderReportsArgs(limit=50)
        assert args.limit == 50

    def test_get_order_changed_reports_args_valid(self):
        """Test GetOrderChangedReportsArgs with valid data."""
        args = GetOrderChangedReportsArgs()
        assert args.limit == 10  # default

    def test_get_filled_reports_args_valid(self):
        """Test GetFilledReportsArgs with valid data."""
        args = GetFilledReportsArgs()
        assert args.limit == 10  # default

    def test_get_event_reports_args_valid(self):
        """Test GetEventReportsArgs with valid data."""
        args = GetEventReportsArgs()
        assert args.limit == 10  # default

    def test_get_order_results_args_valid(self):
        """Test GetOrderResultsArgs with valid data."""
        args = GetOrderResultsArgs(account="12345678")
        assert args.account == "12345678"


class TestModelValidation:
    """Test general model validation behavior."""

    def test_model_field_types(self):
        """Test that models enforce correct field types."""
        # Test that string cannot be passed to int field
        with pytest.raises(ValidationError):
            PlaceOrderArgs(
                account="12345678",
                symbol="2330",
                quantity="not_an_int",  # Should be int
                price=500.0,
                buy_sell="Buy"
            )

        # Test that string cannot be passed to float field
        with pytest.raises(ValidationError):
            PlaceOrderArgs(
                account="12345678",
                symbol="2330",
                quantity=1000,
                price="not_a_float",  # Should be float
                buy_sell="Buy"
            )

    def test_model_optional_fields(self):
        """Test optional fields in models."""
        # PlaceOrderArgs has optional fields with defaults
        args = PlaceOrderArgs(
            account="12345678",
            symbol="2330",
            quantity=1000,
            price=500.0,
            buy_sell="Buy"
        )

        # These should have default values
        assert args.market_type == "Common"
        assert args.price_type == "Limit"
        assert args.time_in_force == "ROD"
        assert args.order_type == "Stock"
        assert args.user_def is None
        assert args.is_non_blocking is False