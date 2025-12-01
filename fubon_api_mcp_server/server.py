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
- FastMCP: MCP 服務器框架
- FubonSDK: 富邦證券官方 SDK
- Pydantic: 數據驗證和序列化
- Pandas: 數據處理和分析

環境變數需求：
- FUBON_USERNAME: 富邦證券帳號
- FUBON_PASSWORD: 密碼
- FUBON_PFX_PATH: PFX 憑證檔案路徑
- FUBON_PFX_PASSWORD: PFX 憑證密碼（可選）
- FUBON_DATA_DIR: 本地數據儲存目錄（可選，預設為用戶應用程式支援目錄）

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
from mcp.server.fastmcp import FastMCP
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

# MCP 服務器實例
mcp = FastMCP("fubon-api-mcp-server")

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
    """提供投資組合績效分析和歸因分析

    這個提示會進行深入的投資組合績效分析，包含風險調整後報酬、
    績效歸因分析、基準比較等，提供專業級的投資績效評估。

    Args:
        account: 帳戶號碼
        period: 分析期間，可選 "1W", "1M", "3M", "6M", "1Y", "ALL"，預設 "1M"

    Returns:
        全面的績效分析報告，包含：
        - 絕對報酬和風險指標
        - 風險調整後績效指標（夏普比率、索提諾比率等）
        - 績效歸因分析（股票選擇、時機選擇、資產配置）
        - 基準比較分析
        - 績效歸因和改進建議
    """
    period_descriptions = {
        "1W": "過去一周",
        "1M": "過去一個月",
        "3M": "過去三個月",
        "6M": "過去六個月",
        "1Y": "過去一年",
        "ALL": "全部期間",
    }

    period_desc = period_descriptions.get(period, "指定期間")

    return f"""請為帳戶 {account} 提供{period_desc}的全面投資組合績效分析：

1. **絕對報酬分析**
   - 使用 get_realized_pnl_summary 工具獲取已實現損益
   - 使用 get_unrealized_pnl 工具獲取未實現損益
   - 計算期間總報酬率和年化報酬率
   - 分析月度/季度報酬波動

2. **風險指標計算**
   - 計算投資組合的波動率（標準差）
   - 計算最大回檔和回檔持續時間
   - 分析下檔波動率（索提諾比率）
   - 評估風險等級和承受能力

3. **風險調整後績效**
   - 計算夏普比率（Sharpe Ratio）
   - 計算資訊比率（Information Ratio）
   - 計算詹森指數（Jensen's Alpha）
   - 與市場基準比較超額報酬

4. **績效歸因分析**
   - 資產配置效果分析（配置報酬 vs 選擇報酬）
   - 個股選擇貢獻度分析
   - 行業配置和選擇效果
   - 時機選擇能力評估

5. **基準比較分析**
   - 與大盤指數比較（加權指數、櫃買指數）
   - 與相關投資組合基準比較
   - 相對績效分析和排名
   - 超額報酬來源分析

6. **績效評估與建議**
   - 整體績效評分（1-10分）
   - 優勢和改進領域識別
   - 投資策略調整建議
   - 風險管理優化建議

請提供數據導向、客觀的績效分析和具體的改進建議。"""


@mcp.prompt()
def advanced_risk_management(account: str) -> str:
    """提供進階風險管理和投資組合優化建議

    這個提示會進行多維度的風險評估，包含市場風險、信用風險、
    流動性風險等，並提供現代投資組合理論的優化建議。

    Args:
        account: 帳戶號碼

    Returns:
        進階風險管理報告，包含：
        - 多因子風險評估
        - 投資組合優化建議（有效前沿）
        - 風險平價配置策略
        - 壓力測試結果
        - 動態風險管理策略
    """
    return f"""請為帳戶 {account} 提供進階風險管理和投資組合優化分析：

1. **多因子風險評估**
   - 使用 get_portfolio_summary 資源分析持倉結構
   - 評估市場風險暴露（Beta係數）
   - 分析行業集中度風險
   - 評估個股特定風險
   - 計算流動性風險指標

2. **投資組合風險指標**
   - 計算投資組合VaR（Value at Risk）
   - 分析壓力測試結果（各種市場情境）
   - 評估極端事件風險（黑天鵝事件）
   - 計算風險價值調整後報酬

3. **現代投資組合理論應用**
   - 分析有效前沿（Efficient Frontier）
   - 計算最優風險-報酬組合
   - 評估當前組合與最優組合的差距
   - 提供再平衡建議

4. **風險平價策略**
   - 分析各資產風險貢獻度
   - 設計風險平價配置策略
   - 比較等權重 vs 風險平價配置
   - 提供動態調整機制

5. **壓力測試與情境分析**
   - 模擬市場崩盤情境（-20%, -30%）
   - 分析利率上升情境影響
   - 評估匯率波動風險
   - 測試流動性緊縮情境

6. **動態風險管理**
   - 設定動態停損機制
   - 設計風險預警指標
   - 提供風險對沖策略
   - 制定風險預算管理

請提供量化分析和具體可行的風險管理策略。"""


@mcp.prompt()
def portfolio_optimization(account: str, objective: str = "max_sharpe") -> str:
    """提供投資組合優化建議（現代投資組合理論）

    這個提示會應用現代投資組合理論，為投資組合提供最佳化配置建議，
    包含有效前沿分析、風險平價、Black-Litterman模型等進階技術。

    Args:
        account: 帳戶號碼
        objective: 優化目標，可選 "max_sharpe", "min_volatility", "target_return", "risk_parity"

    Returns:
        投資組合優化報告，包含：
        - 當前組合分析
        - 有效前沿計算
        - 優化後配置建議
        - 預期風險和報酬
        - 實施策略和再平衡計劃
    """
    objective_descriptions = {
        "max_sharpe": "最大化夏普比率",
        "min_volatility": "最小化波動率",
        "target_return": "達成目標報酬",
        "risk_parity": "風險平價配置",
    }

    objective_desc = objective_descriptions.get(objective, "綜合優化")

    return f"""請為帳戶 {account} 提供{objective_desc}的投資組合優化分析：

1. **當前組合診斷**
   - 使用 get_portfolio_summary 資源分析現有持倉
   - 計算當前組合的預期報酬和風險
   - 評估組合分散度和相關性
   - 分析與市場基準的比較

2. **資產預期報酬估計**
   - 分析歷史報酬數據
   - 考慮基本面因素（財務指標、成長性）
   - 納入市場預期和經濟指標
   - 使用 Black-Litterman 模型整合主觀觀點

3. **風險模型建構**
   - 估計資產間相關係數矩陣
   - 計算個股波動率
   - 考慮系統性風險和特質風險
   - 建構多因子風險模型

4. **投資組合優化**
   - 計算有效前沿（Efficient Frontier）
   - 根據{objective_desc}目標尋找最優組合
   - 考慮交易成本和流動性約束
   - 設定風險預算和集中度限制

5. **優化結果分析**
   - 比較優化前後的風險-報酬特徵
   - 分析個股權重變動原因
   - 評估預期改進幅度
   - 進行敏感性分析

6. **實施策略**
   - 制定分階段調整計劃
   - 設定再平衡觸發條件
   - 設計風險控制機制
   - 提供績效監控指標

請提供數學嚴謹的優化分析和務實的實施建議。"""


@mcp.prompt()
def market_sentiment_analysis() -> str:
    """提供市場情緒分析和投資機會識別

    這個提示會整合多種市場情緒指標，包含新聞情感分析、
    社交媒體情緒、技術指標情緒、選擇權情緒等，提供市場情緒全景圖。

    Returns:
        市場情緒分析報告，包含：
        - 多維度情緒指標綜合評分
        - 市場極端情緒警示
        - 情緒驅動的投資機會
        - 反向投資策略建議
    """
    return """請提供當前市場的全面情緒分析：

1. **技術指標情緒分析**
   - 使用 get_trading_signals 工具分析多項技術指標
   - 計算技術指標總體樂觀度（0-100分）
   - 分析指標背離和極端讀數
   - 評估市場過熱/過冷程度

2. **成交量情緒分析**
   - 使用 get_snapshot_actives 工具分析成交活躍股
   - 分析成交量與價格趨勢的配合度
   - 計算恐慌指數（Put/Call Ratio）
   - 評估市場參與度和熱度

3. **新聞和媒體情緒**
   - 分析金融新聞情感傾向
   - 評估媒體報導的正面/負面比例
   - 監測重要事件和公告影響
   - 計算新聞情緒指數

4. **投資者行為分析**
   - 分析散戶 vs 機構投資者行為
   - 評估融資融券餘額變化
   - 監測大戶持股變化
   - 分析外資和投信動向

5. **選擇權情緒指標**
   - 分析選擇權未平倉量分布
   - 計算選擇權恐慌指數
   - 評估市場對未來波動率的預期
   - 分析看漲/看跌選擇權比例

6. **綜合情緒評分**
   - 整合各項情緒指標
   - 計算整體市場情緒指數
   - 識別情緒極端區間
   - 提供情緒導向的投資建議

7. **反向投資機會**
   - 識別過度樂觀/悲觀的標的
   - 分析均值回歸機會
   - 提供逆向投資策略
   - 設定情緒反轉訊號

請提供數據導向的情緒分析和具體的投資機會建議。"""


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
        - 實戰部署建議
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

7. **實戰部署建議**
   - 設計訂單執行邏輯
   - 設定監控和警示機制
   - 制定策略調整規則
   - 提供績效追蹤指標

請提供完整的量化策略框架，包含代碼示例和實戰部署指南。"""


@mcp.prompt()
def options_strategy_optimizer(symbol: str, market_view: str = "neutral") -> str:
    """提供選擇權策略優化建議

    這個提示會分析選擇權市場，為指定的標的提供最適合的選擇權策略，
    包含Greeks分析、策略比較、風險評估等。

    Args:
        symbol: 標的股票代碼
        market_view: 市場觀點，可選 "bullish", "bearish", "neutral", "volatile"

    Returns:
        選擇權策略優化報告，包含：
        - 適合的選擇權策略推薦
        - Greeks分析和風險指標
        - 策略比較和預期報酬
        - 實施建議和風險管理
    """
    view_descriptions = {
        "bullish": "看漲觀點",
        "bearish": "看跌觀點",
        "neutral": "中性觀點",
        "volatile": "高波動預期",
    }

    view_desc = view_descriptions.get(market_view, "市場觀點")

    return f"""請提供{symbol}的選擇權策略優化建議，基於{view_desc}：

1. **市場環境分析**
   - 使用 get_trading_signals 工具分析{symbol}技術指標
   - 評估當前波動率環境
   - 分析選擇權隱含波動率
   - 評估市場對未來波動的預期

2. **策略適配性分析**
   - 根據{view_desc}推薦適合策略
   - 比較單一選擇權 vs 複合策略
   - 分析策略的成本效益
   - 評估策略的靈活度

3. **Greeks分析**
   - 計算Delta、Gamma、Theta、Vega、Rho
   - 分析選擇權敏感度
   - 評估時間價值衰減
   - 分析波動率變化影響

4. **策略具體設計**
   - 設計具體的選擇權組合
   - 設定履約價和到期日
   - 計算最大損失和潛在獲利
   - 分析盈虧平衡點

5. **風險評估**
   - 計算策略的最大風險
   - 分析崩盤風險（Gap risk）
   - 評估提前履約可能性
   - 設計風險對沖機制

6. **成本效益分析**
   - 比較不同策略的成本
   - 分析預期報酬率
   - 計算策略的效率指標
   - 評估資金使用效率

7. **執行與管理**
   - 提供下單執行建議
   - 設定調整和退出條件
   - 設計監控指標
   - 制定風險控制計劃

請提供專業的選擇權策略分析和具體的實施建議。"""


@mcp.prompt()
def futures_spread_analyzer(futures_type: str = "tx") -> str:
    """提供期貨價差分析和套利機會識別

    這個提示會分析期貨價差走勢，識別套利機會，包含跨月價差、
    跨式價差、蝶式價差等進階分析。

    Args:
        futures_type: 期貨類型，可選 "tx" (台指期), "mt" (小台), "te" (電子期)

    Returns:
        期貨價差分析報告，包含：
        - 價差走勢分析
        - 套利機會識別
        - 風險評估
        - 交易策略建議
    """
    futures_names = {"tx": "台指期", "mt": "小台期", "te": "電子期"}

    futures_name = futures_names.get(futures_type, futures_type.upper())

    return f"""請提供{futures_name}的期貨價差分析和套利機會識別：

1. **價差基本分析**
   - 分析近月 vs 遠月合約價差
   - 評估價差的正常範圍
   - 分析季節性價差走勢
   - 計算價差的統計特性

2. **跨月價差分析**
   - 比較不同到期月份的價差
   - 分析持倉成本和融資成本影響
   - 識別異常價差機會
   - 評估套利空間

3. **蝶式價差分析**
   - 分析蝶式價差的公平價值
   - 識別蝶式套利機會
   - 評估波動率曲線影響
   - 計算蝶式價差的Greeks

4. **統計套利機會**
   - 使用統計方法識別偏離
   - 計算Z-score和標準差
   - 設定進出場門檻
   - 評估套利成功機率

5. **風險管理**
   - 分析基差風險
   - 評估流動性風險
   - 考慮跳空風險
   - 設計停損機制

6. **交易策略建議**
   - 提供具體的套利策略
   - 設定倉位大小和槓桿
   - 制定進出場時機
   - 提供績效預期

請提供專業的期貨價差分析和具體的套利策略建議。"""


@mcp.prompt()
def volatility_trading_advisor(symbol: str) -> str:
    """提供波動率交易策略建議

    這個提示會分析市場波動率，提供波動率交易策略，包含VIX相關策略、
    選擇權波動率交易、統計波動率交易等。

    Args:
        symbol: 股票代碼或指數代碼

    Returns:
        波動率交易策略報告，包含：
            - 波動率環境分析
            - 波動率交易機會
            - 策略設計和風險管理
            - 實施建議
    """
    return f"""請為{symbol}提供波動率交易策略分析和建議：

1. **波動率環境分析**
   - 分析{symbol}的歷史波動率
   - 比較隱含波動率 vs 實現波動率
   - 評估當前波動率等級
   - 分析波動率微笑曲線

2. **波動率指標分析**
   - 計算ATR（平均真實波動）
   - 分析布林通道波動性
   - 評估波動率的趨勢
   - 識別波動率極端值

3. **波動率交易策略**
   - 設計長波動率策略（看漲波動）
   - 設計短波動率策略（看跌波動）
   - 分析選擇權的波動率交易
   - 評估統計套利機會

4. **VIX相關策略**
   - 分析VIX指數走勢
   - 設計VIX期貨和選擇權策略
   - 評估波動率風險溢價
   - 分析恐慌指數應用

5. **風險管理**
   - 設定波動率止損機制
   - 設計動態對沖策略
   - 評估Gamma和Vega風險
   - 制定資金管理計劃

6. **市場時機選擇**
   - 識別高波動環境機會
   - 分析低波動環境策略
   - 評估事件驅動波動
   - 設定進出場訊號

請提供專業的波動率交易分析和具體的策略建議。"""


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

    def initialize_sdk(self, username: str, password: str, pfx_path: str, pfx_password: str = ""):
        """初始化SDK"""
        try:
            logger.info("正在初始化富邦證券SDK...")
            self.sdk = FubonSDK()
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


def main():
    """
    應用程式主入口點函數。

    負責初始化富邦證券 SDK、進行身份認證、設定事件回調，
    並啟動 MCP 服務器。這個函數會在程式啟動時執行所有必要的初始化工作。

    初始化流程:
    1. 檢查必要的環境變數（用戶名、密碼、憑證路徑）
    2. 初始化富邦 SDK 實例
    3. 登入到富邦證券系統
    4. 初始化即時資料連線
    5. 設定所有主動回報事件回調函數
    6. 啟動 MCP 服務器

    環境變數需求:
    - FUBON_USERNAME: 富邦證券帳號
    - FUBON_PASSWORD: 登入密碼
    - FUBON_PFX_PATH: PFX 憑證檔案路徑
    - FUBON_PFX_PASSWORD: PFX 憑證密碼（可選）

    如果初始化失敗，程式會輸出錯誤訊息並以錯誤代碼退出。
    """
    try:
        # 檢查必要的環境變數
        if not all([username, password, pfx_path]):
            raise ValueError("FUBON_USERNAME, FUBON_PASSWORD, and FUBON_PFX_PATH environment variables are required")

        # 使用新的狀態管理系統初始化SDK
        success = server_state.initialize_sdk(username, password, pfx_path, pfx_password or "")
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
        indicators_service = AnalysisService(
            mcp, config.sdk, config.accounts, config.reststock, config.restfutopt
        )

        logger.info("富邦證券MCP server運行中...")
        mcp.run()
    except KeyboardInterrupt:
        logger.info("收到中斷信號，正在優雅關閉...")
        server_state.logout()
        sys.exit(0)
    except Exception as e:
        logger.exception(f"啟動伺服器時發生錯誤: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
