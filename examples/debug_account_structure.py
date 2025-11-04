"""
Debug script to check the actual structure of config.accounts
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

print("\n" + "="*60)
print("檢查 config.accounts 的結構")
print("="*60)

print(f"\n1. config.accounts 類型: {type(config.accounts)}")
print(f"2. config.accounts 是否為 None: {config.accounts is None}")

if config.accounts:
    print(f"3. hasattr 'is_success': {hasattr(config.accounts, 'is_success')}")
    if hasattr(config.accounts, 'is_success'):
        print(f"   - is_success 值: {config.accounts.is_success}")
    
    print(f"4. hasattr 'data': {hasattr(config.accounts, 'data')}")
    if hasattr(config.accounts, 'data'):
        print(f"   - data 類型: {type(config.accounts.data)}")
        print(f"   - data 值: {config.accounts.data}")
    
    print(f"5. hasattr 'accounts': {hasattr(config.accounts, 'accounts')}")
    if hasattr(config.accounts, 'accounts'):
        print(f"   - accounts 類型: {type(config.accounts.accounts)}")
        print(f"   - accounts 長度: {len(config.accounts.accounts) if config.accounts.accounts else 0}")
        if config.accounts.accounts:
            print(f"   - 第一個帳戶: {config.accounts.accounts[0]}")
            print(f"   - 第一個帳戶類型: {type(config.accounts.accounts[0])}")
            acc = config.accounts.accounts[0]
            print(f"   - 帳戶屬性:")
            for attr in dir(acc):
                if not attr.startswith('_'):
                    print(f"     - {attr}: {getattr(acc, attr, 'N/A')}")
    
    print(f"\n6. 所有屬性:")
    for attr in dir(config.accounts):
        if not attr.startswith('_'):
            print(f"   - {attr}: {getattr(config.accounts, attr, 'N/A')}")
