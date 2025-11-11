#!/usr/bin/env python3
"""
富邦證券MCP服務器功能驗證腳本

使用真實的.env配置來驗證server.py中的所有主要功能是否正常工作。
這個腳本會模擬實際使用場景，測試各個組件的功能。
"""

import json
import os
import sys
from pathlib import Path

# 添加項目根目錄到Python路徑
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def load_env_file():
    """載入.env文件"""
    env_path = project_root / ".env"
    if not env_path.exists():
        print("❌ .env文件不存在")
        return False

    from dotenv import load_dotenv
    load_dotenv(env_path)
    print("✅ 已載入.env配置")
    return True

def test_imports():
    """測試所有必要的模組導入"""
    try:
        # 測試基本導入
        from fubon_api_mcp_server.server import mcp, server_state
        from fubon_api_mcp_server.config import config
        from fubon_api_mcp_server.utils import validate_and_get_account
        from fubon_api_mcp_server.enums import to_bs_action, to_market_type

        print("✅ 所有模組導入成功")
        return True
    except Exception as e:
        print(f"❌ 模組導入失敗: {e}")
        return False

def test_config_loading():
    """測試配置載入"""
    try:
        from fubon_api_mcp_server.config import config

        required_keys = ['username', 'password', 'pfx_path']

        for key in required_keys:
            if not getattr(config, key, None):
                print(f"❌ 配置缺少必要字段: {key}")
                return False

        print("✅ 配置載入成功")
        print(f"   - 用戶名: {config.username}")
        print(f"   - PFX路徑: {config.pfx_path}")
        return True
    except Exception as e:
        print(f"❌ 配置載入失敗: {e}")
        return False

def test_server_initialization():
    """測試服務器初始化"""
    try:
        from fubon_api_mcp_server.server import server_state

        # 測試SDK初始化（實際登入）
        success = server_state.initialize_sdk(
            os.getenv('FUBON_USERNAME'),
            os.getenv('FUBON_PASSWORD'),
            os.getenv('FUBON_PFX_PATH'),
            os.getenv('FUBON_PFX_PASSWORD') or ""
        )

        if success:
            print("✅ SDK初始化和登入成功")
            print(f"   - 帳戶數量: {len(server_state.accounts) if hasattr(server_state.accounts, '__len__') else '未知'}")
            return True
        else:
            print("❌ SDK初始化或登入失敗")
            print("   請檢查 .env 配置和憑證文件")
            return False

    except Exception as e:
        print(f"❌ 服務器初始化失敗: {e}")
        return False

def test_mcp_tools():
    """測試MCP工具註冊"""
    try:
        import asyncio
        from fubon_api_mcp_server.server import mcp

        async def check_tools():
            tools = await mcp.list_tools()
            tool_names = [tool.name for tool in tools]

            # 檢查關鍵工具是否存在
            essential_tools = [
                'get_realtime_quotes',
                'place_order',
                'get_account_info',
                'get_inventory'
            ]

            missing_tools = []
            for tool in essential_tools:
                if tool not in tool_names:
                    missing_tools.append(tool)

            if missing_tools:
                print(f"❌ 缺少必要工具: {missing_tools}")
                return False

            print(f"✅ MCP工具註冊成功，共 {len(tools)} 個工具")
            print(f"   - 關鍵工具: {essential_tools}")
            return True

        return asyncio.run(check_tools())

    except Exception as e:
        print(f"❌ MCP工具測試失敗: {e}")
        return False

def test_data_processing():
    """測試數據處理功能"""
    try:
        from fubon_api_mcp_server.indicators import calculate_bollinger_bands, calculate_rsi
        import pandas as pd
        import numpy as np

        # 創建測試數據
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        prices = np.random.normal(100, 10, 100)
        df = pd.DataFrame({'close': prices}, index=dates)

        # 測試技術指標計算
        bb = calculate_bollinger_bands(df['close'])
        rsi = calculate_rsi(df['close'])

        if not bb or not rsi.any():
            print("❌ 技術指標計算失敗")
            return False

        print("✅ 數據處理功能正常")
        print(f"   - Bollinger Bands計算成功: {len(bb['upper'])} 筆數據")
        print(f"   - RSI計算成功: {len(rsi)} 筆數據")
        return True

    except Exception as e:
        print(f"❌ 數據處理測試失敗: {e}")
        return False

def test_market_data_subscription():
    """測試市場數據訂閱"""
    try:
        from fubon_api_mcp_server.server import server_state

        # 測試訂閱股票報價
        stream_id = server_state.subscribe_market_data("2330", "quote")

        if stream_id:
            print("✅ 市場數據訂閱成功")
            print(f"   - Stream ID: {stream_id}")

            # 測試取消訂閱
            success = server_state.unsubscribe_market_data(stream_id)
            if success:
                print("✅ 取消訂閱成功")
            else:
                print("❌ 取消訂閱失敗")

            return True
        else:
            print("❌ 市場數據訂閱失敗")
            print("   請檢查網路連線和市場狀態")
            return False

    except Exception as e:
        print(f"❌ 市場數據訂閱測試失敗: {e}")
        return False

def test_json_serialization():
    """測試JSON序列化功能"""
    try:
        # 測試json.dumps的使用
        test_data = {
            "symbol": "2330",
            "price": 500.0,
            "volume": 1000,
            "timestamp": "2024-01-01T10:00:00"
        }

        json_str = json.dumps(test_data, ensure_ascii=False, indent=2)
        parsed_data = json.loads(json_str)

        if parsed_data != test_data:
            print("❌ JSON序列化測試失敗")
            return False

        print("✅ JSON序列化功能正常")
        return True

    except Exception as e:
        print(f"❌ JSON序列化測試失敗: {e}")
        return False

def test_file_operations():
    """測試檔案操作"""
    try:
        from fubon_api_mcp_server.server import read_local_stock_data, save_to_local_csv

        # 測試本地數據讀取
        data = read_local_stock_data("2330")
        print(f"✅ 本地數據讀取功能正常 (2330數據: {'存在' if data is not None else '不存在'})")

        # 測試數據保存（創建測試數據）
        test_data = [
            {"date": "2024-01-01", "open": 100, "high": 105, "low": 95, "close": 102, "volume": 1000}
        ]
        save_to_local_csv("TEST", test_data)
        print("✅ 數據保存功能正常")

        return True

    except Exception as e:
        print(f"❌ 檔案操作測試失敗: {e}")
        return False

def main():
    """主測試函數"""
    print("🚀 開始富邦證券MCP服務器功能驗證...")
    print("=" * 50)

    tests = [
        ("環境變數載入", load_env_file),
        ("模組導入", test_imports),
        ("配置載入", test_config_loading),
        ("服務器初始化", test_server_initialization),
        ("市場數據訂閱", test_market_data_subscription),
        ("MCP工具註冊", test_mcp_tools),
        ("數據處理", test_data_processing),
        ("JSON序列化", test_json_serialization),
        ("檔案操作", test_file_operations),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n🧪 測試: {test_name}")
        if test_func():
            passed += 1
        else:
            print(f"   測試 '{test_name}' 失敗")

    print("\n" + "=" * 50)
    print(f"📊 測試結果: {passed}/{total} 通過")

    if passed == total:
        print("🎉 所有功能驗證通過！富邦證券MCP服務器準備就緒。")
        return True
    else:
        print("❌ 部分功能驗證失敗，請檢查相關配置和代碼。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)