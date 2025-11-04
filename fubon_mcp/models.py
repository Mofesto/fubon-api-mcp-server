"""
Pydantic models for parameter validation in Fubon API MCP Server.

This module contains all the BaseModel classes used for validating
API parameters across different MCP tools.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel

# =============================================================================
# Historical Data Models
# =============================================================================


class HistoricalCandlesArgs(BaseModel):
    symbol: str
    from_date: str
    to_date: str


# =============================================================================
# Trading Models
# =============================================================================


class PlaceOrderArgs(BaseModel):
    account: str
    symbol: str
    quantity: int
    price: float
    buy_sell: str  # 'Buy' or 'Sell'
    market_type: str = "Common"  # Market type, default "Common"
    price_type: str = "Limit"  # Price type, default "Limit"
    time_in_force: str = "ROD"  # Time in force, default "ROD"
    order_type: str = "Stock"  # Order type, default "Stock"
    user_def: Optional[str] = None  # User-defined field, optional
    is_non_blocking: bool = False  # Whether to use non-blocking mode


class CancelOrderArgs(BaseModel):
    account: str
    order_no: str


class ModifyPriceArgs(BaseModel):
    account: str
    order_no: str
    new_price: float


class ModifyQuantityArgs(BaseModel):
    account: str
    order_no: str
    new_quantity: int


class BatchPlaceOrderArgs(BaseModel):
    account: str
    orders: List[Dict]  # List of order parameter dictionaries
    max_workers: int = 10  # Maximum number of parallel workers


# =============================================================================
# Account Models
# =============================================================================


class GetAccountInfoArgs(BaseModel):
    account: str = ""  # Empty string means return all accounts


class GetInventoryArgs(BaseModel):
    account: str


class GetUnrealizedPnLArgs(BaseModel):
    account: str


class GetSettlementArgs(BaseModel):
    account: str
    days: str = "0d"  # 0d, 1d, 2d, 3d


class GetBankBalanceArgs(BaseModel):
    account: str


# =============================================================================
# Market Data Models
# =============================================================================


class GetIntradayTickersArgs(BaseModel):
    market: str  # e.g., TSE, OTC


class GetIntradayTickerArgs(BaseModel):
    symbol: str


class GetIntradayQuoteArgs(BaseModel):
    symbol: str


class GetIntradayCandlesArgs(BaseModel):
    symbol: str


class GetIntradayTradesArgs(BaseModel):
    symbol: str


class GetIntradayVolumesArgs(BaseModel):
    symbol: str


class GetSnapshotQuotesArgs(BaseModel):
    market: str


class GetSnapshotMoversArgs(BaseModel):
    market: str


class GetSnapshotActivesArgs(BaseModel):
    market: str


class GetHistoricalStatsArgs(BaseModel):
    symbol: str


class GetRealtimeQuotesArgs(BaseModel):
    symbol: str


# =============================================================================
# Order and Report Models
# =============================================================================


class GetOrderStatusArgs(BaseModel):
    account: str


class GetOrderReportsArgs(BaseModel):
    limit: int = 10  # Number of latest records to return


class GetOrderChangedReportsArgs(BaseModel):
    limit: int = 10


class GetFilledReportsArgs(BaseModel):
    limit: int = 10


class GetEventReportsArgs(BaseModel):
    limit: int = 10


class GetOrderResultsArgs(BaseModel):
    account: str
