#!/usr/bin/env python3
"""
富邦 API MCP Server - 技術指標真實數據測試

此腳本用於測試技術指標計算功能，使用真實的市場數據。
包含完整的真實數據測試案例，展示如何在實際市場數據上計算技術指標。

⚠️ 重要注意事項：
- 此腳本會調用真實的富邦 API 獲取市場數據
- 需要正確的環境變數設定
- 會產生網路請求和 API 調用
- 請確保有足夠的 API 調用額度

使用前準備：
1. 設定環境變數：
   - FUBON_USERNAME=您的帳號
   - FUBON_PASSWORD=您的密碼
   - FUBON_PFX_PATH=PFX憑證檔案路徑
   - FUBON_PFX_PASSWORD=PFX密碼（可選）

2. 安裝依賴：
   pip install python-dotenv fubon-neo mcp

3. 運行測試：
   python examples/indicators_real_test.py

測試涵蓋範圍：
- 移動平均指標 (SMA, EMA, WMA)
- 波段指標 (Bollinger Bands)
- 動量指標 (RSI, Williams %R, CCI, ROC)
- 趨勢指標 (MACD, ADX)
- 波動率指標 (ATR)
- 成交量指標 (OBV, Volume Rate)
- 隨機指標 (KD)
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# 添加專案根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加載環境變數
load_dotenv()

from fubon_neo.sdk import FubonSDK

from fubon_api_mcp_server.config import config
from fubon_api_mcp_server.indicators import (
    calculate_adx,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_cci,
    calculate_ema,
    calculate_kd,
    calculate_macd,
    calculate_obv,
    calculate_roc,
    calculate_rsi,
    calculate_sma,
    calculate_volume_rate,
    calculate_williams_r,
    calculate_wma,
)
from fubon_api_mcp_server.market_data_service import MarketDataService


def print_section(title: str):
    """列印區段標題"""
    print(f"\n{'='*70}")
    print(f"🧪 {title}")
    print("=" * 70)


def print_indicator_result(indicator_name: str, result, symbol: str):
    """列印指標計算結果"""
    print(f"\n📊 {indicator_name} ({symbol})")

    if isinstance(result, dict):
        for key, value in result.items():
            if hasattr(value, "iloc") and len(value) > 0:
                latest_value = value.iloc[-1]
                if pd.notna(latest_value):
                    print(f"   {key}: {latest_value:.4f}")
                else:
                    print(f"   {key}: NaN (數據不足)")
            else:
                print(f"   {key}: {value}")
    else:
        if hasattr(result, "iloc") and len(result) > 0:
            latest_value = result.iloc[-1]
            if pd.notna(latest_value):
                print(f"   最新值: {latest_value:.4f}")
            else:
                print(f"   最新值: NaN (數據不足)")
        else:
            print(f"   結果: {result}")


def run_indicator_test(indicator_name: str, indicator_func, data_dict: dict, symbol: str, *args, **kwargs):
    """運行單個指標測試"""
    try:
        print(f"\n🔍 計算指標: {indicator_name}")

        # 根據指標函數需要的參數準備數據
        if indicator_name in ["SMA", "EMA", "WMA", "RSI", "ROC"]:
            result = indicator_func(data_dict["close"], *args, **kwargs)
        elif indicator_name == "Bollinger Bands":
            result = indicator_func(data_dict["close"], *args, **kwargs)
        elif indicator_name in ["Williams %R", "CCI", "ATR", "ADX"]:
            result = indicator_func(data_dict["high"], data_dict["low"], data_dict["close"], *args, **kwargs)
        elif indicator_name == "MACD":
            result = indicator_func(data_dict["close"], *args, **kwargs)
        elif indicator_name == "OBV":
            result = indicator_func(data_dict["close"], data_dict["volume"])
        elif indicator_name == "Volume Rate":
            result = indicator_func(data_dict["volume"], *args, **kwargs)
        elif indicator_name == "KD":
            result = indicator_func(data_dict["high"], data_dict["low"], data_dict["close"], *args, **kwargs)
        else:
            result = indicator_func(data_dict["close"], *args, **kwargs)

        print_indicator_result(indicator_name, result, symbol)
        return {"status": "success", "result": result}

    except Exception as e:
        error_msg = f"指標計算失敗: {str(e)}"
        print(f"❌ {indicator_name}: {error_msg}")
        return {"status": "error", "message": error_msg}


def main():
    """主測試函數"""
    print("🚀 富邦 API MCP Server - 技術指標真實數據測試")
    print("=" * 70)
    print(f"⏰ 測試開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. 環境檢查
    print_section("環境檢查")
    required_env = ["FUBON_USERNAME", "FUBON_PASSWORD", "FUBON_PFX_PATH"]
    missing_env = [env for env in required_env if not os.getenv(env)]

    if missing_env:
        print(f"❌ 缺少必要的環境變數: {missing_env}")
        print("\n請設定以下環境變數：")
        for env in missing_env:
            print(f"   export {env}=<您的{env.replace('FUBON_', '')}>")
        print("\n💡 提示：您也可以在 .env 檔案中設定這些變數")
        return

    print("✅ 環境變數檢查通過")

    # 2. 初始化 SDK
    print_section("SDK 初始化")
    try:
        sdk = FubonSDK()
        accounts = sdk.login(config.username, config.password, config.pfx_path, config.pfx_password or "")

        if not accounts or not hasattr(accounts, "is_success") or not accounts.is_success:
            print("❌ SDK 登入失敗")
            if hasattr(accounts, "message"):
                print(f"   錯誤訊息: {accounts.message}")
            return

        print(f"✅ SDK 初始化成功，獲取到 {len(accounts.data)} 個帳戶")

        # 初始化即時資料連線
        sdk.init_realtime()
        print("✅ 即時資料連線初始化成功")

        # 初始化 REST 客戶端
        reststock = sdk.marketdata.rest_client.stock
        restfutopt = sdk.marketdata.rest_client.futopt

        if reststock is None:
            print("❌ 股票行情服務未初始化")
            return

        print("✅ REST 客戶端初始化成功")

    except Exception as e:
        print(f"❌ SDK 初始化失敗: {e}")
        import traceback

        traceback.print_exc()
        return

    # 3. 初始化 Market Data Service
    print_section("Market Data Service 初始化")
    try:
        # 創建模擬 MCP 實例
        class MockMCP:
            def tool(self):
                def decorator(func):
                    return func

                return decorator

        mock_mcp = MockMCP()
        base_data_dir = config.BASE_DATA_DIR
        base_data_dir.mkdir(exist_ok=True)

        market_data_service = MarketDataService(mock_mcp, base_data_dir, reststock, restfutopt, sdk)
        print("✅ Market Data Service 初始化成功")

    except Exception as e:
        print(f"❌ Market Data Service 初始化失敗: {e}")
        import traceback

        traceback.print_exc()
        return

    # 4. 獲取真實市場數據
    print_section("獲取真實市場數據")

    test_symbol = "2330"  # 台積電
    end_date = datetime.now()
    start_date = end_date - timedelta(days=120)  # 獲取120天的數據

    print(f"📈 獲取 {test_symbol} 的歷史數據 ({start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')})")

    try:
        result = market_data_service.historical_candles(
            {"symbol": test_symbol, "from_date": start_date.strftime("%Y-%m-%d"), "to_date": end_date.strftime("%Y-%m-%d")}
        )

        if result.get("status") != "success" or len(result.get("data", [])) < 50:
            print(f"❌ 獲取歷史數據失敗或數據點不足: {result.get('message', '未知錯誤')}")
            print("❌ insufficient_data：真實行情不足，停止測試，不使用模擬資料補值")
            return
        else:
            data = result.get("data", [])
            if not data:
                print("❌ 沒有獲取到歷史數據")
                return

            print(f"✅ 成功獲取 {len(data)} 筆歷史數據")

            # 轉換為 DataFrame 格式
            df = pd.DataFrame(data)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")

            # 準備指標計算所需的數據
            market_data = {"close": df["close"], "high": df["high"], "low": df["low"], "volume": df["volume"]}

            print(f"📊 數據範圍: {df['date'].min()} 至 {df['date'].max()}")
            print(f"📊 數據筆數: {len(df)}")
            print(f"📊 價格範圍: {df['close'].min():.2f} - {df['close'].max():.2f}")

    except Exception as e:
        print(f"❌ 數據獲取失敗: {e}")
        import traceback

        traceback.print_exc()
        return

    # 5. 執行指標測試
    test_results = []

    print_section("技術指標計算測試")

    # 5.1 移動平均指標
    print("\n📈 移動平均指標測試")

    test_results.append(run_indicator_test("SMA", calculate_sma, market_data, test_symbol, period=20))
    test_results.append(run_indicator_test("EMA", calculate_ema, market_data, test_symbol, period=20))
    test_results.append(run_indicator_test("WMA", calculate_wma, market_data, test_symbol, period=20))

    # 5.2 波段指標
    print("\n📊 波段指標測試")

    test_results.append(
        run_indicator_test("Bollinger Bands", calculate_bollinger_bands, market_data, test_symbol, period=20, stddev=2.0)
    )

    # 5.3 動量指標
    print("\n💹 動量指標測試")

    test_results.append(run_indicator_test("RSI", calculate_rsi, market_data, test_symbol, period=14))
    test_results.append(run_indicator_test("Williams %R", calculate_williams_r, market_data, test_symbol, period=14))
    test_results.append(run_indicator_test("CCI", calculate_cci, market_data, test_symbol, period=20))
    test_results.append(run_indicator_test("ROC", calculate_roc, market_data, test_symbol, period=10))

    # 5.4 趨勢指標
    print("\n📉 趨勢指標測試")

    test_results.append(run_indicator_test("MACD", calculate_macd, market_data, test_symbol, fast=12, slow=26, signal=9))
    test_results.append(run_indicator_test("ADX", calculate_adx, market_data, test_symbol, period=14))

    # 5.5 波動率指標
    print("\n📊 波動率指標測試")

    test_results.append(run_indicator_test("ATR", calculate_atr, market_data, test_symbol, period=14))

    # 5.6 成交量指標
    print("\n📦 成交量指標測試")

    test_results.append(run_indicator_test("OBV", calculate_obv, market_data, test_symbol))
    test_results.append(run_indicator_test("Volume Rate", calculate_volume_rate, market_data, test_symbol, period=20))

    # 5.7 隨機指標
    print("\n🎯 隨機指標測試")

    test_results.append(run_indicator_test("KD", calculate_kd, market_data, test_symbol, period=9, smooth_k=3, smooth_d=3))

    # 6. 測試總結
    print_section("測試總結")

    successful_tests = 0
    failed_tests = 0

    print("📊 指標計算結果詳情：")
    for i, result in enumerate(test_results, 1):
        status = result.get("status", "unknown")
        if status == "success":
            successful_tests += 1
            print(f"   ✅ 指標 {i}: 計算成功")
        else:
            failed_tests += 1
            print(f"   ❌ 指標 {i}: {result.get('message', '未知錯誤')}")

    print(f"\n🎯 測試統計:")
    print(f"   總指標數: {len(test_results)}")
    print(f"   計算成功: {successful_tests}")
    print(f"   計算失敗: {failed_tests}")
    print(f"   成功率: {(successful_tests / len(test_results) * 100):.1f}%")

    print(f"\n⏰ 測試結束時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if failed_tests == 0:
        print("\n🎉 所有指標計算都成功了！")
        print(f"💡 測試數據: {test_symbol} 股票 {len(df)} 筆歷史數據")
        print("💡 所有指標都基於 TA-Lib 實現，提供專業的技術分析功能")
    else:
        print(f"\n⚠️  有 {failed_tests} 個指標計算失敗，請檢查上面的詳細資訊")

    print("\n💡 使用提示：")
    print("   • 指標計算需要足夠的歷史數據，建議至少 50 個數據點")
    print("   • NaN 值表示該時間點無法計算指標（數據不足）")
    print("   • 可配合 pandas 和 matplotlib 進行可視化分析")
    print("   • 真實市場數據可能因交易時段而有所差異")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用戶中斷測試執行")
    except Exception as e:
        print(f"\n\n❌ 測試過程中發生未預期的錯誤: {e}")
        import traceback

        traceback.print_exc()
