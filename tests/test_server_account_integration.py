#!/usr/bin/env python3
import pytest
from unittest.mock import Mock, patch

from fubon_api_mcp_server import server


class TestServerAccountIntegration:
    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    def test_get_watchlist_with_serialized_inventory(self, mock_validate):
        # Arrange
        mock_validate.return_value = (Mock(account="1234567"), None)
        mock_inventory = [
            {
                "stock_no": "0050",
                "stock_name": "ETF-0050",
                "quantity": 1000,
                "market_price": 55.0,
            }
        ]

        with patch.object(server, "account_service") as mock_account_service:
            mock_account_service.get_inventory.return_value = {
                "status": "success",
                "data": mock_inventory,
                "message": "ok",
            }

            # Act
            result = server.get_watchlist("1234567")

            # Assert
            assert result["status"] == "success"
            assert isinstance(result["data"], dict)
            assert result["data"]["account"] == "1234567"
            assert len(result["data"]["stocks"]) == 1
            assert result["data"]["stocks"][0]["symbol"] == "0050"

    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    def test_get_watchlist_inventory_failure(self, mock_validate):
        mock_validate.return_value = (Mock(account="1234567"), None)

        with patch.object(server, "account_service") as mock_account_service:
            mock_account_service.get_inventory.return_value = {
                "status": "error",
                "data": None,
                "message": "API error",
            }

            server.server_state.clear_cache(f"watchlist_1234567")
            res = server.get_watchlist("1234567")
            assert res["status"] == "error"
            assert "無法獲取帳戶" in res["message"]

    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    def test_get_portfolio_summary_merge(self, mock_validate):
        mock_validate.return_value = (Mock(account="1234567"), None)

        inv = [
            {"stock_no": "2330", "quantity": 10, "cost_price": 500.0, "market_price": 520.0, "market_value": 5200},
            {"stock_no": "0050", "quantity": 5, "cost_price": 50.0, "market_price": 55.0, "market_value": 275},
        ]
        pnl = [
            {"stock_no": "2330", "unrealized_profit": 200, "unrealized_loss": 0},
            {"stock_no": "0050", "unrealized_profit": 25, "unrealized_loss": 0},
        ]

        with patch.object(server, "account_service") as mock_account_service:
            mock_account_service.get_inventory.return_value = {"status": "success", "data": inv}
            mock_account_service.get_unrealized_pnl.return_value = {"status": "success", "data": pnl}

            server.server_state.clear_cache(f"portfolio_1234567")
            result = server.get_portfolio_summary("1234567")
            assert result["status"] == "success"
            data = result["data"]
            # 2 positions
            assert data["total_positions"] == 2
            # Verify summary sums
            assert data["summary"]["total_market_value"] == 5200 + 275
            assert data["summary"]["total_unrealized_pnl"] == 225

    @patch("fubon_api_mcp_server.server.validate_and_get_account")
    def test_get_account_summary_financials(self, mock_validate):
        mock_validate.return_value = (Mock(account="1234567"), None)

        # patch account_service for bank balance and unrealized pnl
        with patch.object(server, "account_service") as mock_account_service, patch.object(
            server, "trading_service"
        ) as mock_trading_service:
            mock_account_service.get_bank_balance.return_value = {
                "status": "success",
                "data": {"balance": 100000},
            }
            mock_account_service.get_unrealized_pnl.return_value = {
                "status": "success",
                "data": [
                    {"stock_no": "2330", "unrealized_profit": 100, "unrealized_loss": 0}
                ],
            }
            mock_trading_service.get_order_results.return_value = {
                "status": "success",
                "data": [],
            }

            server.server_state.clear_cache(f"account_summary_1234567")
            result = server.get_account_summary("1234567")
            assert result["status"] == "success"
            assert result["data"]["financial_info"]["bank_balance"]["balance"] == 100000
            assert result["data"]["financial_info"]["unrealized_pnl"] == 100


if __name__ == "__main__":
    pytest.main([__file__, "-q"])