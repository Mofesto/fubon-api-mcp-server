
import pytest
from unittest.mock import MagicMock, patch
from fubon_api_mcp_server.trading_service import TradingService
from fubon_neo.sdk import Order
from fubon_neo.constant import BSAction, MarketType, PriceType, TimeInForce, OrderType

class TestTradingServicePriceType:
    @pytest.fixture
    def mock_mcp(self):
        return MagicMock()

    @pytest.fixture
    def mock_sdk(self):
        sdk = MagicMock()
        # Mock stock client
        sdk.stock = MagicMock()
        # Mock place_order return
        mock_result = MagicMock()
        mock_result.is_success = True
        mock_result.data.order_no = "TEST_ORDER"
        sdk.stock.place_order.return_value = mock_result
        return sdk

    @pytest.fixture
    def trading_service(self, mock_mcp, mock_sdk):
        return TradingService(
            mcp=mock_mcp,
            sdk=mock_sdk,
            accounts=["1234567"],
            base_data_dir=MagicMock(),
            reststock=MagicMock(),
            restfutopt=MagicMock()
        )

    def test_place_order_market_price(self, trading_service, mock_sdk):
        """Test place_order with Market price type clears price"""
        args = {
            "account": "1234567",
            "buy_sell": "Buy",
            "symbol": "2330",
            "quantity": 1000,
            "price": "1000",  # Should be ignored
            "price_type": "Market"
        }
        
        with patch("fubon_api_mcp_server.trading_service.validate_and_get_account") as mock_validate:
            mock_validate.return_value = (MagicMock(), None)
            
            result = trading_service.place_order(args)
            
            assert result["status"] == "success"
            
            # Verify SDK call
            mock_sdk.stock.place_order.assert_called_once()
            call_args = mock_sdk.stock.place_order.call_args
            
            # Check Order object in kwargs or args
            if "order" in call_args.kwargs:
                order_obj = call_args.kwargs["order"]
            else:
                order_obj = call_args.args[1]
                
            assert isinstance(order_obj, Order)
            assert order_obj.price == ""
            assert order_obj.price_type == PriceType.Market

    def test_place_order_limit_up(self, trading_service, mock_sdk):
        """Test place_order with LimitUp price type clears price"""
        args = {
            "account": "1234567",
            "buy_sell": "Buy",
            "symbol": "2330",
            "quantity": 1000,
            "price": "1000",  # Should be ignored
            "price_type": "LimitUp"
        }
        
        with patch("fubon_api_mcp_server.trading_service.validate_and_get_account") as mock_validate:
            mock_validate.return_value = (MagicMock(), None)
            
            trading_service.place_order(args)
            
            # Verify SDK call
            call_args = mock_sdk.stock.place_order.call_args
            if "order" in call_args.kwargs:
                order_obj = call_args.kwargs["order"]
            else:
                order_obj = call_args.args[1]
                
            assert order_obj.price == ""
            assert order_obj.price_type == PriceType.LimitUp

    def test_place_order_limit_down(self, trading_service, mock_sdk):
        """Test place_order with LimitDown price type clears price"""
        args = {
            "account": "1234567",
            "buy_sell": "Buy",
            "symbol": "2330",
            "quantity": 1000,
            "price": "1000",  # Should be ignored
            "price_type": "LimitDown"
        }
        
        with patch("fubon_api_mcp_server.trading_service.validate_and_get_account") as mock_validate:
            mock_validate.return_value = (MagicMock(), None)
            
            trading_service.place_order(args)
            
            # Verify SDK call
            call_args = mock_sdk.stock.place_order.call_args
            if "order" in call_args.kwargs:
                order_obj = call_args.kwargs["order"]
            else:
                order_obj = call_args.args[1]
                
            assert order_obj.price == ""
            assert order_obj.price_type == PriceType.LimitDown

    def test_place_order_limit(self, trading_service, mock_sdk):
        """Test place_order with Limit price type keeps price"""
        args = {
            "account": "1234567",
            "buy_sell": "Buy",
            "symbol": "2330",
            "quantity": 1000,
            "price": "1000",
            "price_type": "Limit"
        }
        
        with patch("fubon_api_mcp_server.trading_service.validate_and_get_account") as mock_validate:
            mock_validate.return_value = (MagicMock(), None)
            
            trading_service.place_order(args)
            
            # Verify SDK call
            call_args = mock_sdk.stock.place_order.call_args
            if "order" in call_args.kwargs:
                order_obj = call_args.kwargs["order"]
            else:
                order_obj = call_args.args[1]
                
            assert order_obj.price == "1000"
            assert order_obj.price_type == PriceType.Limit
