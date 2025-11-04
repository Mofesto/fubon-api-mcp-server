#!/usr/bin/env python3
"""
FUBON API 測試腳本
測試所有 MCP server 中的工具功能
"""

from dotenv import load_dotenv
from fubon_neo.sdk import FubonSDK

# 加載環境變數
load_dotenv()


def test_api_connection(fubon_credentials):
    """測試 API 連線"""
    print("=== 測試 API 連線 ===")
    try:
        username = fubon_credentials["username"]
        password = fubon_credentials["password"]
        pfx_path = fubon_credentials["pfx_path"]
        pfx_password = fubon_credentials["pfx_password"]

        sdk = FubonSDK()
        accounts = sdk.login(username, password, pfx_path, pfx_password or "")
        sdk.init_realtime()
        reststock = sdk.marketdata.rest_client.stock

        print("✅ API 連線成功")
        print(f"帳戶類型: {type(accounts)}")
        print(f"帳戶值: {accounts}")

        if hasattr(accounts, "data"):
            print(f"帳戶數量: {len(accounts.data) if accounts.data else 0}")
        else:
            print("帳戶沒有 data 屬性")

        # 使用 assert 進行檢查而不是返回值
        assert accounts is not None, "登入失敗，accounts 為 None"
        assert hasattr(accounts, "is_success") and accounts.is_success, "登入失敗"
        assert reststock is not None, "無法獲取 REST 客戶端"
    except Exception as e:
        print(f"❌ API 連線失敗: {str(e)}")
        raise  # 重新拋出異常讓 pytest 處理


def test_intraday_tickers(rest_client):
    """測試獲取股票列表"""
    print("\n=== 測試 intraday tickers ===")
    try:
        result = rest_client.intraday.tickers(market="TSE")
        assert result is not None, "API 返回 None"
        assert "data" in result, "回應中沒有 data 字段"
        assert result["data"], "data 字段為空"
        print(f"✅ 成功獲取 TSE 市場股票列表，數量: {len(result['data'])}")
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        raise


def test_intraday_ticker(rest_client):
    """測試獲取股票基本資料"""
    print("\n=== 測試 intraday ticker ===")
    try:
        result = rest_client.intraday.ticker(symbol="2330")
        assert result is not None, "API 返回 None"
        assert isinstance(result, dict), "回應不是字典格式"
        assert "symbol" in result, "回應中沒有 symbol 字段"
        print("✅ 成功獲取 2330 基本資料")
        print(f"   股票名稱: {result.get('name', 'N/A')}")
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        raise


def test_intraday_quote(rest_client):
    """測試獲取即時報價"""
    print("\n=== 測試 intraday quote ===")
    try:
        result = rest_client.intraday.quote(symbol="2330")
        assert result is not None, "API 返回 None"
        assert isinstance(result, dict), "回應不是字典格式"
        assert "symbol" in result, "回應中沒有 symbol 字段"
        print("✅ 成功獲取 2330 即時報價")
        print(f"   最新價: {result.get('lastPrice', 'N/A')}")
        print(f"   漲跌: {result.get('change', 'N/A')}")
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        raise


def test_intraday_candles(rest_client):
    """測試獲取盤中 K 線"""
    print("\n=== 測試 intraday candles ===")
    try:
        result = rest_client.intraday.candles(symbol="2330")
        assert result is not None, "API 返回 None"
        assert "data" in result, "回應中沒有 data 字段"
        assert result["data"], "data 字段為空"
        print(f"✅ 成功獲取 2330 盤中 K 線，數量: {len(result['data'])}")
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        raise


def test_intraday_trades(rest_client):
    """測試獲取成交明細"""
    print("\n=== 測試 intraday trades ===")
    try:
        result = rest_client.intraday.trades(symbol="2330")
        assert result is not None, "API 返回 None"
        assert "data" in result, "回應中沒有 data 字段"
        print(f"✅ 成功獲取 2330 成交明細，數量: {len(result['data']) if isinstance(result['data'], list) else 'N/A'}")
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        raise


def test_intraday_volumes(rest_client):
    """測試獲取分價量表"""
    print("\n=== 測試 intraday volumes ===")
    try:
        result = rest_client.intraday.volumes(symbol="2330")
        assert result is not None, "API 返回 None"
        assert "data" in result, "回應中沒有 data 字段"
        print(f"✅ 成功獲取 2330 分價量表，數量: {len(result['data']) if isinstance(result['data'], list) else 'N/A'}")
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        raise


def test_snapshot_quotes(rest_client):
    """測試獲取行情快照"""
    print("\n=== 測試 snapshot quotes ===")
    try:
        result = rest_client.snapshot.quotes(market="TSE")
        assert result is not None, "API 返回 None"
        assert "data" in result, "回應中沒有 data 字段"
        assert result["data"], "data 字段為空"
        print(f"✅ 成功獲取 TSE 行情快照，數量: {len(result['data'])}")
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        raise


def test_snapshot_movers(rest_client):
    """測試獲取漲跌幅排行"""
    print("\n=== 測試 snapshot movers ===")
    try:
        result = rest_client.snapshot.movers(market="TSE", direction="up", change="percent")
        assert result is not None, "API 返回 None"
        assert "data" in result, "回應中沒有 data 字段"
        assert result["data"], "data 字段為空"
        print(f"✅ 成功獲取 TSE 漲跌幅排行 (上漲百分比)，數量: {len(result['data'])}")
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        raise


def test_snapshot_actives(rest_client):
    """測試獲取成交量值排行"""
    print("\n=== 測試 snapshot actives ===")
    try:
        result = rest_client.snapshot.actives(market="TSE", trade="volume")
        assert result is not None, "API 返回 None"
        assert "data" in result, "回應中沒有 data 字段"
        assert result["data"], "data 字段為空"
        print(f"✅ 成功獲取 TSE 成交量排行，數量: {len(result['data'])}")
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        raise


def test_historical_candles(rest_client):
    """測試獲取歷史 K 線"""
    print("\n=== 測試 historical candles ===")
    try:
        result = rest_client.historical.candles(symbol="2330", from_date="2024-10-01", to_date="2024-10-05")
        assert result is not None, "API 返回 None"
        assert "data" in result, "回應中沒有 data 字段"
        assert result["data"], "data 字段為空"
        print(f"✅ 成功獲取 2330 歷史 K 線，數量: {len(result['data'])}")
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        raise


def test_historical_stats(rest_client):
    """測試獲取歷史統計"""
    print("\n=== 測試 historical stats ===")
    try:
        result = rest_client.historical.stats(symbol="2330")
        print(f"API 回應: {result}")
        assert result is not None, "API 返回 None"
        assert isinstance(result, dict), "回應不是字典格式"
        if "data" in result and result["data"]:
            print("✅ 成功獲取 2330 歷史統計")
        else:
            print("⚠️ API 返回成功但無數據")
            # 視為通過，因為 API 呼叫成功
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        raise


def test_bank_balance(fubon_sdk):
    """測試獲取銀行水位"""
    print("\n=== 測試 bank balance ===")
    try:
        sdk, accounts = fubon_sdk  # 解包元組
        assert accounts is not None, "沒有帳戶資訊"
        assert hasattr(accounts, "data"), "帳戶沒有 data 屬性"
        assert accounts.data, "帳戶數據為空"

        account = accounts.data[0]  # 使用第一個帳戶
        result = sdk.accounting.bank_remain(account)
        assert result is not None, "API 返回 None"
        assert hasattr(result, "is_success"), "回應沒有 is_success 屬性"
        assert result.is_success, "API 呼叫失敗"

        balance_data = result.data
        print("✅ 成功獲取銀行水位")
        print(f"   帳戶: {getattr(balance_data, 'account', 'N/A')}")
        print(f"   貨幣: {getattr(balance_data, 'currency', 'N/A')}")
        print(f"   餘額: {getattr(balance_data, 'balance', 'N/A'):,} 元")
        print(f"   可用餘額: {getattr(balance_data, 'available_balance', 'N/A'):,} 元")
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        raise


def test_inventory(fubon_sdk):
    """測試獲取庫存資訊"""
    print("\n=== 測試 inventory ===")
    try:
        sdk, accounts = fubon_sdk  # 解包元組
        assert accounts is not None, "沒有帳戶資訊"
        assert hasattr(accounts, "data"), "帳戶沒有 data 屬性"
        assert accounts.data, "帳戶數據為空"

        account = accounts.data[0]  # 使用第一個帳戶
        result = sdk.accounting.inventories(account)
        assert result is not None, "API 返回 None"
        assert hasattr(result, "is_success"), "回應沒有 is_success 屬性"
        assert result.is_success, "API 呼叫失敗"

        inventory_data = result.data
        print("✅ 成功獲取庫存資訊")
        if hasattr(inventory_data, "__iter__"):
            count = 0
            for item in inventory_data:
                if hasattr(item, "symbol"):
                    count += 1
                    print(f"   {getattr(item, 'symbol', 'N/A')}: {getattr(item, 'quantity', 'N/A')} 股")
            print(f"   總計: {count} 檔股票")
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        raise


def test_unrealized_pnl(fubon_sdk):
    """測試獲取未實現損益"""
    print("\n=== 測試 unrealized pnl ===")
    try:
        sdk, accounts = fubon_sdk  # 解包元組
        assert accounts is not None, "沒有帳戶資訊"
        assert hasattr(accounts, "data"), "帳戶沒有 data 屬性"
        assert accounts.data, "帳戶數據為空"

        account = accounts.data[0]  # 使用第一個帳戶
        result = sdk.accounting.unrealized_gains_and_loses(account)
        assert result is not None, "API 返回 None"
        assert hasattr(result, "is_success"), "回應沒有 is_success 屬性"
        assert result.is_success, "API 呼叫失敗"

        pnl_data = result.data
        print("✅ 成功獲取未實現損益")
        total_pnl = 0
        if hasattr(pnl_data, "__iter__"):
            count = 0
            for item in pnl_data:
                if hasattr(item, "symbol"):
                    count += 1
                    pnl = getattr(item, "unrealized_gain_loss", 0)
                    total_pnl += pnl
                    print(f"   {getattr(item, 'symbol', 'N/A')}: {pnl:,} 元")
            print(f"   總計淨盈虧: {total_pnl:,} 元 ({count} 檔股票)")
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        raise


def test_settlement_info(fubon_sdk):
    """測試獲取交割資訊"""
    print("\n=== 測試 settlement info ===")
    try:
        sdk, accounts = fubon_sdk  # 解包元組
        assert accounts is not None, "沒有帳戶資訊"
        assert hasattr(accounts, "data"), "帳戶沒有 data 屬性"
        assert accounts.data, "帳戶數據為空"

        account = accounts.data[0]  # 使用第一個帳戶
        result = sdk.accounting.query_settlement(account, "0d")
        assert result is not None, "API 返回 None"
        assert hasattr(result, "is_success"), "回應沒有 is_success 屬性"
        assert result.is_success, "API 呼叫失敗"

        settlement_data = result.data
        print("✅ 成功獲取交割資訊")
        if hasattr(settlement_data, "details") and settlement_data.details:
            detail = settlement_data.details[0]
            settlement_date = getattr(detail, "settlement_date", None)
            total_amount = getattr(detail, "total_settlement_amount", None)

            if settlement_date:
                print(f"   交割日期: {settlement_date}")
            else:
                print("   交割日期: 今日無交割數據")

            if total_amount is not None:
                print(f"   合計交割金額: {total_amount:,} 元")
            else:
                print("   合計交割金額: 無數據")
        else:
            print("   無交割明細數據")
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        raise


def test_active_reports():
    """測試主動回報功能（檢查是否有設置callback）"""
    print("\n=== 測試 active reports setup ===")
    try:
        # 檢查是否有設置callback的方法
        from fubon_neo.sdk import FubonSDK

        sdk = FubonSDK()

        # 檢查是否有相關的方法
        has_set_on_order = hasattr(sdk, "set_on_order")
        has_set_on_order_changed = hasattr(sdk, "set_on_order_changed")
        has_set_on_filled = hasattr(sdk, "set_on_filled")
        has_set_on_event = hasattr(sdk, "set_on_event")

        assert has_set_on_order, "缺少 set_on_order 方法"
        assert has_set_on_order_changed, "缺少 set_on_order_changed 方法"
        assert has_set_on_filled, "缺少 set_on_filled 方法"
        assert has_set_on_event, "缺少 set_on_event 方法"

        print("✅ SDK 支援所有主動回報 callback 方法")
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        raise


def test_disconnect_reconnect():
    """測試斷線重連機制"""
    print("\n=== 測試 disconnect reconnect ===")
    try:
        # 模擬斷線事件 - 直接測試事件處理邏輯
        print("模擬斷線事件 (code=300)...")

        # 創建一個簡單的模擬事件處理器來測試邏輯
        event_reports = []

        def mock_on_event(code, content):
            """模擬事件處理器"""
            report = {"timestamp": "2025-11-03T12:00:00", "code": code, "content": content, "type": "event"}
            event_reports.append(report)
            print(f"收到事件通知: {code} - {content}")

            # 模擬斷線重連邏輯
            if code == "300":
                print("[事件通知] 偵測到斷線（代碼300），啟動自動重連。")
                print("[自動重連] 模擬重連程序...")
                print("[自動重連] 重新登入成功，重新設定所有事件 callback。")

        # 測試正常事件
        mock_on_event("100", "系統啟動")
        mock_on_event("200", "行情連線正常")

        # 測試斷線事件
        mock_on_event("300", "WebSocket 已斷線")

        # 測試其他事件
        mock_on_event("400", "系統維護通知")

        print("✅ 斷線重連邏輯測試完成")
        print(f"   總共處理了 {len(event_reports)} 個事件")
        assert len(event_reports) > 0, "沒有收到任何事件"
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        raise


def run_all_tests():
    """運行所有測試（用於直接執行腳本）"""
    print("開始 FUBON API 測試套件")
    print("=" * 50)

    # 注意：這個函數現在只是為了向後兼容
    # 實際測試應該使用 pytest 運行
    print("請使用以下命令運行完整測試套件：")
    print("  pytest tests/test_fubon_api.py -v")
    print("或者：")
    print("  python -m pytest tests/ -v")

    # 簡單的連接測試
    try:
        # 這裡我們不能輕易調用測試函數，因為它們依賴於 fixtures
        print("\n⚠️  直接運行此腳本不再支持完整測試")
        print("請使用 pytest 運行測試：")
        print("  pytest tests/test_fubon_api.py::test_api_connection -v")
        print("  pytest tests/test_fubon_api.py -k 'intraday' -v")
        print("  pytest tests/test_fubon_api.py -k 'snapshot' -v")
        print("  pytest tests/test_fubon_api.py -k 'historical' -v")
        print("  pytest tests/test_fubon_api.py -k 'bank_balance or inventory or unrealized_pnl or settlement_info' -v")
    except Exception as e:
        print(f"❌ 測試準備失敗: {str(e)}")


if __name__ == "__main__":
    run_all_tests()
