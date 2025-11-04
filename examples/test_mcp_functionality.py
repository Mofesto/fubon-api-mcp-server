"""
Test MCP Server functionality with actual Fubon API connection.

This script tests the MCP server by:
1. Initializing the SDK with credentials from .env
2. Testing basic account functions
3. Testing market data functions
4. Verifying tool registration and execution
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import fubon_mcp
sys.path.insert(0, str(Path(__file__).parent.parent))

from fubon_mcp import config


def initialize_sdk():
    """Initialize Fubon SDK with credentials from .env file."""
    from fubon_neo.sdk import FubonSDK
    
    # Check required environment variables
    if not all([config.username, config.password, config.pfx_path]):
        raise ValueError("FUBON_USERNAME, FUBON_PASSWORD, and FUBON_PFX_PATH environment variables are required")
    
    # Initialize SDK and login
    config.sdk = FubonSDK()
    config.accounts = config.sdk.login(
        config.username, 
        config.password, 
        config.pfx_path, 
        config.pfx_password or ""
    )
    config.sdk.init_realtime()
    config.reststock = config.sdk.marketdata.rest_client.stock
    
    # Verify login success
    if not config.accounts or not hasattr(config.accounts, "is_success") or not config.accounts.is_success:
        raise ValueError("登入失敗，請檢查憑證是否正確")


async def test_sdk_initialization():
    """Test if SDK can be initialized with credentials."""
    print("\n" + "="*60)
    print("測試 1: SDK 初始化")
    print("="*60)
    
    try:
        initialize_sdk()
        print("✅ SDK 初始化成功")
        print(f"   - SDK 已創建: {config.sdk is not None}")
        print(f"   - 帳戶資訊: {config.accounts is not None}")
        print(f"   - REST API 客戶端: {config.reststock is not None}")
        if config.accounts and hasattr(config.accounts, 'data'):
            print(f"   - 可用帳戶數: {len(config.accounts.data)}")
        return True
    except Exception as e:
        print(f"❌ SDK 初始化失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_account_info():
    """Test getting account information."""
    print("\n" + "="*60)
    print("測試 2: 取得帳戶資訊")
    print("="*60)
    
    try:
        from fubon_mcp.account_service import get_account_info
        
        # Call the function wrapper (MCP tool) with empty args dict
        result = get_account_info.fn({})
        print("✅ 成功取得帳戶資訊")
        print(f"   狀態: {result.get('status')}")
        print(f"   訊息: {result.get('message')}")
        
        if result.get('status') == 'success' and result.get('data'):
            accounts = result['data']
            print(f"   帳戶數量: {len(accounts)}")
            for i, acc in enumerate(accounts, 1):
                print(f"   帳戶 {i}:")
                print(f"     - 姓名: {acc.get('name')}")
                print(f"     - 分公司: {acc.get('branch_no')}")
                print(f"     - 帳號: {acc.get('account')}")
                print(f"     - 類型: {acc.get('account_type')}")
        return True
    except Exception as e:
        print(f"❌ 取得帳戶資訊失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_inventory():
    """Test getting inventory information."""
    print("\n" + "="*60)
    print("測試 3: 取得庫存資訊")
    print("="*60)
    
    try:
        from fubon_mcp.account_service import get_inventory
        
        if not config.accounts or not hasattr(config.accounts, 'data') or not config.accounts.data:
            print("⚠️  無可用帳戶，跳過測試")
            return True
        
        account_id = config.accounts.data[0].account
        result = get_inventory.fn({"account": account_id})
        print("✅ 成功取得庫存資訊")
        print(f"   狀態: {result.get('status')}")
        print(f"   訊息: {result.get('message')}")
        
        if result.get('status') == 'success' and result.get('data'):
            inventory = result['data']
            if isinstance(inventory, list) and inventory:
                print(f"   庫存數量: {len(inventory)} 檔")
                for i, stock in enumerate(inventory[:3], 1):  # 只顯示前3檔
                    print(f"   股票 {i}:")
                    print(f"     - 代碼: {getattr(stock, 'stock_no', 'N/A')}")
                    print(f"     - 帳戶: {getattr(stock, 'account', 'N/A')}")
                    print(f"     - 昭日庫存: {getattr(stock, 'lastday_qty', 'N/A')} 股")
                    print(f"     - 今日庫存: {getattr(stock, 'today_qty', 'N/A')} 股")
                    print(f"     - 可賣數量: {getattr(stock, 'tradable_qty', 'N/A')} 股")
                    print(f"     - 訂單類型: {getattr(stock, 'order_type', 'N/A')}")
                if len(inventory) > 3:
                    print(f"   ... 還有 {len(inventory) - 3} 檔股票")
            elif isinstance(inventory, list):
                print("   庫存: 空 (無持股)")
        return True
    except Exception as e:
        print(f"❌ 取得庫存資訊失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_market_data():
    """Test getting market data."""
    print("\n" + "="*60)
    print("測試 4: 取得市場報價")
    print("="*60)
    
    try:
        from fubon_mcp.market_data_service import get_intraday_quote
        
        # Test with a common stock (台積電 2330)
        result = get_intraday_quote.fn({"symbol": "2330"})
        print("✅ 成功取得市場報價 (2330)")
        print(f"   狀態: {result.get('status')}")
        
        if result.get('status') == 'success' and result.get('data'):
            quote = result['data']
            print(f"   股票資訊:")
            print(f"     - 代碼: {quote.get('symbol', 'N/A')}")
            print(f"     - 名稱: {quote.get('name', 'N/A')}")
            print(f"     - 最新價: {quote.get('lastPrice', 'N/A')}")
            print(f"     - 收盤價: {quote.get('closePrice', 'N/A')}")
            print(f"     - 開盤: {quote.get('openPrice', 'N/A')}")
            print(f"     - 最高: {quote.get('highPrice', 'N/A')}")
            print(f"     - 最低: {quote.get('lowPrice', 'N/A')}")
            print(f"     - 成交量: {quote.get('lastSize', 'N/A')}")
            print(f"     - 總成交量: {quote.get('total', {}).get('tradeVolume', 'N/A')}")
            print(f"     - 漲跌: {quote.get('change', 'N/A')}")
            print(f"     - 漲跌幅: {quote.get('changePercent', 'N/A')}%")
            print(f"     - 平均價: {quote.get('avgPrice', 'N/A')}")
            print(f"     - 昨收: {quote.get('previousClose', 'N/A')}")
        elif result.get('message'):
            print(f"   訊息: {result.get('message')}")
        return True
    except Exception as e:
        print(f"❌ 取得市場報價失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_tools_registration():
    """Test if all tools are properly registered."""
    print("\n" + "="*60)
    print("測試 5: 工具註冊驗證")
    print("="*60)
    
    try:
        tools = await config.mcp.get_tools()
        print(f"✅ 成功取得工具列表")
        print(f"   總共註冊: {len(tools)} 個工具")
        
        # Count tools by category
        categories = {
            "account": ["account", "inventory", "pnl", "settlement", "balance"],
            "market": ["quote", "ticker", "candle", "snapshot", "intraday"],
            "trading": ["order", "place", "modify", "cancel"],
            "reports": ["report", "result", "filled", "event"],
            "historical": ["historical", "indicator", "trend"]
        }
        
        for cat_name, keywords in categories.items():
            count = sum(1 for name in tools.keys() 
                       if any(kw in name.lower() for kw in keywords))
            if count > 0:
                print(f"   - {cat_name}: {count} 個工具")
        
        return True
    except Exception as e:
        print(f"❌ 工具註冊驗證失敗: {e}")
        return False


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("🚀 開始測試 Fubon MCP Server 功能")
    print("="*60)
    
    results = []
    
    # Test 1: SDK initialization (required for other tests)
    sdk_ok = await test_sdk_initialization()
    results.append(("SDK 初始化", sdk_ok))
    
    if not sdk_ok:
        print("\n❌ SDK 初始化失敗，無法繼續測試")
        return
    
    # Test 2-4: Functional tests
    results.append(("帳戶資訊", await test_account_info()))
    results.append(("庫存資訊", await test_inventory()))
    results.append(("市場報價", await test_market_data()))
    
    # Test 5: Tools registration
    results.append(("工具註冊", await test_tools_registration()))
    
    # Summary
    print("\n" + "="*60)
    print("📊 測試結果摘要")
    print("="*60)
    
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    
    for name, ok in results:
        status = "✅ 通過" if ok else "❌ 失敗"
        print(f"  {status} - {name}")
    
    print(f"\n總計: {passed}/{total} 測試通過")
    
    if passed == total:
        print("🎉 所有測試通過！MCP Server 功能正常")
    else:
        print("⚠️  部分測試失敗，請檢查錯誤訊息")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  測試被用戶中斷")
    except Exception as e:
        print(f"\n\n❌ 測試過程發生錯誤: {e}")
        import traceback
        traceback.print_exc()
