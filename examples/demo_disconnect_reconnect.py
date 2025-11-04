#!/usr/bin/env python3
"""
FUBON 斷線重連功能演示腳本
展示如何處理交易Socket斷線並自動重連
"""

from dotenv import load_dotenv

# 加載環境變數
load_dotenv()


def demo_disconnect_reconnect():
    """演示斷線重連功能"""
    print("=== FUBON 斷線重連功能演示 ===")
    print()

    # 模擬事件處理器（不依賴實際server運行）
    event_reports = []

    def mock_on_event(code, content):
        """模擬事件處理器"""
        from datetime import datetime

        report = {"timestamp": datetime.now().isoformat(), "code": code, "content": content, "type": "event"}
        event_reports.append(report)
        print(f"收到事件通知: {code} - {content}")

        # 模擬斷線重連邏輯
        if code == "300":
            print("[事件通知] 偵測到斷線（代碼300），啟動自動重連。")
            print("[自動重連] 模擬重連程序...")
            print("[自動重連] 重新登入成功，重新設定所有事件 callback。")

    print("1. 模擬正常事件通知：")
    mock_on_event("100", "系統啟動")
    mock_on_event("200", "行情連線正常")

    print("\n2. 模擬斷線事件（代碼300）：")
    print("   觸發自動重連機制...")
    mock_on_event("300", "WebSocket 已斷線")

    print("\n3. 再次觸發斷線事件，測試lock機制：")
    print("   理論上lock會防止重複重連...")
    mock_on_event("300", "再次斷線")

    print("\n4. 其他事件類型：")
    mock_on_event("400", "系統維護通知")
    mock_on_event("500", "緊急通知")

    print("\n=== 演示完成 ===")
    print(f"總共處理了 {len(event_reports)} 個事件")
    print("注意：實際重連需要在有交易活動時才能觀察到完整效果")


if __name__ == "__main__":
    demo_disconnect_reconnect()
