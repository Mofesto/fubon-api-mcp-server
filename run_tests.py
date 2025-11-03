#!/usr/bin/env python3
"""
測試運行器腳本
提供便捷的測試執行選項
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_tests(test_type=None, verbose=False, coverage=False):
    """運行測試"""
    cmd = ["python", "-m", "pytest"]

    if test_type:
        if test_type == "unit":
            cmd.append("tests/test_api_connection.py")
            cmd.append("tests/test_market_data.py")
        elif test_type == "account":
            cmd.append("tests/test_account_info.py")
        elif test_type == "trading":
            cmd.append("tests/test_trading.py")
            cmd.append("-m trading")
        elif test_type == "integration":
            cmd.append("tests/test_integration.py")
            cmd.append("-m integration")
        elif test_type == "all":
            cmd.append("tests/")
    else:
        cmd.append("tests/")

    if verbose:
        cmd.append("--verbose")
        cmd.append("-s")

    if coverage:
        cmd.extend(["--cov=server", "--cov-report=html", "--cov-report=term"])

    print(f"執行命令: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=Path(__file__).parent)

    return result.returncode == 0


def run_specific_test(test_file):
    """運行特定測試文件"""
    cmd = ["python", "-m", "pytest", f"tests/{test_file}", "--verbose", "-s"]
    print(f"執行命令: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="富邦MCP服務器測試運行器")
    parser.add_argument("action", choices=["run", "unit", "account", "trading", "integration", "all"], help="測試類型")
    parser.add_argument("--verbose", "-v", action="store_true", help="詳細輸出")
    parser.add_argument("--coverage", "-c", action="store_true", help="生成覆蓋率報告")
    parser.add_argument("--file", "-f", help="指定測試文件")

    args = parser.parse_args()

    if args.file:
        success = run_specific_test(args.file)
    else:
        success = run_tests(args.action, args.verbose, args.coverage)

    if success:
        print("✅ 所有測試通過！")
        sys.exit(0)
    else:
        print("❌ 測試失敗！")
        sys.exit(1)


if __name__ == "__main__":
    main()
