"""
Setup script for fubon-api-mcp-server

此腳本用於打包和安裝富邦證券 MCP 服務器包。
支援通過 pip 安裝和命令行工具啟動服務器。
"""

from setuptools import find_packages, setup

# 讀取專案說明文件
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# 讀取依賴列表（過濾掉平台特定的依賴）
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = []
    for line in fh:
        line = line.strip()
        # 跳過空行和註釋
        if not line or line.startswith("#"):
            continue
        # 跳過包含環境標記的行（平台特定的依賴）
        if ";" in line:
            continue
        requirements.append(line)

setup(
    # 包基本資訊
    name="fubon-api-mcp-server",
    use_scm_version={
        "write_to": "fubon_api_mcp_server/_version.py",
        "version_scheme": "post-release",
        "local_scheme": "node-and-date",
        "fallback_version": "1.8.0",
    },
    setup_requires=["setuptools-scm"],
    author="Jimmy Cui",
    author_email="",
    description="富邦證券 MCP 服務器 - Model Context Protocol 服務器用於富邦證券 API",
    # 詳細說明（從 README.md 讀取）
    long_description=long_description,
    long_description_content_type="text/markdown",
    # 專案連結
    url="https://github.com/Mofesto/fubon-api-mcp-server",
    # 自動發現包（會找到 fubon_api_mcp_server 包）
    packages=find_packages(),
    # PyPI 分類器，用於描述包的特性和適用性
    classifiers=[
        "Development Status :: 4 - Beta",  # 開發狀態：測試版
        "Intended Audience :: Developers",  # 目標受眾：開發者
        "License :: OSI Approved :: MIT License",  # 許可證
        "Operating System :: OS Independent",  # 作業系統：跨平台
        "Programming Language :: Python :: 3",  # Python 版本支援
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Office/Business :: Financial :: Investment",  # 主題：金融投資
    ],
    # Python 版本需求
    python_requires=">=3.10",
    # 運行依賴（從 requirements.txt 讀取）
    install_requires=requirements,
    # 可選依賴，用於開發和測試
    extras_require={
        "dev": [
            "pytest>=7.0.0",  # 測試框架
            "pytest-cov>=4.0.0",  # 測試覆蓋率
            "pytest-xdist>=3.0.0",  # 並行測試
            "pytest-mock>=3.10.0",  # Mock 工具
        ],
    },
    # 命令行入口點，允許通過 `fubon-api-mcp-server` 命令啟動服務器
    entry_points={
        "console_scripts": [
            "fubon-api-mcp-server=fubon_api_mcp_server.server:main",
        ],
    },
    # 包含包數據文件（如配置文件）
    include_package_data=True,
    # 不使用 zip 格式，允許直接編輯已安裝的包（用於開發）
    zip_safe=False,
)
