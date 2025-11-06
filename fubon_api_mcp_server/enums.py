"""
富邦 API 枚舉類型定義和轉換工具

此模組提供富邦 API 中使用的所有枚舉類型的類型定義和安全的轉換函數，
用於改善強型別檢查和代碼安全性。
"""

from typing import Optional, Union

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

# 類型別名定義
EnumType = Union[
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
    StopSign,
    TimeInForce,
    TimeSliceOrderType,
    TradingType,
    TriggerContent,
]


def safe_enum_conversion(enum_class: type, value: str, default: Optional[EnumType] = None) -> Optional[EnumType]:
    """
    安全地將字串轉換為枚舉值

    Args:
        enum_class: 枚舉類別
        value: 要轉換的字串值
        default: 如果轉換失敗時的預設值

    Returns:
        枚舉值或預設值

    Raises:
        ValueError: 如果沒有預設值且轉換失敗
    """
    try:
        return getattr(enum_class, value)
    except AttributeError:
        if default is not None:
            return default
        raise ValueError(f"無效的枚舉值 '{value}' 對於 {enum_class.__name__}")


# 具體的枚舉轉換函數，帶有正確的類型註解


def to_bs_action(value: str) -> BSAction:
    """將字串轉換為 BSAction 枚舉"""
    return safe_enum_conversion(BSAction, value, BSAction.Buy if value not in ["Buy", "Sell"] else None)


def to_market_type(value: str) -> MarketType:
    """將字串轉換為 MarketType 枚舉"""
    return safe_enum_conversion(MarketType, value, MarketType.Common)


def to_order_type(value: str) -> OrderType:
    """將字串轉換為 OrderType 枚舉"""
    return safe_enum_conversion(OrderType, value, OrderType.Stock)


def to_price_type(value: str) -> PriceType:
    """將字串轉換為 PriceType 枚舉"""
    return safe_enum_conversion(PriceType, value, PriceType.Limit)


def to_time_in_force(value: str) -> TimeInForce:
    """將字串轉換為 TimeInForce 枚舉"""
    return safe_enum_conversion(TimeInForce, value, TimeInForce.ROD)


def to_trading_type(value: str) -> TradingType:
    """將字串轉換為 TradingType 枚舉"""
    return safe_enum_conversion(TradingType, value, TradingType.Reference)


def to_trigger_content(value: str) -> TriggerContent:
    """將字串轉換為 TriggerContent 枚舉"""
    return safe_enum_conversion(TriggerContent, value, TriggerContent.MatchedPrice)


def to_operator(value: str) -> Operator:
    """將字串轉換為 Operator 枚舉"""
    return safe_enum_conversion(Operator, value, Operator.LessThan)


def to_condition_market_type(value: str) -> ConditionMarketType:
    """將字串轉換為 ConditionMarketType 枚舉"""
    return safe_enum_conversion(ConditionMarketType, value, ConditionMarketType.Common)


def to_condition_order_type(value: str) -> ConditionOrderType:
    """將字串轉換為 ConditionOrderType 枚舉"""
    return safe_enum_conversion(ConditionOrderType, value, ConditionOrderType.Stock)


def to_condition_price_type(value: str) -> ConditionPriceType:
    """將字串轉換為 ConditionPriceType 枚舉"""
    return safe_enum_conversion(ConditionPriceType, value, ConditionPriceType.Limit)


def to_stop_sign(value: str) -> StopSign:
    """將字串轉換為 StopSign 枚舉"""
    return safe_enum_conversion(StopSign, value, StopSign.Full)


def to_direction(value: str) -> Direction:
    """將字串轉換為 Direction 枚舉"""
    return safe_enum_conversion(Direction, value, Direction.Up)


def to_time_slice_order_type(value: str) -> TimeSliceOrderType:
    """將字串轉換為 TimeSliceOrderType 枚舉"""
    return safe_enum_conversion(TimeSliceOrderType, value)


def to_condition_status(value: str) -> ConditionStatus:
    """將字串轉換為 ConditionStatus 枚舉"""
    return safe_enum_conversion(ConditionStatus, value)


def to_history_status(value: str) -> HistoryStatus:
    """將字串轉換為 HistoryStatus 枚舉"""
    return safe_enum_conversion(HistoryStatus, value)


def to_stock_types(values: list) -> list:
    """將字串列表轉換為 StockType 枚舉列表"""
    if not values:
        return [StockType.Stock]  # 預設值

    result = []
    for value in values:
        # 處理用戶文檔中的名稱映射
        if value == "ConvertBond":
            value = "CovertBond"  # 修正拼寫
        elif value == "ETF_and_ETN":
            value = "EtfAndEtn"
        # "Stock" 保持不變

        enum_value = safe_enum_conversion(StockType, value)
        if enum_value:
            result.append(enum_value)

    return result if result else [StockType.Stock]


# 枚舉值到字串的轉換函數（用於序列化）


def enum_to_string(enum_value: EnumType) -> str:
    """將枚舉值轉換為字串"""
    return enum_value.name if hasattr(enum_value, "name") else str(enum_value)


# 枚舉驗證函數


def validate_enum_value(enum_class: type, value: str) -> bool:
    """驗證字串是否為有效的枚舉值"""
    try:
        getattr(enum_class, value)
        return True
    except AttributeError:
        return False


# 枚舉文檔和說明

ENUM_DOCUMENTATION = {
    BSAction: {"Buy": "買", "Sell": "賣"},
    ConditionMarketType: {"Common": "一般盤", "Fixing": "定盤", "IntradayOdd": "盤中零股", "Odd": "盤後零股"},
    TradingType: {"Reference": "自動參考委託物件", "Scheduled": "時間"},
    TriggerContent: {
        "BidPrice": "買進價",
        "AskPrice": "賣出價",
        "MatchedPrice": "成交價",
        "TotalQuantity": "總量",
        "Time": "時間",
    },
    Operator: {
        "GreaterThanOrEqual": "大於等於",
        "LessThanOrEqual": "小於等於",
        "GreaterThan": "大於",
        "LessThan": "小於",
        "Equal": "等於",
    },
    StopSign: {"Full": "全部成交為止", "Partial": "部分成交為止", "UntilEnd": "效期結束為止"},
    TimeInForce: {
        "ROD": "當日有效(Rest of Day)",
        "FOK": "全部成交否則取消(Fill-or-Kill)",
        "IOC": "立即成交否則取消(Immediate-or-Cancel)",
    },
    ConditionPriceType: {
        "Limit": "限價",
        "BidPrice": "買進價",
        "AskPrice": "賣出價",
        "Market": "市價",
        "MatchedPrice": "成交價",
        "LimitUp": "漲停價",
        "LimitDown": "跌停價",
        "Reference": "參考價(平盤價)",
    },
    ConditionOrderType: {"Stock": "現貨", "Margin": "融資", "Short": "融券", "DayTrade": "當沖"},
    Direction: {"Up": "上漲", "Down": "下跌"},
    TimeSliceOrderType: {
        "Type1": "從開始時間，每隔幾秒送一筆，總共送N筆，每筆送M張",
        "Type2": "從開始到結束，每隔X秒送一筆，總共N張，剩餘張數加總至最後一筆",
        "Type3": "從開始到結束，每隔X秒送一筆，總共N張，剩餘張數從最後一筆往前分配",
    },
    ConditionStatus: {
        "Type1": "今日相關查詢",
        "Type2": "尚有效單",
        "Type3": "條件比對中",
        "Type4": "委託處理中",
        "Type5": "委託成功",
        "Type6": "已通知",
        "Type7": "委託失敗",
        "Type8": "已有成交",
        "Type9": "刪除成功",
        "Type10": "異常",
        "Type11": "失效",
    },
    HistoryStatus: {
        "Type1": "所有條件單 ( 不包含已刪除、失效)",
        "Type2": "選擇期間內全部成交單",
        "Type3": "選擇期間內部分成交單",
        "Type4": "選擇期間刪除單",
        "Type5": "選擇期間失效單",
        "Type6": "選擇期間內已觸發記錄",
    },
}
