#!/usr/bin/env python3
"""
富邦證券串流服務

此模組提供 WebSocket 和即時數據串流功能，包括：
- 市場數據訂閱和取消訂閱
- 即時數據獲取
- 事件監聽器管理
- WebSocket 串流控制
- 即時數據推送

主要組件：
- StreamingService: 串流服務類
- WebSocket 連線管理
- 即時數據緩衝區管理
- 事件監聽器系統
"""

import logging
from datetime import datetime
from typing import Dict, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field


class StreamingService:
    """串流服務類"""

    def __init__(self, mcp: FastMCP, server_state):
        self.mcp = mcp
        self.server_state = server_state
        self._register_tools()
        self.logger = logging.getLogger(__name__)

    def _register_tools(self):
        """註冊所有串流相關的工具"""
        # 市場數據訂閱工具
        self.mcp.tool()(self.subscribe_market_data)
        self.mcp.tool()(self.unsubscribe_market_data)
        self.mcp.tool()(self.get_active_subscriptions)
        self.mcp.tool()(self.get_realtime_data)

        # 事件監聽器工具
        self.mcp.tool()(self.register_event_listener)
        self.mcp.tool()(self.unregister_event_listener)

        # WebSocket 串流工具
        self.mcp.tool()(self.start_websocket_stream)
        self.mcp.tool()(self.stop_websocket_stream)
        self.mcp.tool()(self.get_stream_status)
        self.mcp.tool()(self.get_all_stream_status)
        self.mcp.tool()(self.push_realtime_update)

    def subscribe_market_data(self, args: Dict) -> dict:
        """
        訂閱市場數據

        訂閱指定股票或期貨的即時市場數據，包括報價、K線、成交量等。
        支援的數據類型：quote（報價）、candles（K線）、volume（成交量）。

        Args:
            symbol (str): 股票代碼或期貨合約代碼
            data_type (str): 數據類型，可選 "quote", "candles", "volume"，預設 "quote"

        Returns:
            dict: 訂閱結果，包含 stream_id 用於後續取消訂閱

        Example:
            {
                "symbol": "2330",
                "data_type": "quote"
            }
        """
        try:
            validated_args = SubscribeMarketDataArgs(**args)
            symbol = validated_args.symbol
            data_type = validated_args.data_type

            stream_id = self.server_state.subscribe_market_data(symbol, data_type)

            if stream_id:
                return {
                    "status": "success",
                    "data": {
                        "stream_id": stream_id,
                        "symbol": symbol,
                        "data_type": data_type,
                        "subscribed_at": datetime.now().isoformat(),
                    },
                    "message": f"成功訂閱 {symbol} 的 {data_type} 數據",
                }
            else:
                return {
                    "status": "error",
                    "data": None,
                    "message": f"訂閱 {symbol} 的 {data_type} 數據失敗",
                }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"訂閱市場數據失敗: {str(e)}",
            }

    def unsubscribe_market_data(self, args: Dict) -> dict:
        """
        取消訂閱市場數據

        取消指定的市場數據訂閱。

        Args:
            stream_id (str): 訂閱時返回的 stream_id

        Returns:
            dict: 取消訂閱結果

        Example:
            {
                "stream_id": "stream_TX00_quote_1699999999"
            }
        """
        try:
            validated_args = UnsubscribeMarketDataArgs(**args)
            stream_id = validated_args.stream_id

            success = self.server_state.unsubscribe_market_data(stream_id)

            if success:
                return {
                    "status": "success",
                    "data": {"stream_id": stream_id},
                    "message": f"成功取消訂閱 {stream_id}",
                }
            else:
                return {
                    "status": "error",
                    "data": None,
                    "message": f"取消訂閱 {stream_id} 失敗，訂閱不存在",
                }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"取消訂閱市場數據失敗: {str(e)}",
            }

    def get_active_subscriptions(self, args: Dict) -> dict:
        """
        獲取所有活躍的訂閱

        返回當前所有活躍的市場數據訂閱資訊。

        Returns:
            dict: 包含所有活躍訂閱的詳細資訊

        Example:
            {}  # 無參數
        """
        try:
            subscriptions = self.server_state.get_active_subscriptions()

            return {
                "status": "success",
                "data": subscriptions,
                "total_market_subscriptions": len(subscriptions.get("market_subscriptions", {})),
                "total_active_streams": len(subscriptions.get("active_streams", {})),
                "message": f"成功獲取活躍訂閱資訊，共 {len(subscriptions.get('active_streams', {}))} 個活躍串流",
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取活躍訂閱失敗: {str(e)}",
            }

    def get_realtime_data(self, args: Dict) -> dict:
        """
        獲取即時數據

        獲取指定股票或期貨的最新即時數據（如果有訂閱）。

        Args:
            symbol (str): 股票代碼或期貨合約代碼

        Returns:
            dict: 最新的即時數據

        Example:
            {
                "symbol": "2330"
            }
        """
        try:
            validated_args = GetRealtimeDataArgs(**args)
            symbol = validated_args.symbol

            data = self.server_state.get_realtime_data(symbol)

            if data:
                return {
                    "status": "success",
                    "data": data,
                    "symbol": symbol,
                    "message": f"成功獲取 {symbol} 的即時數據",
                }
            else:
                return {
                    "status": "error",
                    "data": None,
                    "message": f"找不到 {symbol} 的即時數據，請先訂閱",
                }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取即時數據失敗: {str(e)}",
            }

    def register_event_listener(self, args: Dict) -> dict:
        """
        註冊事件監聽器

        註冊指定事件類型的監聽器，用於接收即時事件通知。

        Args:
            event_type (str): 事件類型，例如 "order_update", "price_alert", "connection_status"
            listener_id (str): 監聽器唯一識別碼

        Returns:
            dict: 註冊結果

        Example:
            {
                "event_type": "order_update",
                "listener_id": "my_order_listener"
            }
        """
        try:
            validated_args = RegisterEventListenerArgs(**args)
            event_type = validated_args.event_type
            listener_id = validated_args.listener_id

            # 創建一個簡單的回調函數（實際應用中可能需要更複雜的邏輯）
            def event_callback(event_data):
                self.logger.info(f"收到事件 {event_type}: {event_data}")

            self.server_state.register_event_listener(event_type, listener_id, event_callback)

            return {
                "status": "success",
                "data": {
                    "event_type": event_type,
                    "listener_id": listener_id,
                    "registered_at": datetime.now().isoformat(),
                },
                "message": f"成功註冊 {event_type} 事件監聽器",
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"註冊事件監聽器失敗: {str(e)}",
            }

    def unregister_event_listener(self, args: Dict) -> dict:
        """
        取消註冊事件監聽器

        取消指定的事件監聽器。

        Args:
            event_type (str): 事件類型
            listener_id (str): 監聽器唯一識別碼

        Returns:
            dict: 取消註冊結果

        Example:
            {
                "event_type": "order_update",
                "listener_id": "my_order_listener"
            }
        """
        try:
            validated_args = UnregisterEventListenerArgs(**args)
            event_type = validated_args.event_type
            listener_id = validated_args.listener_id

            self.server_state.unregister_event_listener(event_type, listener_id)

            return {
                "status": "success",
                "data": {
                    "event_type": event_type,
                    "listener_id": listener_id,
                },
                "message": f"成功取消註冊 {event_type} 事件監聽器",
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"取消註冊事件監聽器失敗: {str(e)}",
            }

    def start_websocket_stream(self, args: Dict) -> dict:
        """
        啟動 WebSocket 即時串流

        啟動指定股票或期貨的 WebSocket 即時數據串流，
        提供低延遲的即時市場數據更新。

        Args:
            symbol (str): 股票代碼或期貨合約代碼
            data_type (str): 數據類型，可選 "quote", "candles", "volume"，預設 "quote"
            interval (int): 更新間隔（秒），預設 1

        Returns:
            dict: 串流啟動結果，包含 stream_id

        Example:
            {
                "symbol": "2330",
                "data_type": "quote",
                "interval": 1
            }
        """
        try:
            validated_args = StartWebSocketStreamArgs(**args)
            symbol = validated_args.symbol
            data_type = validated_args.data_type
            interval = validated_args.interval

            stream_id = self.server_state.start_websocket_stream(symbol, data_type, interval)

            if stream_id:
                return {
                    "status": "success",
                    "data": {
                        "stream_id": stream_id,
                        "symbol": symbol,
                        "data_type": data_type,
                        "interval": interval,
                        "started_at": datetime.now().isoformat(),
                    },
                    "message": f"成功啟動 {symbol} 的 {data_type} WebSocket 串流",
                }
            else:
                return {
                    "status": "error",
                    "data": None,
                    "message": f"啟動 {symbol} 的 {data_type} WebSocket 串流失敗",
                }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"啟動 WebSocket 串流失敗: {str(e)}",
            }

    def stop_websocket_stream(self, args: Dict) -> dict:
        """
        停止 WebSocket 即時串流

        停止指定的 WebSocket 數據串流。

        Args:
            stream_id (str): 串流 ID

        Returns:
            dict: 停止串流結果

        Example:
            {
                "stream_id": "ws_2330_quote_1699999999"
            }
        """
        try:
            validated_args = StopWebSocketStreamArgs(**args)
            stream_id = validated_args.stream_id

            success = self.server_state.stop_websocket_stream(stream_id)

            if success:
                return {
                    "status": "success",
                    "data": {"stream_id": stream_id},
                    "message": f"成功停止 WebSocket 串流 {stream_id}",
                }
            else:
                return {
                    "status": "error",
                    "data": None,
                    "message": f"停止 WebSocket 串流 {stream_id} 失敗，串流不存在",
                }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"停止 WebSocket 串流失敗: {str(e)}",
            }

    def get_stream_status(self, args: Dict) -> dict:
        """
        獲取串流狀態

        獲取指定 WebSocket 串流的詳細狀態資訊。

        Args:
            stream_id (str): 串流 ID

        Returns:
            dict: 串流狀態資訊

        Example:
            {
                "stream_id": "ws_2330_quote_1699999999"
            }
        """
        try:
            validated_args = GetStreamStatusArgs(**args)
            stream_id = validated_args.stream_id

            status = self.server_state.get_stream_status(stream_id)

            if status:
                return {
                    "status": "success",
                    "data": status,
                    "message": f"成功獲取串流 {stream_id} 狀態",
                }
            else:
                return {
                    "status": "error",
                    "data": None,
                    "message": f"找不到串流 {stream_id}",
                }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取串流狀態失敗: {str(e)}",
            }

    def get_all_stream_status(self, args: Dict) -> dict:
        """
        獲取所有串流狀態

        獲取所有活躍 WebSocket 串流的狀態總覽。

        Returns:
            dict: 所有串流狀態總覽

        Example:
            {}  # 無參數
        """
        try:
            status = self.server_state.get_all_stream_status()

            return {
                "status": "success",
                "data": status,
                "message": f"成功獲取所有串流狀態，共 {status['total_streams']} 個活躍串流",
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"獲取所有串流狀態失敗: {str(e)}",
            }

    def push_realtime_update(self, args: Dict) -> dict:
        """
        推送即時數據更新

        手動推送即時數據更新到所有相關的監聽器和訂閱者。
        通常用於測試或手動數據注入。

        Args:
            symbol (str): 股票代碼或期貨合約代碼
            data (dict): 要推送的數據
            data_type (str): 數據類型，可選 "quote", "candles", "volume"，預設 "quote"

        Returns:
            dict: 推送結果

        Example:
            {
                "symbol": "2330",
                "data": {"price": 500.0, "volume": 1000},
                "data_type": "quote"
            }
        """
        try:
            validated_args = PushRealtimeUpdateArgs(**args)
            symbol = validated_args.symbol
            data = validated_args.data
            data_type = validated_args.data_type

            self.server_state.push_realtime_update(symbol, data, data_type)

            return {
                "status": "success",
                "data": {
                    "symbol": symbol,
                    "data_type": data_type,
                    "data": data,
                    "pushed_at": datetime.now().isoformat(),
                },
                "message": f"成功推送 {symbol} 的 {data_type} 即時更新",
            }
        except Exception as e:
            return {
                "status": "error",
                "data": None,
                "message": f"推送即時更新失敗: {str(e)}",
            }


# Pydantic 參數驗證模型
class SubscribeMarketDataArgs(BaseModel):
    """訂閱市場數據參數"""

    symbol: str = Field(..., description="股票代碼或期貨合約代碼")
    data_type: str = Field("quote", description="數據類型：quote, candles, volume")


class UnsubscribeMarketDataArgs(BaseModel):
    """取消訂閱市場數據參數"""

    stream_id: str = Field(..., description="訂閱時返回的 stream_id")


class GetActiveSubscriptionsArgs(BaseModel):
    """獲取活躍訂閱參數（無參數）"""

    pass


class GetRealtimeDataArgs(BaseModel):
    """獲取即時數據參數"""

    symbol: str = Field(..., description="股票代碼或期貨合約代碼")


class RegisterEventListenerArgs(BaseModel):
    """註冊事件監聽器參數"""

    event_type: str = Field(..., description="事件類型，如 order_update, price_alert, connection_status")
    listener_id: str = Field(..., description="監聽器唯一識別碼")


class UnregisterEventListenerArgs(BaseModel):
    """取消註冊事件監聽器參數"""

    event_type: str = Field(..., description="事件類型")
    listener_id: str = Field(..., description="監聽器唯一識別碼")


class StartWebSocketStreamArgs(BaseModel):
    """啟動 WebSocket 串流參數"""

    symbol: str = Field(..., description="股票代碼或期貨合約代碼")
    data_type: str = Field("quote", description="數據類型：quote, candles, volume")
    interval: int = Field(1, description="更新間隔（秒）", ge=1)


class StopWebSocketStreamArgs(BaseModel):
    """停止 WebSocket 串流參數"""

    stream_id: str = Field(..., description="串流 ID")


class GetStreamStatusArgs(BaseModel):
    """獲取串流狀態參數"""

    stream_id: str = Field(..., description="串流 ID")


class PushRealtimeUpdateArgs(BaseModel):
    """推送即時更新參數"""

    symbol: str = Field(..., description="股票代碼或期貨合約代碼")
    data: Dict = Field(..., description="要推送的數據")
    data_type: str = Field("quote", description="數據類型：quote, candles, volume")
