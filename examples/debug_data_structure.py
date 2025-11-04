"""
Debug script to check actual data structure returned
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fubon_mcp import config
from fubon_neo.sdk import FubonSDK
from fubon_mcp.account_service import get_inventory
from fubon_mcp.market_data_service import get_intraday_quote

# Initialize SDK
print("正在初始化 SDK...")
config.sdk = FubonSDK()
config.accounts = config.sdk.login(
    config.username, 
    config.password, 
    config.pfx_path, 
    config.pfx_password or ""
)
config.sdk.init_realtime()
config.reststock = config.sdk.marketdata.rest_client.stock

print("\n" + "="*60)
print("測試 1: 庫存資訊結構")
print("="*60)

account_id = config.accounts.data[0].account
result = get_inventory.fn({"account": account_id})

print(f"\nResult status: {result.get('status')}")
print(f"Result message: {result.get('message')}")
print(f"Result data type: {type(result.get('data'))}")

if result.get('data'):
    inventory = result['data']
    print(f"Inventory length: {len(inventory)}")
    if inventory:
        print(f"\nFirst item type: {type(inventory[0])}")
        print(f"First item: {inventory[0]}")
        print(f"\nFirst item attributes:")
        for attr in dir(inventory[0]):
            if not attr.startswith('_'):
                print(f"  - {attr}: {getattr(inventory[0], attr, 'N/A')}")

print("\n" + "="*60)
print("測試 2: 市場報價結構")
print("="*60)

result = get_intraday_quote.fn({"symbol": "2330"})

print(f"\nResult status: {result.get('status')}")
print(f"Result message: {result.get('message')}")
print(f"Result data type: {type(result.get('data'))}")

if result.get('data'):
    quote = result['data']
    print(f"Quote type: {type(quote)}")
    print(f"Quote: {quote}")
