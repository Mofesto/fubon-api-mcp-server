"""Run Phase 3 analysis against a real account without exposing trading writes."""

from __future__ import annotations

import json
import os
from unittest.mock import Mock, patch

from dotenv import load_dotenv
from fubon_neo.sdk import FubonSDK

from fubon_api_mcp_server.analysis_service import AnalysisService

WRITE_METHODS = {
    "place_order",
    "cancel_order",
    "modify_price",
    "modify_quantity",
    "batch_place_order",
    "condition_order",
}


class ReadOnlyStockClient:
    def __init__(self, stock_client):
        self._stock_client = stock_client

    def __getattr__(self, name):
        if name in WRITE_METHODS:
            raise RuntimeError(f"唯讀範例禁止存取交易寫入方法: {name}")
        return getattr(self._stock_client, name)


class ReadOnlySDK:
    def __init__(self, sdk):
        self.accounting = sdk.accounting
        self.stock = ReadOnlyStockClient(sdk.stock)


def summarize(name: str, result: dict) -> None:
    data = result.get("data") or {}
    summary = {
        "tool": name,
        "status": result.get("status"),
        "message": result.get("message"),
        "data_source": data.get("data_source"),
        "as_of": data.get("as_of"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> None:
    load_dotenv()
    required = ["FUBON_USERNAME", "FUBON_PASSWORD", "FUBON_PFX_PATH"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"缺少環境變數: {', '.join(missing)}")

    sdk = FubonSDK()
    login = sdk.login(
        os.environ["FUBON_USERNAME"],
        os.environ["FUBON_PASSWORD"],
        os.environ["FUBON_PFX_PATH"],
        os.getenv("FUBON_PFX_PASSWORD", ""),
    )
    if not login or not login.is_success or not login.data:
        raise RuntimeError("富邦 SDK 登入失敗")

    sdk.init_realtime()
    account_obj = login.data[0]
    service = AnalysisService(
        Mock(),
        ReadOnlySDK(sdk),
        [account_obj.account],
        sdk.marketdata.rest_client.stock,
        sdk.marketdata.rest_client.futopt,
    )
    try:
        summarize(
            "generate_market_sentiment_index",
            service.generate_market_sentiment_index(
                {"symbols": ["2330"], "index_components": ["technical", "volume"], "lookback_period": 60}
            ),
        )
        with patch("fubon_api_mcp_server.analysis_service.validate_and_get_account", return_value=(account_obj, None)):
            summarize(
                "calculate_portfolio_var",
                service.calculate_portfolio_var({"account": "redacted", "lookback_days": 60}),
            )
    finally:
        sdk.logout()


if __name__ == "__main__":
    main()
