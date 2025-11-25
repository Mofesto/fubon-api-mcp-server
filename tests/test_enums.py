"""
測試 enums.py 模組的枚舉轉換函數
"""

import pytest
from fubon_neo.constant import (
    BSAction,
    ConditionMarketType,
    ConditionOrderType,
    ConditionPriceType,
    ConditionStatus,
    Direction,
    HistoryStatus,
    MarketType,
    Operator,
    OrderType,
    PriceType,
    StockType,
    StopSign,
    TimeInForce,
    TimeSliceOrderType,
    TradingType,
    TriggerContent,
)

from fubon_api_mcp_server.enums import (
    enum_to_string,
    safe_enum_conversion,
    to_bs_action,
    to_condition_market_type,
    to_condition_order_type,
    to_condition_price_type,
    to_condition_status,
    to_direction,
    to_history_status,
    to_market_type,
    to_operator,
    to_order_type,
    to_price_type,
    to_stock_types,
    to_stop_sign,
    to_time_in_force,
    to_time_slice_order_type,
    to_trading_type,
    to_trigger_content,
    validate_enum_value,
)


class TestSafeEnumConversion:
    """測試 safe_enum_conversion 函數"""

    def test_valid_conversion(self):
        """測試有效的轉換"""
        result = safe_enum_conversion(BSAction, "Buy")
        assert result == BSAction.Buy

    def test_invalid_conversion_with_default(self):
        """測試無效轉換返回預設值"""
        result = safe_enum_conversion(BSAction, "Invalid", BSAction.Sell)
        assert result == BSAction.Sell

    def test_invalid_conversion_without_default(self):
        """測試無效轉換拋出異常"""
        with pytest.raises(ValueError, match="無效的枚舉值"):
            safe_enum_conversion(BSAction, "Invalid")


class TestBasicEnumConversions:
    """測試基本枚舉轉換函數"""

    def test_to_bs_action_valid(self):
        """測試有效的 BSAction 轉換"""
        assert to_bs_action("Buy") == BSAction.Buy
        assert to_bs_action("Sell") == BSAction.Sell

    def test_to_market_type_valid(self):
        """測試有效的 MarketType 轉換"""
        assert to_market_type("Common") == MarketType.Common

    def test_to_order_type_valid(self):
        """測試有效的 OrderType 轉換"""
        assert to_order_type("Stock") == OrderType.Stock
        assert to_order_type("Margin") == OrderType.Margin

    def test_to_price_type_valid(self):
        """測試有效的 PriceType 轉換"""
        assert to_price_type("Limit") == PriceType.Limit
        assert to_price_type("Market") == PriceType.Market

    def test_to_time_in_force_valid(self):
        """測試有效的 TimeInForce 轉換"""
        assert to_time_in_force("ROD") == TimeInForce.ROD
        assert to_time_in_force("IOC") == TimeInForce.IOC
        assert to_time_in_force("FOK") == TimeInForce.FOK


class TestConditionEnumConversions:
    """測試條件單相關的枚舉轉換函數"""

    def test_to_trading_type_valid(self):
        """測試有效的 TradingType 轉換"""
        assert to_trading_type("Reference") == TradingType.Reference
        assert to_trading_type("Scheduled") == TradingType.Scheduled

    def test_to_trigger_content_valid(self):
        """測試有效的 TriggerContent 轉換"""
        assert to_trigger_content("MatchedPrice") == TriggerContent.MatchedPrice
        assert to_trigger_content("BidPrice") == TriggerContent.BidPrice
        assert to_trigger_content("AskPrice") == TriggerContent.AskPrice
        assert to_trigger_content("TotalQuantity") == TriggerContent.TotalQuantity

    def test_to_operator_valid(self):
        """測試有效的 Operator 轉換"""
        assert to_operator("LessThan") == Operator.LessThan
        assert to_operator("GreaterThan") == Operator.GreaterThan
        assert to_operator("LessThanOrEqual") == Operator.LessThanOrEqual
        assert to_operator("GreaterThanOrEqual") == Operator.GreaterThanOrEqual

    def test_to_condition_market_type_valid(self):
        """測試有效的 ConditionMarketType 轉換"""
        assert to_condition_market_type("Common") == ConditionMarketType.Common

    def test_to_condition_order_type_valid(self):
        """測試有效的 ConditionOrderType 轉換"""
        assert to_condition_order_type("Stock") == ConditionOrderType.Stock
        assert to_condition_order_type("Margin") == ConditionOrderType.Margin

    def test_to_condition_price_type_valid(self):
        """測試有效的 ConditionPriceType 轉換"""
        assert to_condition_price_type("Limit") == ConditionPriceType.Limit
        assert to_condition_price_type("Market") == ConditionPriceType.Market

    def test_to_stop_sign_valid(self):
        """測試有效的 StopSign 轉換"""
        assert to_stop_sign("Full") == StopSign.Full
        assert to_stop_sign("Partial") == StopSign.Partial
        assert to_stop_sign("UntilEnd") == StopSign.UntilEnd

    def test_to_direction_valid(self):
        """測試有效的 Direction 轉換"""
        assert to_direction("Up") == Direction.Up
        assert to_direction("Down") == Direction.Down


class TestAdvancedEnumConversions:
    """測試進階枚舉轉換函數 (未覆蓋的部分)"""

    def test_to_time_slice_order_type_valid(self):
        """測試有效的 TimeSliceOrderType 轉換"""
        assert to_time_slice_order_type("Type1") == TimeSliceOrderType.Type1
        assert to_time_slice_order_type("Type2") == TimeSliceOrderType.Type2
        assert to_time_slice_order_type("Type3") == TimeSliceOrderType.Type3

    def test_to_time_slice_order_type_invalid(self):
        """測試無效的 TimeSliceOrderType 轉換"""
        with pytest.raises(ValueError):
            to_time_slice_order_type("InvalidType")

    def test_to_condition_status_valid(self):
        """測試有效的 ConditionStatus 轉換"""
        assert to_condition_status("Type1") == ConditionStatus.Type1
        assert to_condition_status("Type5") == ConditionStatus.Type5

    def test_to_condition_status_invalid(self):
        """測試無效的 ConditionStatus 轉換"""
        with pytest.raises(ValueError):
            to_condition_status("InvalidType")

    def test_to_history_status_valid(self):
        """測試有效的 HistoryStatus 轉換"""
        assert to_history_status("Type1") == HistoryStatus.Type1
        assert to_history_status("Type2") == HistoryStatus.Type2

    def test_to_history_status_invalid(self):
        """測試無效的 HistoryStatus 轉換"""
        with pytest.raises(ValueError):
            to_history_status("InvalidType")


class TestStockTypes:
    """測試 to_stock_types 函數"""

    def test_empty_list(self):
        """測試空列表返回預設值"""
        result = to_stock_types([])
        assert result == [StockType.Stock]

    def test_valid_stock_type(self):
        """測試有效的 StockType"""
        result = to_stock_types(["Stock"])
        assert result == [StockType.Stock]

    def test_convertbond_mapping(self):
        """測試 ConvertBond 的名稱映射"""
        result = to_stock_types(["ConvertBond"])
        assert result == [StockType.CovertBond]

    def test_etf_etn_mapping(self):
        """測試 ETF_and_ETN 的名稱映射"""
        result = to_stock_types(["ETF_and_ETN"])
        assert result == [StockType.EtfAndEtn]

    def test_multiple_types(self):
        """測試多個股票類型"""
        result = to_stock_types(["Stock", "ConvertBond", "ETF_and_ETN"])
        assert len(result) == 3
        assert StockType.Stock in result
        assert StockType.CovertBond in result
        assert StockType.EtfAndEtn in result


class TestUtilityFunctions:
    """測試輔助函數"""

    def test_enum_to_string_with_name(self):
        """測試帶 name 屬性的枚舉轉字串"""
        result = enum_to_string(BSAction.Buy)
        assert result == "BSAction.Buy"

    def test_enum_to_string_without_name(self):
        """測試不帶 name 屬性的值轉字串"""

        class SimpleValue:
            def __str__(self):
                return "SimpleString"

        result = enum_to_string(SimpleValue())
        assert result == "SimpleString"

    def test_validate_enum_value_valid(self):
        """測試有效枚舉值驗證"""
        assert validate_enum_value(BSAction, "Buy") is True
        assert validate_enum_value(PriceType, "Limit") is True

    def test_validate_enum_value_invalid(self):
        """測試無效枚舉值驗證"""
        assert validate_enum_value(BSAction, "InvalidAction") is False
        assert validate_enum_value(PriceType, "InvalidPrice") is False
