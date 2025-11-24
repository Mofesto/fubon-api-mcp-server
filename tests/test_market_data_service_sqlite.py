import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from fubon_api_mcp_server.market_data_service import MarketDataService


class DummyMCP:
    def tool(self):
        def decorator(f):
            return f

        return decorator


def make_reststock_with_data():
    # returns simple dict response with 'data' list expected by service
    def candles(**params):
        return {
            "data": [
                {
                    "date": "2020-01-01",
                    "open": 100,
                    "high": 105,
                    "low": 95,
                    "close": 102,
                    "volume": 1000,
                },
                {
                    "date": "2020-01-02",
                    "open": 102,
                    "high": 106,
                    "low": 101,
                    "close": 104,
                    "volume": 1200,
                },
            ]
        }

    return SimpleNamespace(historical=SimpleNamespace(candles=candles))


def test_historical_candles_writes_and_reads_sqlite(tmp_path: Path):
    mcp = DummyMCP()
    reststock = make_reststock_with_data()

    # create service with empty restfutopt/sdk
    service = MarketDataService(mcp=mcp, base_data_dir=tmp_path, reststock=reststock, restfutopt=None, sdk=None)

    # call historical_candles -> should fetch from API and save to sqlite
    resp = service.historical_candles({"symbol": "2330", "from_date": "2020-01-01", "to_date": "2020-01-02"})

    assert resp["status"] == "success"
    assert isinstance(resp["data"], list) and len(resp["data"]) == 2

    # verify that local cache now returns the same records
    local = service._get_local_historical_data("2330", "2020-01-01", "2020-01-02")
    assert local is not None and local["status"] == "success"
    assert len(local["data"]) == 2

    # also assert DB file exists and contains expected rows
    db_path = service.db_path
    assert db_path.exists()

    # query sqlite directly
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM stock_historical_data WHERE symbol = ?", ("2330",))
        count = cur.fetchone()[0]
        assert count == 2
