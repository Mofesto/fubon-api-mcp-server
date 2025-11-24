#!/usr/bin/env python3
"""
富邦 API MCP Server - Reports Service 單元測試

此測試檔案使用 pytest 框架測試 reports_service 的所有功能。
測試分為兩類：
1. 模擬測試：使用 mock 物件測試邏輯
2. 整合測試：使用真實 API 測試（需要環境變數）

使用方法：
# 運行所有測試
pytest tests/test_reports_service.py -v

# 只運行模擬測試
pytest tests/test_reports_service.py::TestReportsServiceMock -v

# 只運行整合測試（需要真實憑證）
pytest tests/test_reports_service.py::TestReportsServiceIntegration -v
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from mcp.server.fastmcp import FastMCP

from fubon_api_mcp_server.reports_service import ReportsService


class TestReportsServiceMock:
    """模擬測試 - 不依賴真實 API"""

    @pytest.fixture
    def mock_mcp(self):
        """模擬 MCP 實例"""
        return Mock(spec=FastMCP)

    @pytest.fixture
    def mock_sdk(self):
        """模擬 SDK 實例"""
        sdk = Mock()
        return sdk

    @pytest.fixture
    def mock_accounts(self):
        """模擬帳戶列表"""
        return ["1234567", "7654321"]

    @pytest.fixture
    def reports_service(self, mock_mcp, mock_sdk, mock_accounts):
        """建立 ReportsService 實例"""
        return ReportsService(mock_mcp, mock_sdk, mock_accounts)

    @patch("fubon_api_mcp_server.reports_service.server_state.latest_order_reports")
    @patch("fubon_api_mcp_server.reports_service.server_state.latest_order_changed_reports")
    @patch("fubon_api_mcp_server.reports_service.server_state.latest_filled_reports")
    @patch("fubon_api_mcp_server.reports_service.server_state.latest_event_reports")
    def test_get_all_reports(
        self, mock_event_reports, mock_filled_reports, mock_order_changed_reports, mock_order_reports, reports_service
    ):
        """測試獲取所有報告"""
        # 設置模擬數據
        mock_order_reports.__iter__ = Mock(return_value=iter([{"order_id": "1"}]))
        mock_order_reports.copy.return_value = [{"order_id": "1"}]
        mock_order_changed_reports.copy.return_value = [{"change_id": "2"}]
        mock_filled_reports.copy.return_value = [{"fill_id": "3"}]
        mock_event_reports.copy.return_value = [{"event_id": "4"}]

        result = reports_service.get_all_reports({})

        assert result["status"] == "success"
        assert "data" in result
        assert "order_reports" in result["data"]
        assert "order_changed_reports" in result["data"]
        assert "filled_reports" in result["data"]
        assert "event_reports" in result["data"]
        assert "成功獲取所有報告" in result["message"]

    @patch("fubon_api_mcp_server.reports_service.server_state.latest_order_reports")
    def test_get_order_reports(self, mock_order_reports, reports_service):
        """測試獲取委託報告"""
        mock_data = [{"order_id": "1"}, {"order_id": "2"}]
        mock_order_reports.copy.return_value = mock_data
        mock_order_reports.__len__ = Mock(return_value=len(mock_data))

        result = reports_service.get_order_reports({})

        assert result["status"] == "success"
        assert result["data"] == mock_data
        assert "成功獲取委託報告，共 2 筆" in result["message"]

    @patch("fubon_api_mcp_server.reports_service.server_state.latest_order_changed_reports")
    def test_get_order_changed_reports(self, mock_order_changed_reports, reports_service):
        """測試獲取委託變更報告"""
        mock_data = [{"change_id": "1"}]
        mock_order_changed_reports.copy.return_value = mock_data
        mock_order_changed_reports.__len__ = Mock(return_value=len(mock_data))

        result = reports_service.get_order_changed_reports({})

        assert result["status"] == "success"
        assert result["data"] == mock_data
        assert "成功獲取委託變更報告，共 1 筆" in result["message"]

    @patch("fubon_api_mcp_server.reports_service.server_state.latest_filled_reports")
    def test_get_filled_reports(self, mock_filled_reports, reports_service):
        """測試獲取成交報告"""
        mock_data = [{"fill_id": "1"}, {"fill_id": "2"}, {"fill_id": "3"}]
        mock_filled_reports.copy.return_value = mock_data
        mock_filled_reports.__len__ = Mock(return_value=len(mock_data))

        result = reports_service.get_filled_reports({})

        assert result["status"] == "success"
        assert result["data"] == mock_data
        assert "成功獲取成交報告，共 3 筆" in result["message"]

    @patch("fubon_api_mcp_server.reports_service.server_state.latest_event_reports")
    def test_get_event_reports(self, mock_event_reports, reports_service):
        """測試獲取事件報告"""
        mock_data = [{"event_id": "1"}]
        mock_event_reports.copy.return_value = mock_data
        mock_event_reports.__len__ = Mock(return_value=len(mock_data))

        result = reports_service.get_event_reports({})

        assert result["status"] == "success"
        assert result["data"] == mock_data
        assert "成功獲取事件報告，共 1 筆" in result["message"]

    def test_initialization(self, reports_service):
        """測試 ReportsService 初始化"""
        assert reports_service.mcp is not None
        assert reports_service.sdk is not None
        assert reports_service.accounts is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
