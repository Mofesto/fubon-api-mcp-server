"""
Unit tests for reports_service.py module.
"""

from unittest.mock import Mock, patch

from fubon_mcp.reports_service import (
    get_all_reports,
    get_event_reports,
    get_filled_reports,
    get_order_changed_reports,
    get_order_reports,
    get_order_results,
)


class TestGetOrderResults:
    """Test get_order_results function."""

    @patch("fubon_mcp.reports_service.validate_and_get_account")
    @patch("fubon_mcp.reports_service.sdk")
    def test_get_order_results_success(self, mock_sdk, mock_validate):
        """Test successful order results retrieval."""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_order_results = Mock()
        mock_order_results.is_success = True
        mock_order_results.data = [{"order_no": "123", "status": "filled"}]
        mock_sdk.stock.get_order_results.return_value = mock_order_results

        result = get_order_results({"account": "123456"})
        assert result["status"] == "success"
        assert result["data"] == [{"order_no": "123", "status": "filled"}]
        assert "Successfully retrieved order results" in result["message"]

    @patch("fubon_mcp.reports_service.validate_and_get_account")
    def test_get_order_results_invalid_account(self, mock_validate):
        """Test order results with invalid account."""
        mock_validate.return_value = (None, "Account not found")

        result = get_order_results({"account": "invalid"})
        assert result["status"] == "error"
        assert result["data"] is None
        assert result["message"] == "Account not found"

    @patch("fubon_mcp.reports_service.validate_and_get_account")
    @patch("fubon_mcp.reports_service.sdk")
    def test_get_order_results_api_failure(self, mock_sdk, mock_validate):
        """Test order results when API fails."""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_order_results = Mock()
        mock_order_results.is_success = False
        mock_sdk.stock.get_order_results.return_value = mock_order_results

        result = get_order_results({"account": "123456"})
        assert result["status"] == "error"
        assert result["data"] is None
        assert "Unable to get order results" in result["message"]

    @patch("fubon_mcp.reports_service.validate_and_get_account")
    @patch("fubon_mcp.reports_service.sdk")
    def test_get_order_results_exception(self, mock_sdk, mock_validate):
        """Test order results with exception."""
        mock_account_obj = Mock()
        mock_validate.return_value = (mock_account_obj, None)

        mock_sdk.stock.get_order_results.side_effect = Exception("API error")

        result = get_order_results({"account": "123456"})
        assert result["status"] == "error"
        assert result["data"] is None
        assert "Failed to get order results" in result["message"]


class TestGetOrderReports:
    """Test get_order_reports function."""

    @patch("fubon_mcp.reports_service.latest_order_reports", [{"id": 1}, {"id": 2}, {"id": 3}])
    def test_get_order_reports_success(self):
        """Test successful order reports retrieval."""
        result = get_order_reports({"limit": 2})
        assert result["status"] == "success"
        assert len(result["data"]) == 2
        assert result["count"] == 2
        assert "Successfully retrieved latest 2 order reports" in result["message"]

    @patch("fubon_mcp.reports_service.latest_order_reports", [])
    def test_get_order_reports_empty(self):
        """Test order reports when no reports available."""
        result = get_order_reports({"limit": 10})
        assert result["status"] == "success"
        assert result["data"] == []
        assert result["count"] == 0

    @patch("fubon_mcp.reports_service.latest_order_reports", [{"id": 1}, {"id": 2}])
    def test_get_order_reports_default_limit(self):
        """Test order reports with default limit."""
        result = get_order_reports({})
        assert result["status"] == "success"
        assert len(result["data"]) == 2  # All available reports
        assert result["count"] == 2

    def test_get_order_reports_exception(self):
        """Test order reports with exception."""
        result = get_order_reports({"limit": "invalid"})
        assert result["status"] == "error"
        assert result["data"] is None
        assert "Failed to get order reports" in result["message"]


class TestGetOrderChangedReports:
    """Test get_order_changed_reports function."""

    @patch("fubon_mcp.reports_service.latest_order_changed_reports", [{"id": 1}, {"id": 2}])
    def test_get_order_changed_reports_success(self):
        """Test successful order changed reports retrieval."""
        result = get_order_changed_reports({"limit": 1})
        assert result["status"] == "success"
        assert len(result["data"]) == 1
        assert result["count"] == 1
        assert "Successfully retrieved latest 1 order change reports" in result["message"]

    @patch("fubon_mcp.reports_service.latest_order_changed_reports", [])
    def test_get_order_changed_reports_empty(self):
        """Test order changed reports when no reports available."""
        result = get_order_changed_reports({"limit": 5})
        assert result["status"] == "success"
        assert result["data"] == []
        assert result["count"] == 0


class TestGetFilledReports:
    """Test get_filled_reports function."""

    @patch("fubon_mcp.reports_service.latest_filled_reports", [{"order_no": "123"}, {"order_no": "456"}])
    def test_get_filled_reports_success(self):
        """Test successful filled reports retrieval."""
        result = get_filled_reports({"limit": 2})
        assert result["status"] == "success"
        assert len(result["data"]) == 2
        assert result["count"] == 2
        assert "Successfully retrieved latest 2 fill reports" in result["message"]

    @patch("fubon_mcp.reports_service.latest_filled_reports", [])
    def test_get_filled_reports_empty(self):
        """Test filled reports when no reports available."""
        result = get_filled_reports({"limit": 10})
        assert result["status"] == "success"
        assert result["data"] == []
        assert result["count"] == 0


class TestGetEventReports:
    """Test get_event_reports function."""

    @patch("fubon_mcp.reports_service.latest_event_reports", [{"event": "login"}, {"event": "logout"}])
    def test_get_event_reports_success(self):
        """Test successful event reports retrieval."""
        result = get_event_reports({"limit": 1})
        assert result["status"] == "success"
        assert len(result["data"]) == 1
        assert result["count"] == 1
        assert "Successfully retrieved latest 1 event notifications" in result["message"]

    @patch("fubon_mcp.reports_service.latest_event_reports", [])
    def test_get_event_reports_empty(self):
        """Test event reports when no reports available."""
        result = get_event_reports({"limit": 5})
        assert result["status"] == "success"
        assert result["data"] == []
        assert result["count"] == 0


class TestGetAllReports:
    """Test get_all_reports function."""

    @patch("fubon_mcp.reports_service.latest_order_reports", [{"id": 1}])
    @patch("fubon_mcp.reports_service.latest_order_changed_reports", [{"id": 2}, {"id": 3}])
    @patch("fubon_mcp.reports_service.latest_filled_reports", [{"id": 4}])
    @patch("fubon_mcp.reports_service.latest_event_reports", [{"id": 5}, {"id": 6}])
    def test_get_all_reports_success(self):
        """Test successful all reports retrieval."""
        result = get_all_reports({"limit": 2})
        assert result["status"] == "success"
        assert "order_reports" in result["data"]
        assert "order_changed_reports" in result["data"]
        assert "filled_reports" in result["data"]
        assert "event_reports" in result["data"]
        assert result["total_count"] == 6  # 1 + 2 + 1 + 2
        assert "Successfully retrieved all types of active reports" in result["message"]

    @patch("fubon_mcp.reports_service.latest_order_reports", [])
    @patch("fubon_mcp.reports_service.latest_order_changed_reports", [])
    @patch("fubon_mcp.reports_service.latest_filled_reports", [])
    @patch("fubon_mcp.reports_service.latest_event_reports", [])
    def test_get_all_reports_empty(self):
        """Test all reports when no reports available."""
        result = get_all_reports({"limit": 5})
        assert result["status"] == "success"
        assert result["total_count"] == 0
        assert all(len(reports) == 0 for reports in result["data"].values())

    def test_get_all_reports_exception(self):
        """Test all reports with exception."""
        result = get_all_reports({"limit": "invalid"})
        assert result["status"] == "error"
        assert result["data"] is None
        assert "Failed to get all reports" in result["message"]
