"""
Test streaming functionality for Phase 2 implementation.
"""

import pytest
from unittest.mock import MagicMock, patch
from fubon_api_mcp_server.server import (
    start_websocket_stream,
    stop_websocket_stream,
    get_stream_status,
    get_all_stream_status,
    push_realtime_update,
    server_state
)


class TestWebSocketStreaming:
    """Test WebSocket streaming functionality."""

    def test_start_websocket_stream_success(self):
        """Test starting a WebSocket stream successfully."""
        # Mock the server state
        with patch.object(server_state, 'start_websocket_stream', return_value='stream_123') as mock_start:
            result = start_websocket_stream({
                'symbol': '2330',
                'data_type': 'quote',
                'interval': '1m'
            })

            assert result['status'] == 'success'
            assert 'stream_id' in result['data']
            mock_start.assert_called_once_with('2330', 'quote', '1m')

    def test_start_websocket_stream_failure(self):
        """Test starting a WebSocket stream with failure."""
        with patch.object(server_state, 'start_websocket_stream', return_value=None):
            result = start_websocket_stream({
                'symbol': 'INVALID',
                'data_type': 'quote'
            })

            assert result['status'] == 'error'
            assert '啟動 INVALID 的 quote WebSocket 串流失敗' in result['message']

    def test_stop_websocket_stream_success(self):
        """Test stopping a WebSocket stream successfully."""
        with patch.object(server_state, 'stop_websocket_stream', return_value=True) as mock_stop:
            result = stop_websocket_stream({
                'stream_id': 'stream_123'
            })

            assert result['status'] == 'success'
            mock_stop.assert_called_once_with('stream_123')

    def test_stop_websocket_stream_failure(self):
        """Test stopping a WebSocket stream with failure."""
        with patch.object(server_state, 'stop_websocket_stream', return_value=False):
            result = stop_websocket_stream({
                'stream_id': 'invalid_stream'
            })

            assert result['status'] == 'error'
            assert '停止 WebSocket 串流 invalid_stream 失敗，串流不存在' in result['message']

    def test_get_stream_status_success(self):
        """Test getting stream status successfully."""
        mock_status = {
            'stream_id': 'stream_123',
            'symbol': '2330',
            'data_type': 'quote',
            'status': 'active'
        }

        with patch.object(server_state, 'get_stream_status', return_value=mock_status):
            result = get_stream_status({
                'stream_id': 'stream_123'
            })

            assert result['status'] == 'success'
            assert result['data'] == mock_status

    def test_get_stream_status_not_found(self):
        """Test getting status for non-existent stream."""
        with patch.object(server_state, 'get_stream_status', return_value=None):
            result = get_stream_status({
                'stream_id': 'nonexistent'
            })

            assert result['status'] == 'error'
            assert '找不到' in result['message']

    def test_get_all_stream_status(self):
        """Test getting all stream statuses."""
        mock_status = {
            'total_streams': 2,
            'active_streams': ['stream_1', 'stream_2'],
            'streams': {}
        }

        with patch.object(server_state, 'get_all_stream_status', return_value=mock_status):
            result = get_all_stream_status({})

            assert result['status'] == 'success'
            assert result['data']['total_streams'] == 2

    def test_push_realtime_update_success(self):
        """Test pushing realtime update successfully."""
        with patch.object(server_state, 'push_realtime_update') as mock_push:
            result = push_realtime_update({
                'symbol': '2330',
                'data': {'price': 500.0},
                'data_type': 'quote'
            })

            assert result['status'] == 'success'
            mock_push.assert_called_once_with('2330', {'price': 500.0}, 'quote')


class TestMCPServerStateStreaming:
    """Test MCPServerState streaming methods."""

    def test_start_websocket_stream(self):
        """Test starting WebSocket stream in server state."""
        # Mock SDK
        mock_sdk = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success = True
        mock_sdk.marketdata.subscribe_quote.return_value = mock_result

        server_state.sdk = mock_sdk

        stream_id = server_state.start_websocket_stream('2330', 'quote', '1m')

        assert stream_id is not None
        assert stream_id.startswith('ws_')
        assert stream_id in server_state._active_streams
        assert server_state._active_streams[stream_id]['symbol'] == '2330'

    def test_stop_websocket_stream(self):
        """Test stopping WebSocket stream in server state."""
        # Setup active stream
        stream_id = 'test_stream_123'
        server_state._active_streams[stream_id] = {
            'subscription_key': '2330_quote',
            'symbol': '2330',
            'data_type': 'quote',
            'status': 'active'
        }

        # Mock SDK
        mock_sdk = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success = True
        mock_sdk.marketdata.unsubscribe_quote.return_value = mock_result

        server_state.sdk = mock_sdk

        result = server_state.stop_websocket_stream(stream_id)

        assert result is True
        assert stream_id not in server_state._active_streams

    def test_get_stream_status(self):
        """Test getting stream status."""
        stream_id = 'test_stream_123'
        server_state._active_streams[stream_id] = {
            'stream_id': stream_id,
            'subscription_key': '2330_quote',
            'symbol': '2330',
            'data_type': 'quote',
            'status': 'active'
        }

        status = server_state.get_stream_status(stream_id)

        assert status is not None
        assert status['stream_id'] == stream_id
        assert status['status'] == 'active'

    def test_get_all_stream_status(self):
        """Test getting all stream statuses."""
        # Setup multiple streams
        server_state._active_streams = {
            'stream_1': {'symbol': '2330', 'data_type': 'quote', 'status': 'active'},
            'stream_2': {'symbol': '2454', 'data_type': 'candles', 'status': 'active'},
        }

        status = server_state.get_all_stream_status()

        assert status['total_streams'] == 2
        assert len(status['active_streams']) == 2

    def test_push_realtime_update(self):
        """Test pushing realtime update."""
        # Setup callback
        callback_called = []

        def test_callback(symbol, data, data_type):
            callback_called.append((symbol, data, data_type))

        server_state._stream_callbacks['test_callback'] = test_callback

        server_state.push_realtime_update('2330', {'price': 500.0}, 'quote')

        # Note: In real implementation, callbacks would be called
        # This is a basic test structure