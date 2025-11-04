"""
Test correct API usage for intraday quote
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fubon_mcp import config
from fubon_neo.sdk import FubonSDK

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

print("\n測試不同的 API 調用方式:")

# Test 1: quote() with no args
try:
    print("\n1. config.reststock.intraday.quote() - no args")
    result = config.reststock.intraday.quote()
    print(f"   Success! Type: {type(result)}")
    print(f"   Result: {result}")
except Exception as e:
    print(f"   Error: {e}")

# Test 2: quote with symbol parameter
try:
    print("\n2. config.reststock.intraday.quote(symbol='2330')")
    result = config.reststock.intraday.quote(symbol='2330')
    print(f"   Success! Type: {type(result)}")
    print(f"   Result: {result}")
except Exception as e:
    print(f"   Error: {e}")

# Test 3: quote with positional symbol
try:
    print("\n3. config.reststock.intraday.quote('2330')")
    result = config.reststock.intraday.quote('2330')
    print(f"   Success! Type: {type(result)}")
    print(f"   Result: {result}")
except Exception as e:
    print(f"   Error: {e}")

# Test 4: Check if there's a different method
print("\n4. Available methods in intraday:")
for attr in dir(config.reststock.intraday):
    if not attr.startswith('_'):
        print(f"   - {attr}")
