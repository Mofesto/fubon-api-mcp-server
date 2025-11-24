#!/usr/bin/env python3
from unittest.mock import Mock

import pytest

from fubon_api_mcp_server.utils import normalize_item


def test_normalize_item_with_dict():
    item = {"stock_no": "2330", "quantity": 10, "cost_price": None}
    nd = normalize_item(item, ["stock_no", "quantity", "cost_price", "stock_name"])  # cost_price None should default to 0

    assert nd["stock_no"] == "2330"
    assert nd["quantity"] == 10
    assert nd["cost_price"] == 0
    assert nd["stock_name"] == ""


def test_normalize_item_with_object():
    class ItemObj:
        def __init__(self):
            self.stock_no = "0050"
            self.market_price = 55.0

    obj = ItemObj()
    nd = normalize_item(obj, ["stock_no", "market_price", "quantity"])  # qty missing -> 0

    assert nd["stock_no"] == "0050"
    assert nd["market_price"] == 55.0
    assert nd["quantity"] == 0


def test_normalize_item_with_none_values():
    item = {"stock_no": None, "quantity": None}
    nd = normalize_item(item, ["stock_no", "quantity"])  # none -> defaults

    assert nd["stock_no"] == ""
    assert nd["quantity"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
