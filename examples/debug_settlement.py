#!/usr/bin/env python3
"""
測試交割資訊數據結構
"""

import os

from dotenv import load_dotenv
from fubon_neo.sdk import FubonSDK

# 加載環境變數
load_dotenv()


def main():
    try:
        username = os.getenv("FUBON_USERNAME")
        password = os.getenv("FUBON_PASSWORD")
        pfx_path = os.getenv("FUBON_PFX_PATH")
        pfx_password = os.getenv("FUBON_PFX_PASSWORD")

        sdk = FubonSDK()
        accounts = sdk.login(username, password, pfx_path, pfx_password or "")

        account = accounts.data[0]
        result = sdk.accounting.query_settlement(account, "0d")

        print("交割資訊API回應:")
        print(f"is_success: {result.is_success}")
        print(f"message: {result.message}")

        if result.is_success:
            data = result.data
            print(f"data類型: {type(data)}")
            print(f"data內容: {data}")

            if hasattr(data, "details"):
                print(f"details類型: {type(data.details)}")
                print(f"details長度: {len(data.details) if data.details else 0}")

                if data.details:
                    detail = data.details[0]
                    print(f"第一筆detail類型: {type(detail)}")
                    print(f"第一筆detail屬性: {dir(detail)}")

                    # 檢查所有屬性
                    for attr in dir(detail):
                        if not attr.startswith("_"):
                            try:
                                value = getattr(detail, attr)
                                print(f"  {attr}: {value} ({type(value)})")
                            except Exception as e:
                                print(f"  {attr}: 無法獲取 - {e}")

    except Exception as e:
        print(f"錯誤: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
