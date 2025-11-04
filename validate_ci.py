#!/usr/bin/env python3
"""
CI/CD 配置驗證腳本

此腳本用於驗證專案的 CI/CD 配置是否正確。
運行前請確保已安裝所有依賴項。
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """運行命令並返回結果"""
    print(f"🔍 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=False, cwd=Path(__file__).parent)
        stdout = result.stdout.decode('utf-8', errors='replace') if result.stdout else ''
        stderr = result.stderr.decode('utf-8', errors='replace') if result.stderr else ''
        if result.returncode == 0:
            print(f"✅ {description} - 成功")
            return True, stdout
        else:
            print(f"❌ {description} - 失敗")
            print(f"錯誤信息: {stderr}")
            return False, stderr
    except Exception as e:
        print(f"❌ {description} - 異常: {str(e)}")
        return False, str(e)


def main():
    """主驗證函數"""
    print("🚀 開始驗證 CI/CD 配置...")
    print("=" * 50)

    results = []

    # 1. 檢查 Python 版本
    success, output = run_command("python --version", "檢查 Python 版本")
    results.append(("Python 版本", success))

    # 2. 檢查依賴項安裝
    success, output = run_command("python -c \"import fubon_mcp; print('版本:', fubon_mcp.__version__)\"", "檢查包導入")
    results.append(("包導入", success))

    # 3. 檢查代碼格式化
    success, output = run_command("python -m black --check --diff fubon_mcp tests", "檢查 Black 格式化")
    results.append(("Black 格式化", success))

    # 4. 檢查導入排序
    success, output = run_command("python -m isort --check-only --diff fubon_mcp tests", "檢查 isort 導入排序")
    results.append(("isort 導入排序", success))

    # 5. 檢查代碼品質
    success, output = run_command("python -m flake8 fubon_mcp tests", "檢查 flake8 代碼品質")
    results.append(("flake8 代碼品質", success))

    # 6. 檢查類型提示 - 實際運行 mypy
    success, output = run_command("python -m mypy fubon_mcp", "檢查 mypy 類型檢查")
    results.append(("mypy 類型檢查", success))

    # 7. 運行測試
    success, output = run_command("python -m pytest --tb=short", "運行測試套件")
    results.append(("測試套件", success))

    # 8. 檢查包構建
    success, output = run_command("python -m build", "檢查包構建")
    results.append(("包構建", success))

    # 9. 檢查 twine 驗證
    if Path("dist").exists():
        success, output = run_command("python -m twine check dist/*", "檢查 twine 包驗證")
        results.append(("twine 包驗證", success))
    else:
        print("⚠️  跳過 twine 檢查 - 沒有 dist 目錄")
        results.append(("twine 包驗證", None))

    # 總結結果
    print("\n" + "=" * 50)
    print("📊 驗證結果總結:")

    passed = 0
    failed = 0
    skipped = 0

    for check, result in results:
        if result is True:
            status = "✅ 通過"
            passed += 1
        elif result is False:
            status = "❌ 失敗"
            failed += 1
        else:
            status = "⚠️  跳過"
            skipped += 1
        print(f"  {check}: {status}")

    print(f"\n總計: {passed} 通過, {failed} 失敗, {skipped} 跳過")

    if failed == 0:
        print("🎉 所有檢查都通過了！CI/CD 配置正確。")
        return 0
    else:
        print("⚠️  有檢查失敗，請檢查上面的錯誤信息。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
