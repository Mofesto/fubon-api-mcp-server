#!/usr/bin/env python3
"""
富邦證券 MCP (Model Context Protocol) 服務器

此模組實現了一個完整的富邦證券交易 API MCP 服務器，提供以下功能：
- 股票歷史數據查詢（本地快取 + API 調用）
- 即時行情數據獲取
- 股票交易下單（買賣、改價、改量、取消）
- 帳戶資訊查詢（資金餘額、庫存、損益）
- 主動回報監聽（委託、成交、事件通知）
- 批量並行下單功能

主要組件：
- MCPServer: MCP v2 服務器框架（支援 2026-07-28 協定）
- FubonSDK: 富邦證券官方 SDK
- Pydantic: 數據驗證和序列化
- Pandas: 數據處理和分析

環境變數需求：
- FUBON_USERNAME: 富邦證券帳號
- FUBON_PASSWORD: 密碼
- FUBON_PFX_PATH: PFX 憑證檔案路徑
- FUBON_PFX_PASSWORD: PFX 憑證密碼（可選）
- FUBON_API_KEY: v2.2.8 API-Key（可選，需搭配 FUBON_USERNAME 與 FUBON_PFX_PATH）
- FUBON_DATA_DIR: 本地數據儲存目錄（可選，預設為用戶應用程式支援目錄）
- FUBON_MCP_TRANSPORT: stdio（預設）、streamable-http 或 sse
- FUBON_MCP_STATELESS_HTTP: Streamable HTTP 是否使用 MCP 2026-07-28 stateless 模式

作者: MCP Server Team
版本: 1.6.0
"""

import functools
import os
import sys
import threading
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from fubon_api_mcp_server.utils import normalize_item, validate_and_get_account

# Set encoding for stdout and stderr to handle Chinese characters properly
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import logging

from dotenv import load_dotenv
from fubon_neo.sdk import Condition, ConditionDayTrade, ConditionOrder, FubonSDK
from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

# 配置模組導入
from . import config, indicators
from .account_service import AccountService
from .analysis_service import AnalysisService

# 本地模組導入
from .enums import (
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
)

# 服務類導入
from .market_data_service import MarketDataService
from .reports_service import ReportsService
from .trading_service import TradingService

# 加載環境變數配置
load_dotenv()

# =============================================================================
# 配置和全局變數
# =============================================================================

# 數據目錄配置 - 用於儲存本地快取的股票歷史數據
DEFAULT_DATA_DIR = Path.home() / "Library" / "Application Support" / "fubon-mcp" / "data"
BASE_DATA_DIR = Path(os.getenv("FUBON_DATA_DIR", DEFAULT_DATA_DIR))

# 確保數據目錄存在
BASE_DATA_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger(__name__)
logger.info(f"使用數據目錄: {BASE_DATA_DIR}")


# =============================================================================
# 環境變數中的認證資訊
# =============================================================================

username = os.getenv("FUBON_USERNAME")
password = os.getenv("FUBON_PASSWORD")
pfx_path = os.getenv("FUBON_PFX_PATH")
pfx_password = os.getenv("FUBON_PFX_PASSWORD")
api_key = os.getenv("FUBON_API_KEY")

# MCP 服務器實例
mcp = MCPServer("fubon-api-mcp-server", version="2.2.8")

# =============================================================================
# SDK 相關全局變數（在 main() 中初始化以避免導入時錯誤）
# =============================================================================

# 這些變數現在在 config.py 中定義

# =============================================================================
# 服務實例（在 main() 中初始化）
# =============================================================================

market_data_service = None
trading_service = None
account_service = None
reports_service = None
indicators_service = None

# 全域鎖定 - 避免同時重複觸發重連機制
relogin_lock = threading.Lock()


def handle_exceptions(func):
    """
    異常處理裝飾器。

    為函數添加全域異常處理，當函數執行發生例外時，
    會捕獲例外並輸出詳細的錯誤資訊到標準錯誤輸出。

    參數:
        func: 要裝飾的函數

    返回:
        wrapper: 裝飾後的函數
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exp:
            # Extract the full traceback
            tb_lines = traceback.format_exc().splitlines()

            # Find the index of the line related to the original function
            func_line_index = next((i for i, line in enumerate(tb_lines) if func.__name__ in line), -1)

            # Highlight the specific part in the traceback where the exception occurred
            relevant_tb = "\n".join(tb_lines[func_line_index:])  # Include traceback from the function name

            error_text = f"{func.__name__} exception: {exp}\nTraceback (most recent call last):\n{relevant_tb}"
            logger.exception(error_text)

            # 若要程式完全跳出，可加入下行 (P.S. jupyter 環境不適用)
            # os._exit(-1)

    return wrapper


# =============================================================================
# 主動回報回調函數
# =============================================================================


def on_order(order_data):
    """
    委託回報事件回調函數。

    當有新的委託單被建立或狀態改變時，此函數會被SDK調用。
    接收到的委託數據會被添加到全局的 latest_order_reports 列表中，
    並限制列表長度最多保留10筆記錄。

    參數:
        order_data: 委託相關的數據對象，包含委託單的詳細資訊
    """
    try:
        # 添加時間戳到數據中
        timestamped_data = {"timestamp": datetime.now().isoformat(), "data": order_data}
        server_state.latest_order_reports.append(timestamped_data)

        # 限制列表長度，最多保留10筆記錄
        if len(server_state.latest_order_reports) > 10:
            server_state.latest_order_reports.pop(0)

        logger.info(f"收到委託回報: {order_data}")
    except Exception as e:
        logger.exception(f"處理委託回報時發生錯誤: {str(e)}")


def on_order_changed(order_changed_data):
    """
    改價/改量/刪單回報事件回調函數。

    當委託單被修改（價格、數量）或刪除時，此函數會被SDK調用。
    接收到的數據會被添加到全局的 latest_order_changed_reports 列表中，
    並限制列表長度最多保留10筆記錄。

    參數:
        order_changed_data: 委託變更相關的數據對象
    """
    try:
        # 添加時間戳到數據中
        timestamped_data = {
            "timestamp": datetime.now().isoformat(),
            "data": order_changed_data,
        }
        server_state.latest_order_changed_reports.append(timestamped_data)

        # 限制列表長度，最多保留10筆記錄
        if len(server_state.latest_order_changed_reports) > 10:
            server_state.latest_order_changed_reports.pop(0)

        logger.info(f"收到改價/改量/刪單回報: {order_changed_data}")
    except Exception as e:
        logger.exception(f"處理改價/改量/刪單回報時發生錯誤: {str(e)}")


def on_filled(filled_data):
    """
    成交回報事件回調函數。

    當委託單發生成交時，此函數會被SDK調用。
    接收到的成交數據會被添加到全局的 latest_filled_reports 列表中，
    並限制列表長度最多保留10筆記錄。

    參數:
        filled_data: 成交相關的數據對象，包含成交價格、數量等資訊
    """
    try:
        # 添加時間戳到數據中
        timestamped_data = {
            "timestamp": datetime.now().isoformat(),
            "data": filled_data,
        }
        server_state.latest_filled_reports.append(timestamped_data)

        # 限制列表長度，最多保留10筆記錄
        if len(server_state.latest_filled_reports) > 10:
            server_state.latest_filled_reports.pop(0)

        logger.info(f"收到成交回報: {filled_data}")
    except Exception as e:
        logger.exception(f"處理成交回報時發生錯誤: {str(e)}")


def on_event(event_data):
    """
    事件通知回調函數。

    當SDK發生各種事件（如連接狀態變化、錯誤通知等）時，此函數會被調用。
    接收到的事件數據會被添加到全局的 latest_event_reports 列表中，
    並限制列表長度最多保留10筆記錄。

    參數:
        event_data: 事件相關的數據對象，包含事件類型和詳細資訊
    """
    try:
        # 添加時間戳到數據中
        timestamped_data = {"timestamp": datetime.now().isoformat(), "data": event_data}
        server_state.latest_event_reports.append(timestamped_data)

        # 限制列表長度，最多保留10筆記錄
        if len(server_state.latest_event_reports) > 10:
            server_state.latest_event_reports.pop(0)

        logger.info(f"收到事件通知: {event_data}")
    except Exception as e:
        logger.exception(f"處理事件通知時發生錯誤: {str(e)}")


# =============================================================================
# Pydantic 參數模型定義
# =============================================================================


class HistoricalCandlesArgs(BaseModel):
    symbol: str
    from_date: str
    to_date: str


class PlaceOrderArgs(BaseModel):
    account: str
    symbol: str
    quantity: int  # 委託數量（股）
    price: float
    buy_sell: str  # 'Buy' or 'Sell'
    market_type: str = "Common"  # 市場別，預設 "Common"
    price_type: str = "Limit"  # 價格類型，預設 "Limit"
    time_in_force: str = "ROD"  # 有效期間，預設 "ROD"
    order_type: str = "Stock"  # 委託類型，預設 "Stock"
    user_def: Optional[str] = None  # 使用者自定義欄位，可選
    is_non_blocking: bool = False  # 是否使用非阻塞模式


class CancelOrderArgs(BaseModel):
    account: str
    order_no: str


class GetAccountInfoArgs(BaseModel):
    account: Optional[str] = None


class GetInventoryArgs(BaseModel):
    account: str


class GetSettlementArgs(BaseModel):
    account: str
    range: str = Field("0d", pattern="^(0d|3d)$")  # 0d: 當日, 3d: 3日


class GetMaintenanceArgs(BaseModel):
    account: str


class GetBankBalanceArgs(BaseModel):
    account: str


class GetMarginQuotaArgs(BaseModel):
    account: str
    stock_no: str


class GetDayTradeStockInfoArgs(BaseModel):
    account: str
    stock_no: str


class QuerySymbolQuoteArgs(BaseModel):
    account: str
    symbol: str
    market_type: Optional[str] = "Common"


class QuerySymbolSnapshotArgs(BaseModel):
    account: str
    market_type: Optional[str] = "Common"
    stock_type: Optional[List[str]] = ["Stock"]


class GetIntradayTickersArgs(BaseModel):
    market: str  # 市場別，可選 TSE 上市；OTC 上櫃；ESB 興櫃一般板；TIB 臺灣創新板；PSB 興櫃戰略新板
    type: Optional[str] = None  # 類型，可選 EQUITY 股票；INDEX 指數；WARRANT 權證；ODDLOT 盤中零股
    exchange: Optional[str] = None  # 交易所，可選 TWSE 臺灣證券交易所；TPEx 證券櫃檯買賣中心
    industry: Optional[str] = None  # 產業別
    isNormal: Optional[bool] = None  # 查詢正常股票
    isAttention: Optional[bool] = None  # 查詢注意股票
    isDisposition: Optional[bool] = None  # 查詢處置股票
    isHalted: Optional[bool] = None  # 查詢暫停交易股票


class GetIntradayTickerArgs(BaseModel):
    symbol: str
    type: Optional[str] = None  # 類型，可選 oddlot 盤中零股


class GetIntradayQuoteArgs(BaseModel):
    symbol: str
    type: Optional[str] = None  # 類型，可選 oddlot 盤中零股


class GetIntradayCandlesArgs(BaseModel):
    symbol: str


class GetIntradayTradesArgs(BaseModel):
    symbol: str
    type: Optional[str] = None  # Ticker 類型，可選 oddlot 盤中零股
    offset: Optional[int] = None  # 偏移量
    limit: Optional[int] = None  # 限制量


class GetIntradayVolumesArgs(BaseModel):
    symbol: str


class GetSnapshotQuotesArgs(BaseModel):
    market: str
    type: Optional[str] = None  # 標的類型，可選 ALLBUT0999 或 COMMONSTOCK


class GetSnapshotMoversArgs(BaseModel):
    market: str
    direction: str = "up"  # 上漲／下跌，可選 up 上漲；down 下跌
    change: str = "percent"  # 漲跌／漲跌幅，可選 percent 漲跌幅；value 漲跌
    gt: Optional[float] = None  # 篩選大於漲跌／漲跌幅的股票
    gte: Optional[float] = None  # 篩選大於或等於漲跌／漲跌幅的股票
    lt: Optional[float] = None  # 篩選小於漲跌／漲跌幅的股票
    lte: Optional[float] = None  # 篩選小於或等於漲跌／漲跌幅的股票
    eq: Optional[float] = None  # 篩選等於漲跌／漲跌幅的股票
    type: Optional[str] = None  # 標的類型，可選 ALLBUT0999 或 COMMONSTOCK


class GetSnapshotActivesArgs(BaseModel):
    market: str
    trade: str = "volume"  # 成交量／成交值，可選 volume 成交量；value 成交值
    type: Optional[str] = None  # 標的類型，可選 ALLBUT0999 或 COMMONSTOCK


class GetHistoricalStatsArgs(BaseModel):
    symbol: str


class GetIntradayProductsArgs(BaseModel):
    type: Optional[str] = None  # 類型，可選 FUTURE 期貨；OPTION 選擇權
    exchange: Optional[str] = None  # 交易所，可選 TAIFEX 臺灣期貨交易所
    session: Optional[str] = None  # 交易時段，可選 REGULAR 一般交易 或 AFTERHOURS 盤後交易
    contractType: Optional[str] = None  # 契約類別，可選 I 指數類；R 利率類；B 債券類；C 商品類；S 股票類；E 匯率類
    status: Optional[str] = None  # 契約狀態，可選 N 正常；P 暫停交易；U 即將上市


class GetIntradayFutOptTickersArgs(BaseModel):
    type: str  # 類型，可選 FUTURE 期貨；OPTION 選擇權
    exchange: Optional[str] = None  # 交易所，可選 TAIFEX 臺灣期貨交易所
    session: Optional[str] = None  # 交易時段，可選 REGULAR 一般交易 或 AFTERHOURS 盤後交易
    product: Optional[str] = None  # 產品代碼
    contractType: Optional[str] = None  # 契約類別，可選 I 指數類；R 利率類；B 債券類；C 商品類；S 股票類；E 匯率類


class GetIntradayFutOptTickerArgs(BaseModel):
    symbol: str  # 商品代碼
    session: Optional[str] = None  # 交易時段，可選 REGULAR 一般交易 或 AFTERHOURS 盤後交易


class GetIntradayFutOptQuoteArgs(BaseModel):
    symbol: str  # 期權代碼
    session: Optional[str] = None  # 交易時段，可選 afterhours 盤後交易


class GetIntradayFutOptCandlesArgs(BaseModel):
    symbol: str  # 期權代碼
    session: Optional[str] = None  # 交易時段，可選 afterhours 盤後交易
    timeframe: Optional[str] = None  # K線週期，可選 1m, 5m, 15m, 30m, 1h, 1d


class GetIntradayFutOptTradesArgs(BaseModel):
    symbol: str  # 期權代碼
    session: Optional[str] = None  # 交易時段，可選 afterhours 盤後交易
    offset: Optional[int] = None  # 偏移量
    limit: Optional[int] = None  # 限制量


class GetIntradayFutOptVolumesArgs(BaseModel):
    symbol: str  # 期權代碼
    session: Optional[str] = None  # 交易時段，可選 afterhours 盤後交易


class GetRealtimeQuotesArgs(BaseModel):
    symbol: str


class GetOrderStatusArgs(BaseModel):
    account: str


class GetOrderReportsArgs(BaseModel):
    limit: int = 10  # 返回最新的幾筆記錄


class GetOrderChangedReportsArgs(BaseModel):
    limit: int = 10


class GetFilledReportsArgs(BaseModel):
    limit: int = 10


class GetEventReportsArgs(BaseModel):
    limit: int = 10


class GetOrderResultsArgs(BaseModel):
    account: str


class GetOrderResultsDetailArgs(BaseModel):
    account: str


class ModifyPriceArgs(BaseModel):
    account: str
    order_no: str
    new_price: float = Field(gt=0)  # 價格必須大於0


class ModifyQuantityArgs(BaseModel):
    account: str
    order_no: str
    new_quantity: int  # 新數量（股）


class BatchPlaceOrderArgs(BaseModel):
    account: str
    orders: List[Dict]  # 每筆訂單的參數字典
    max_workers: int = 10  # 最大並行數量


class GetTrailOrderArgs(BaseModel):
    """有效移動鎖利查詢參數"""

    account: str


class GetTrailHistoryArgs(BaseModel):
    """歷史移動鎖利查詢參數"""

    account: str
    start_date: str
    end_date: str


class TimeSliceSplitArgs(BaseModel):
    """分時分量拆單設定參數 (SplitDescription)"""

    method: str  # TimeSliceOrderType 成員名稱，例如 Type1/Type2/Type3
    interval: int  # 間隔秒數 (>0)
    single_quantity: int  # 每次委託股數（必須為1000的倍數，>0）
    total_quantity: Optional[int] = None  # 總委託股數（必須為1000的倍數，選填）
    start_time: str  # 開始時間，格式如 '083000'
    end_time: Optional[str] = None  # 結束時間，Type2/Type3 必填

    # 支援更靈活的輸入格式
    split_type: Optional[str] = None  # 向後兼容字段
    split_count: Optional[int] = None  # 總拆單次數，用於計算 total_quantity
    split_unit: Optional[int] = None  # 每單位數量（通常等於 single_quantity）

    def model_post_init(self, __context):
        # 基本檢核
        if self.interval is None or self.interval <= 0:
            raise ValueError("interval 必須為正整數")
        if self.single_quantity is None or self.single_quantity <= 0:
            raise ValueError("single_quantity 必須為正整數")

        # 驗證股數必須為1000的倍數
        if self.single_quantity % 1000 != 0:
            raise ValueError(f"single_quantity 必須為1000的倍數（張數），輸入值 {self.single_quantity} 股無效")

        # 如果提供了 split_count，自動計算 total_quantity
        if self.split_count is not None and self.split_count > 0:
            if self.total_quantity is None:
                self.total_quantity = self.split_count * self.single_quantity
            elif self.total_quantity != self.split_count * self.single_quantity:
                raise ValueError(
                    f"total_quantity ({self.total_quantity}) 與 split_count * single_quantity ({self.split_count * self.single_quantity}) 不一致"
                )

        if self.total_quantity is not None and self.total_quantity <= self.single_quantity:
            raise ValueError("total_quantity 必須大於 single_quantity")

        # 驗證總股數也必須為1000的倍數
        if self.total_quantity is not None and self.total_quantity % 1000 != 0:
            raise ValueError(f"total_quantity 必須為1000的倍數（張數），輸入值 {self.total_quantity} 股無效")

        # 針對 method 類型的檢核
        try:
            from fubon_neo.constant import TimeSliceOrderType as _TS

            # 如果用戶傳入 "TimeSlice"，根據參數自動推斷類型
            if self.method == "TimeSlice":
                if self.end_time:
                    self.method = "Type2"  # 有結束時間，使用 Type2
                else:
                    self.method = "Type1"  # 無結束時間，使用 Type1

            m = getattr(_TS, self.method)
        except Exception:
            raise ValueError("method 無效，必須是 TimeSliceOrderType 的成員名稱 (Type1/Type2/Type3) 或 'TimeSlice' (自動推斷)")


# =============================================================================
# 技術指標與訊號 參數模型
# =============================================================================


class CalculateBollingerBandsArgs(BaseModel):
    symbol: str
    period: int = 20
    stddev: float = 2.0
    from_date: Optional[str] = None
    to_date: Optional[str] = None


class CalculateRSIArgs(BaseModel):
    symbol: str
    period: int = 14
    from_date: Optional[str] = None
    to_date: Optional[str] = None


class CalculateMACDArgs(BaseModel):
    symbol: str
    fast: int = 12
    slow: int = 26
    signal: int = 9
    from_date: Optional[str] = None
    to_date: Optional[str] = None


class CalculateKDArgs(BaseModel):
    symbol: str
    period: int = 9
    smooth_k: int = 3
    smooth_d: int = 3
    from_date: Optional[str] = None
    to_date: Optional[str] = None


class GetTradingSignalsArgs(BaseModel):
    symbol: str
    from_date: Optional[str] = None
    to_date: Optional[str] = None


# =============================================================================
# 即時市場數據訂閱參數模型
# =============================================================================


# =============================================================================
# 技術指標/交易訊號工具函式


# =============================================================================
# MCP Prompts - 提供智慧型交易分析和建議
# =============================================================================


@mcp.prompt()
def trading_analysis(symbol: str) -> str:
    """提供股票技術分析和交易建議

    這個提示會整合多項技術指標，為指定股票提供全面的技術分析和交易建議。
    包含布林通道、RSI、MACD、KD指標的綜合分析，以及市場趨勢判斷。

    Args:
        symbol: 股票代碼，例如 '2330' 或 '0050'

    Returns:
        詳細的技術分析報告，包含：
        - 當前市場趨勢分析
        - 技術指標綜合評分
        - 買賣建議和風險提示
        - 建議的進出場策略
    """
    return f"""請為股票代碼 {symbol} 提供全面的技術分析和交易建議：

1. **市場概況分析**
   - 使用 get_market_overview 資源查看整體市場狀況
   - 分析台股指數走勢和大盤氛圍

2. **技術指標分析**
   - 使用 get_trading_signals 工具獲取 {symbol} 的技術指標數據
   - 分析布林通道、RSI、MACD、KD等指標
   - 評估多頭 vs 空頭訊號強度

3. **價格走勢分析**
   - 使用 historical_candles 工具獲取 {symbol} 的歷史數據
   - 分析價格趨勢、支撐阻力位
   - 評估成交量配合度

4. **交易建議**
   - 根據綜合分析提供買進/賣出/持有建議
   - 建議適當的停損停利價位
   - 評估風險等級和成功機率

5. **投資策略建議**
   - 根據持倉比例建議投資金額
   - 提供分散風險的建議
   - 建議觀察時間週期

請提供客觀、數據導向的分析結論。"""


@mcp.prompt()
def risk_assessment(account: str) -> str:
    """提供帳戶風險評估和投資組合優化建議

    這個提示會分析帳戶的整體風險狀況，包含投資組合分散度、
    損益狀況、資金使用效率等，為投資者提供風險管理和優化建議。

    Args:
        account: 帳戶號碼

    Returns:
        全面的風險評估報告，包含：
        - 投資組合風險等級評估
        - 資金配置和分散度分析
        - 損益狀況和績效評估
        - 風險管理建議和優化策略
    """
    return f"""請為帳戶 {account} 提供全面的風險評估和投資組合優化建議：

1. **帳戶整體狀況分析**
   - 使用 get_account_summary 資源查看帳戶基本資訊
   - 分析資金餘額和可用資金狀況
   - 評估帳戶健康度指標

2. **投資組合風險分析**
   - 使用 get_portfolio_summary 資源分析持倉結構
   - 評估投資組合分散度（行業、個股集中度）
   - 分析單一股權重和風險暴露

3. **損益和績效評估**
   - 使用 get_unrealized_pnl 工具查看未實現損益
   - 使用 get_realized_pnl_summary 工具分析已實現損益
   - 計算投資報酬率和風險調整後報酬

4. **資金使用效率分析**
   - 使用 get_bank_balance 工具查看資金使用狀況
   - 分析融資融券使用比例
   - 評估槓桿風險等級

5. **風險管理建議**
   - 根據分析結果提供風險等級評估（低/中/高風險）
   - 建議投資組合再平衡策略
   - 提供風險控制措施和停損機制建議

6. **優化策略建議**
   - 建議資產配置調整方向
   - 提供分散投資的具體建議
   - 制定長短期投資策略框架

請基於數據提供客觀的風險評估和具體可行的優化建議。"""


@mcp.prompt()
def market_opportunity_scanner() -> str:
    """掃描市場投資機會和熱門標的

    這個提示會掃描市場上的潛在投資機會，分析熱門標的和市場趨勢，
    幫助投資者發現被低估或具有成長潛力的投資機會。

    Returns:
        市場機會掃描報告，包含：
        - 市場熱點分析
        - 潛在投資機會標的
        - 行業趨勢分析
        - 投資機會評估和建議
    """
    return """請掃描當前市場的投資機會和熱門標的：

1. **市場整體分析**
   - 使用 get_market_overview 資源了解大盤狀況
   - 分析上漲/下跌家數比例
   - 評估市場熱度和投資氣氛

2. **熱門標的發掘**
   - 使用 get_snapshot_actives 工具找出成交量最大的股票
   - 使用 get_snapshot_movers 工具找出漲跌幅最大的股票
   - 分析成交量和價格變動的關聯性

3. **行業趨勢分析**
   - 分析不同行業的表現差異
   - 找出領漲和落後行業
   - 評估行業輪動機會

4. **投資機會評估**
   - 篩選出具有投資價值的標的
   - 分析基本面和技術面指標
   - 評估投資風險和報酬潛力

5. **投資建議**
   - 提供具體的投資機會建議
   - 說明進場時機和持有策略
   - 提醒相關風險和注意事項

請提供數據導向的市場分析和具體的投資機會建議。"""


@mcp.prompt()
def portfolio_rebalancing(account: str) -> str:
    """提供投資組合再平衡建議

    這個提示會分析帳戶的投資組合是否需要再平衡，根據風險偏好和投資目標
    提供具體的調整建議，幫助維持最佳的資產配置。

    Args:
        account: 帳戶號碼

    Returns:
        投資組合再平衡建議報告，包含：
        - 當前組合分析
        - 目標配置建議
        - 具體調整方案
        - 執行時機建議
    """
    return f"""請為帳戶 {account} 的投資組合提供再平衡建議：

1. **當前組合分析**
   - 使用 get_portfolio_summary 資源分析現有持倉
   - 計算各股票的權重比例
   - 評估組合分散度和風險集中度

2. **目標配置制定**
   - 根據風險偏好設定目標配置比例
   - 考慮行業、規模、成長性等分散原則
   - 設定個股最大持股比例限制

3. **偏差分析**
   - 比較當前配置與目標配置的差異
   - 找出需要調整的部位
   - 評估調整的緊急程度

4. **再平衡策略**
   - 提供具體的買賣調整建議
   - 建議分批執行或一次性調整
   - 考慮交易成本和稅務影響

5. **執行建議**
   - 建議最佳的執行時機
   - 提供風險控制措施
   - 設定後續追蹤和再平衡週期

請提供具體、可操作的再平衡建議。"""


@mcp.prompt()
def trading_strategy_builder(symbol: str, strategy_type: str = "trend_following") -> str:
    """建立客製化交易策略

    這個提示會根據指定的股票和策略類型，建立適合的交易策略框架。
    支援趨勢跟隨、均線策略、突破策略等多種策略類型。

    Args:
        symbol: 股票代碼
        strategy_type: 策略類型，可選 "trend_following", "mean_reversion", "breakout", "swing"

    Returns:
        客製化交易策略建構指南，包含：
        - 策略原理說明
        - 具體執行規則
        - 風險管理機制
        - 績效評估方法
    """
    strategy_descriptions = {
        "trend_following": "趨勢跟隨策略 - 順應市場主流方向交易",
        "mean_reversion": "均值回歸策略 - 利用價格偏離均值的回歸特性",
        "breakout": "突破策略 - 在價格突破關鍵價位時進場",
        "swing": "波段策略 - 捕捉中短線價格波段",
    }

    strategy_desc = strategy_descriptions.get(strategy_type, "綜合策略")

    return f"""請為股票 {symbol} 建立{strategy_desc}的交易策略：

1. **策略原理說明**
   - 解釋{strategy_type}策略的核心邏輯
   - 分析適用於{symbol}的理由
   - 說明策略的優缺點

2. **技術指標選用**
   - 使用 get_trading_signals 工具分析{symbol}的技術指標
   - 選擇適合{strategy_type}策略的指標組合
   - 設定指標參數和權重

3. **進出場規則**
   - 定義具體的買進訊號條件
   - 定義具體的賣出訊號條件
   - 設定過濾條件避免假訊號

4. **風險管理**
   - 設定停損停利機制
   - 定義單筆交易的最大損失比例
   - 設定總資金使用比例

5. **策略測試與優化**
   - 使用歷史數據回測策略績效
   - 分析勝率、獲利因子、最大回檔
   - 根據回測結果優化參數

6. **執行指南**
   - 提供實際交易時的執行步驟
   - 設定觀察清單和監控頻率
   - 說明策略調整時機

請提供完整、可執行的交易策略框架。"""


@mcp.prompt()
def performance_analytics(account: str, period: str = "1M") -> str:
    """以富邦正式成交、目前損益和指數行情產生損益貢獻提示。"""
    return f"""請使用 calculate_performance_attribution 分析帳戶 {account}，期間為 {period}、基準為 IX0001。

只根據工具回傳的正式成交現金流、目前未實現損益與基準價格報酬整理結果。若工具回傳
insufficient_data，請直接說明缺少的成交、持倉或行情，不得補入報酬率。富邦 API 未提供期間
起始淨值與完整入出金歷史，因此不得計算帳戶總報酬、超額報酬、Sharpe、Sortino 或 Brinson 歸因。"""


@mcp.prompt()
def advanced_risk_management(account: str) -> str:
    """使用正式持倉與行情產生 VaR/CVaR 和明確情境分析提示。"""
    return f"""請為帳戶 {account} 執行唯讀風險分析：

1. 呼叫 calculate_portfolio_var，分別整理歷史法與參數法 VaR/CVaR、共同觀測期間及資料日期。
2. 只有在使用者已明確提供價格衝擊時才呼叫 run_portfolio_stress_test；不得自行假設利率、匯率、
   Beta、流動性或產業敏感度。
3. 空倉、過期行情或共同觀測不足時，完整保留 insufficient_data，不得以預設波動率補值。
4. 這是決策支援，不得呼叫任何下單、改單或刪單工具。"""


@mcp.prompt()
def portfolio_optimization(account: str, objective: str = "max_sharpe") -> str:
    """使用富邦歷史報酬與共變異矩陣產生長倉配置提示。"""
    return f"""請呼叫 optimize_portfolio_allocation 分析帳戶 {account}，optimization_method={objective}。

只解讀工具回傳的正式歷史報酬、共變異矩陣、限制條件與 SciPy 求解結果。清楚列出 lookback、
risk_free_rate、max_weight 和資料涵蓋期間。不得加入 Black-Litterman、基本面預測、交易成本、
主觀市場觀點或保證改善幅度；也不得自動執行再平衡交易。"""


@mcp.prompt()
def market_sentiment_analysis(symbols: str = "IX0001") -> str:
    """使用明確標的的正式技術與成交量資料產生市場狀態提示。"""
    return f"""請把逗號分隔的標的 {symbols} 正規化為 symbols 陣列，呼叫 generate_market_sentiment_index，
index_components 僅使用 technical 與 volume。逐一列出標的資料日期、觀測筆數與分數，再整理整體結果。

這不是新聞、社群、法人或選擇權情緒，也不是獲利機率。工具回傳 insufficient_data 時不得給方向性建議，
全程不得呼叫任何交易寫入工具。"""


@mcp.prompt()
def algorithmic_strategy_builder(symbol: str, strategy_type: str = "momentum") -> str:
    """建立演算法交易策略（量化策略開發）

    這個提示會協助建立量化交易策略，包含動量策略、均值回歸、
    統計套利等，使用歷史數據進行回測和優化。

    Args:
        symbol: 股票代碼
        strategy_type: 策略類型，可選 "momentum", "mean_reversion", "pairs_trading", "statistical_arbitrage"

    Returns:
        量化策略建構指南，包含：
        - 策略邏輯和參數設定
        - 歷史回測結果分析
        - 風險指標評估
        - 唯讀研究限制
    """
    strategy_descriptions = {
        "momentum": "動量策略 - 追蹤市場趨勢",
        "mean_reversion": "均值回歸策略 - 利用價格偏離",
        "pairs_trading": "配對交易策略 - 統計套利",
        "statistical_arbitrage": "統計套利策略 - 多資產套利",
    }

    strategy_desc = strategy_descriptions.get(strategy_type, "量化策略")

    return f"""請為{symbol}建立{strategy_desc}的量化交易策略：

1. **策略原理與假設**
   - 解釋{strategy_type}策略的理論基礎
   - 分析適用於{symbol}的條件
   - 設定策略的基本假設和限制

2. **數據準備和特徵工程**
   - 使用 historical_candles 工具獲取歷史數據
   - 設計技術指標和特徵變數
   - 處理數據缺失和異常值
   - 設定觀察窗口和滾動計算

3. **策略邏輯設計**
   - 定義進出場條件和規則
   - 設定策略參數（持有期、止損點等）
   - 設計過濾條件避免假訊號
   - 考慮交易成本和滑價

4. **歷史回測與評估**
   - 設定回測期間和初始資金
   - 計算策略的年化報酬率
   - 分析最大回檔和夏普比率
   - 評估勝率和獲利因子

5. **風險管理整合**
   - 設定動態止損機制
   - 設計倉位大小管理
   - 考慮市場波動率調整
   - 設定風險預算控制

6. **參數優化與穩健性測試**
   - 使用網格搜索優化參數
   - 進行步進式前瞻分析
   - 測試不同市場環境下的表現
   - 評估策略的穩健性

7. **資料與驗證限制**
   - 列出富邦歷史行情的來源、期間與觀測筆數
   - 將訓練區間與樣本外測試區間分開
   - 未實際執行的回測不得提供績效數字
   - 不得呼叫下單、改單或刪單工具

請提供可重現的唯讀研究框架；資料不足時回報 insufficient_data，不得虛構回測結果。"""


@mcp.prompt()
def futures_spread_analyzer(near_symbol: str, far_symbol: str, lookback_days: int = 252) -> str:
    """使用明確指定的富邦期貨合約產生跨月價差提示。"""
    return f"""請呼叫 detect_arbitrage_opportunities，參數如下：
- arbitrage_types: ["futures_calendar"]
- futures_pairs: [{{"near_symbol": "{near_symbol}", "far_symbol": "{far_symbol}"}}]
- lookback_days: {lookback_days}

請只解讀正式行情得到的近遠月價格、價差、歷史均值、標準差、Z-score、觀測數與資料日期。
Z-score 超過門檻只代表統計偏離，不是保證獲利、可成交套利或下單指示。"""


@mcp.prompt()
def volatility_trading_advisor(symbol: str) -> str:
    """使用富邦正式歷史 K 線產生實現波動率研究提示。"""
    return f"""請只使用 historical_candles、analyze_stock 或其他富邦正式行情工具分析 {symbol}：

1. 根據實際日報酬計算不同窗口的年化實現波動率，並列出期間與資料日期。
2. 整理 ATR、布林通道寬度及其歷史分位數；資料不足時回報 insufficient_data。
3. 不得聲稱已取得 VIX、隱含波動率、波動率微笑或 Greeks，因富邦目前資料介面未提供這些欄位。
4. 不得把歷史波動率解讀為獲利機率，也不得呼叫任何交易寫入工具。"""


# =============================================================================
# 狀態管理 - 單例模式實現
# =============================================================================


class MCPServerState:
    """MCP服務器狀態管理單例類"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.sdk = None
            self.accounts = None
            self.reststock = None
            self.restfutopt = None
            self._resource_cache = {}
            self._cache_ttl = 300  # 5分鐘預設TTL
            self._last_cache_cleanup = datetime.now()

            # Phase 2: 訂閱管理
            self._market_subscriptions = {}  # symbol -> subscription_info
            self._active_streams = {}  # stream_id -> stream_info
            self._event_listeners = {}  # event_type -> listeners
            self._realtime_data_buffer = {}  # symbol -> latest_data
            self._stream_callbacks = {}  # stream_id -> callback_function
            self._websocket_clients = {}  # data_type -> websocket_client

            # 主動回報數據存儲（全局變數，線程安全）
            # 這些變數由 SDK 回調函數使用，用於存儲主動回報數據
            self.latest_order_reports = []  # 最新的委託回報（最多保留10筆）
            self.latest_order_changed_reports = []  # 最新的改價/改量/刪單回報（最多保留10筆）
            self.latest_filled_reports = []  # 最新的成交回報（最多保留10筆）
            self.latest_event_reports = []  # 最新的事件通知回報（最多保留10筆）

            MCPServerState._initialized = True

    def initialize_sdk(
        self,
        username: str,
        password: str,
        pfx_path: str,
        pfx_password: str = "",
        api_key: Optional[str] = None,
    ):
        """初始化SDK"""
        try:
            logger.info("正在初始化富邦證券SDK...")
            self.sdk = FubonSDK()
            if api_key:
                if not username or not pfx_path:
                    raise ValueError("API-Key 登入需要 FUBON_USERNAME、FUBON_API_KEY 與 FUBON_PFX_PATH")
                self.accounts = self.sdk.apikey_login(username, api_key, pfx_path, pfx_password)
            else:
                self.accounts = self.sdk.login(username, password, pfx_path, pfx_password)
            self.sdk.init_realtime()
            self.reststock = self.sdk.marketdata.rest_client.stock
            self.restfutopt = self.sdk.marketdata.rest_client.futopt

            if not self.accounts or not hasattr(self.accounts, "is_success") or not self.accounts.is_success:
                raise ValueError("登入失敗，請檢查憑證是否正確")

            # 設定主動回報事件回調函數
            self.sdk.set_on_order(on_order)
            self.sdk.set_on_order_changed(on_order_changed)
            self.sdk.set_on_filled(on_filled)
            self.sdk.set_on_event(on_event)

            logger.info("富邦證券SDK初始化成功")
            return True
        except Exception as e:
            logger.exception(f"SDK初始化失敗: {str(e)}")
            return False

    def clear_cache(self):
        """Clear cached MCP resource data during logout or re-login."""
        self._resource_cache.clear()
        self._last_cache_cleanup = datetime.now()

    def logout(self):
        """登出並清理狀態"""
        try:
            if self.sdk:
                result = self.sdk.logout()
                if result:
                    logger.info("已成功登出")
                else:
                    logger.warning("登出失敗")
        except Exception as e:
            logger.exception(f"登出時發生錯誤: {str(e)}")
        finally:
            # 清理狀態
            self.sdk = None
            self.accounts = None
            self.reststock = None
            self.restfutopt = None
            self.clear_cache()

            # Phase 2: 清理訂閱和 WebSocket 連線
            # 斷開所有 WebSocket 連線
            for ws_key, ws_info in self._websocket_clients.items():
                try:
                    ws_info["client"].disconnect()
                except Exception:
                    pass  # 忽略斷開連線的錯誤
            self._websocket_clients.clear()

            self._market_subscriptions.clear()
            self._active_streams.clear()
            self._event_listeners.clear()
            self._realtime_data_buffer.clear()
            self._stream_callbacks.clear()

            # 清理主動回報數據
            self.latest_order_reports.clear()
            self.latest_order_changed_reports.clear()
            self.latest_filled_reports.clear()
            self.latest_event_reports.clear()


# 全域狀態管理器實例
server_state = MCPServerState()


def _env_bool(name: str, default: bool) -> bool:
    """Read a strict boolean environment variable with a safe default."""
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} 必須是 true/false（也支援 1/0、yes/no、on/off）")


def run_mcp_server() -> None:
    """Run MCP v2 using the configured transport.

    Stdio remains the default for desktop MCP hosts. Streamable HTTP opts into
    the 2026-07-28 stateless request model by default; each request is handled
    by the official MCP v2 server without relying on a session id or sticky
    routing. SSE remains available for legacy clients.
    """
    transport = os.getenv("FUBON_MCP_TRANSPORT", "stdio").strip().lower()
    if transport == "stdio":
        mcp.run("stdio")
        return

    host = os.getenv("FUBON_MCP_HOST", "127.0.0.1").strip()
    port_text = os.getenv("FUBON_MCP_PORT", "8000").strip()
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ValueError("FUBON_MCP_PORT 必須是整數") from exc
    if not 1 <= port <= 65535:
        raise ValueError("FUBON_MCP_PORT 必須介於 1 到 65535")

    if transport == "streamable-http":
        mcp.run(
            "streamable-http",
            host=host,
            port=port,
            streamable_http_path=os.getenv("FUBON_MCP_HTTP_PATH", "/mcp").strip() or "/mcp",
            json_response=_env_bool("FUBON_MCP_JSON_RESPONSE", False),
            stateless_http=_env_bool("FUBON_MCP_STATELESS_HTTP", True),
        )
        return

    if transport == "sse":
        mcp.run(
            "sse",
            host=host,
            port=port,
            sse_path=os.getenv("FUBON_MCP_SSE_PATH", "/sse").strip() or "/sse",
            message_path=os.getenv("FUBON_MCP_MESSAGE_PATH", "/messages/").strip() or "/messages/",
        )
        return

    raise ValueError("FUBON_MCP_TRANSPORT 必須是 stdio、streamable-http 或 sse")


def main():
    """
    應用程式主入口點函數。

    負責初始化富邦證券 SDK、進行身份認證、設定事件回調，
    並啟動 MCP 服務器。這個函數會在程式啟動時執行所有必要的初始化工作。

    初始化流程:
    1. 檢查必要的環境變數（傳統帳密或 v2.2.8 API-Key 登入資料）
    2. 初始化富邦 SDK 實例
    3. 登入到富邦證券系統
    4. 初始化即時資料連線
    5. 設定所有主動回報事件回調函數
    6. 啟動 MCP 服務器

    環境變數需求:
    - FUBON_USERNAME: 富邦證券帳號
    - 傳統登入：FUBON_PASSWORD、FUBON_PFX_PATH
    - API-Key 登入：FUBON_API_KEY、FUBON_PFX_PATH（網頁匯出憑證）
    - FUBON_PFX_PASSWORD: PFX 憑證密碼（可選）

    如果初始化失敗，程式會輸出錯誤訊息並以錯誤代碼退出。
    """
    try:
        # API-Key 登入仍需 personal_id 與網頁匯出的 PFX 憑證；沒有 API-Key
        # 時維持既有的帳號密碼登入流程。
        if api_key:
            if not all([username, api_key, pfx_path]):
                raise ValueError("FUBON_USERNAME, FUBON_API_KEY, and FUBON_PFX_PATH environment variables are required")
        elif not all([username, password, pfx_path]):
            raise ValueError("FUBON_USERNAME, FUBON_PASSWORD, and FUBON_PFX_PATH environment variables are required")

        # 使用新的狀態管理系統初始化SDK
        success = server_state.initialize_sdk(username, password, pfx_path, pfx_password or "", api_key=api_key)
        if not success:
            raise ValueError("登入失敗，請檢查憑證是否正確")

        # 設置全局變數以保持向後兼容性
        config.sdk = server_state.sdk
        config.accounts = server_state.accounts
        config.reststock = server_state.reststock
        config.restfutopt = server_state.restfutopt

        # 初始化服務實例
        global market_data_service, trading_service, account_service, reports_service, indicators_service
        market_data_service = MarketDataService(mcp, BASE_DATA_DIR, config.reststock, config.restfutopt, config.sdk)
        trading_service = TradingService(
            mcp,
            config.sdk,
            config.accounts,
            BASE_DATA_DIR,
            config.reststock,
            config.restfutopt,
        )
        account_service = AccountService(mcp, config.sdk, config.accounts)
        reports_service = ReportsService(mcp, config.sdk, config.accounts)
        indicators_service = AnalysisService(mcp, config.sdk, config.accounts, config.reststock, config.restfutopt)

        logger.info("富邦證券MCP server運行中...")
        run_mcp_server()
    except KeyboardInterrupt:
        logger.info("收到中斷信號，正在優雅關閉...")
        server_state.logout()
        sys.exit(0)
    except Exception as e:
        logger.exception(f"啟動伺服器時發生錯誤: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
