"""
Debug script to test get_account_info directly
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fubon_mcp import config
from fubon_neo.sdk import FubonSDK
from fubon_mcp.account_service import get_account_info

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
print("測試 get_account_info 函數")
print("="*60)

# Call get_account_info with empty args
print("\n1. 調用 get_account_info.fn({})")
result = get_account_info.fn({})

print(f"\n2. 返回結果:")
print(f"   - status: {result.get('status')}")
print(f"   - message: {result.get('message')}")
print(f"   - data: {result.get('data')}")

if result.get('data'):
    print(f"\n3. 數據詳情:")
    if isinstance(result['data'], list):
        print(f"   - 類型: list")
        print(f"   - 長度: {len(result['data'])}")
        for i, acc in enumerate(result['data']):
            print(f"   - 帳戶 {i+1}: {acc}")
    else:
        print(f"   - 類型: {type(result['data'])}")
        print(f"   - 內容: {result['data']}")

print("\n" + "="*60)
print("檢查 _get_all_accounts_basic_info 內部邏輯")
print("="*60)

print(f"\n1. config.accounts 存在: {config.accounts is not None}")
print(f"2. hasattr 'is_success': {hasattr(config.accounts, 'is_success')}")
if hasattr(config.accounts, 'is_success'):
    print(f"   - is_success: {config.accounts.is_success}")

print(f"3. hasattr 'data': {hasattr(config.accounts, 'data')}")
if hasattr(config.accounts, 'data'):
    print(f"   - data 類型: {type(config.accounts.data)}")
    print(f"   - data 內容: {config.accounts.data}")
    if config.accounts.data:
        print(f"   - data 長度: {len(config.accounts.data)}")
        for i, acc in enumerate(config.accounts.data):
            print(f"\n   帳戶 {i+1}:")
            print(f"   - name: {getattr(acc, 'name', 'N/A')}")
            print(f"   - branch_no: {getattr(acc, 'branch_no', 'N/A')}")
            print(f"   - account: {getattr(acc, 'account', 'N/A')}")
            print(f"   - account_type: {getattr(acc, 'account_type', 'N/A')}")
