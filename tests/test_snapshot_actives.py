#!/usr/bin/env python3
import inspect
import os

from dotenv import load_dotenv
from fubon_neo.sdk import FubonSDK

# 加載環境變量
load_dotenv()

# 獲取認證信息
username = os.getenv("FUBON_USERNAME")
password = os.getenv("FUBON_PASSWORD")
pfx_path = os.getenv("FUBON_PFX_PATH")
pfx_password = os.getenv("FUBON_PFX_PASSWORD")

if not all([username, password, pfx_path]):
    raise ValueError("FUBON_USERNAME, FUBON_PASSWORD, and FUBON_PFX_PATH environment variables are required")

# 初始化SDK
sdk = FubonSDK()
accounts = sdk.login(username, password, pfx_path, pfx_password or "")
sdk.init_realtime()
reststock = sdk.marketdata.rest_client.stock

# 測試get_snapshot_actives函數 - 檢查方法簽名

try:
    print("檢查 actives 方法的簽名...")
    sig = inspect.signature(reststock.snapshot.actives)
    print(f"actives 方法簽名: {sig}")
    print(f"參數: {list(sig.parameters.keys())}")
    for name, param in sig.parameters.items():
        print(f"  {name}: {param}")
except Exception as e:
    print(f"檢查方法簽名失敗: {str(e)}")

# 測試get_snapshot_actives函數 - 嘗試不傳參數
try:
    print("測試 get_snapshot_actives 函數 (不傳參數)...")
    result = reststock.snapshot.actives()
    print(f"成功獲取成交量值排行: {len(result)} 筆資料")
    print(f"第一筆資料: {result[0] if result else '無資料'}")
except Exception as e:
    print(f"測試失敗: {str(e)}")

# 測試get_snapshot_actives函數 - 只傳market關鍵字參數
try:
    print("測試 get_snapshot_actives 函數 (market='TSE')...")
    result = reststock.snapshot.actives(market="TSE")
    print(f"成功獲取 TSE 成交量值排行: {len(result)} 筆資料")
    print(f"第一筆資料: {result[0] if result else '無資料'}")
except Exception as e:
    print(f"測試失敗: {str(e)}")

# 測試get_snapshot_actives函數 - 傳market和trade關鍵字參數
try:
    print("測試 get_snapshot_actives 函數 (market='TSE', trade='volume')...")
    result = reststock.snapshot.actives(market="TSE", trade="volume")
    print(f"成功獲取 TSE 成交量值排行: {len(result)} 筆資料")
    print(f"第一筆資料: {result[0] if result else '無資料'}")
except Exception as e:
    print(f"測試失敗: {str(e)}")

print("測試完成")
