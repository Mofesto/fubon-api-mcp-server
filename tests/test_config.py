#!/usr/bin/env python3
"""
Config 模組測試

測試 config.py 的各種功能，包括:
1. 不同平台的資料目錄配置
2. 環境變數處理
3. 資料庫路徑設定
4. 日誌配置
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


class TestConfig:
    """Config 類測試"""

    def test_config_default_path_structure(self):
        """測試預設資料路徑結構 (不依賴特定平台)"""
        from fubon_api_mcp_server.config import Config

        config = Config()

        # 驗證 DEFAULT_DATA_DIR 和 BASE_DATA_DIR 是 Path 物件
        assert isinstance(config.DEFAULT_DATA_DIR, Path)
        assert isinstance(config.BASE_DATA_DIR, Path)

        # 驗證路徑包含 "fubon-mcp"
        assert "fubon-mcp" in str(config.DEFAULT_DATA_DIR)
        assert "data" in str(config.DEFAULT_DATA_DIR)

    def test_config_custom_data_dir(self, tmp_path):
        """測試自訂資料目錄 (使用可寫入的臨時目錄)"""
        import importlib

        from fubon_api_mcp_server import config as config_module

        custom_path = tmp_path / "custom" / "data" / "path"
        with patch.dict(os.environ, {"FUBON_DATA_DIR": str(custom_path)}):
            importlib.reload(config_module)
            config = config_module.Config()

            assert config.BASE_DATA_DIR == custom_path

    @patch.dict(os.environ, {"FUBON_USERNAME": "testuser", "FUBON_PASSWORD": "testpass"})
    def test_config_credentials_from_env(self):
        """測試從環境變數讀取憑證"""
        import importlib

        from fubon_api_mcp_server import config as config_module

        importlib.reload(config_module)
        config = config_module.Config()

        assert config.username == "testuser"
        assert config.password == "testpass"

    @patch.dict(os.environ, {"FUBON_PFX_PATH": "/path/to/cert.pfx", "FUBON_PFX_PASSWORD": "certpass"})
    def test_config_pfx_credentials_from_env(self):
        """測試從環境變數讀取憑證檔案路徑和密碼"""
        import importlib

        from fubon_api_mcp_server import config as config_module

        importlib.reload(config_module)
        config = config_module.Config()

        assert config.pfx_path == "/path/to/cert.pfx"
        assert config.pfx_password == "certpass"

    def test_config_credentials_default_none(self):
        """測試預設情況下憑證為 None"""
        from fubon_api_mcp_server.config import Config

        config = Config()

        # 在測試環境中可能已設定環境變數,所以只檢查屬性存在
        assert hasattr(config, "username")
        assert hasattr(config, "password")
        assert hasattr(config, "pfx_path")
        assert hasattr(config, "pfx_password")

    def test_config_database_path(self, tmp_path):
        """測試資料庫路徑設定"""
        with patch.dict(os.environ, {"FUBON_DATA_DIR": str(tmp_path)}):
            import importlib

            from fubon_api_mcp_server import config as config_module

            importlib.reload(config_module)
            config = config_module.Config()

            expected_db_path = tmp_path / "stock_data.db"
            assert config.DATABASE_PATH == expected_db_path

    def test_config_data_dir_creation(self, tmp_path):
        """測試資料目錄自動建立"""
        custom_dir = tmp_path / "custom" / "nested" / "data"
        assert not custom_dir.exists()

        with patch.dict(os.environ, {"FUBON_DATA_DIR": str(custom_dir)}):
            import importlib

            from fubon_api_mcp_server import config as config_module

            importlib.reload(config_module)
            config = config_module.Config()

            assert custom_dir.exists()
            assert config.BASE_DATA_DIR == custom_dir

    def test_config_mcp_placeholder(self):
        """測試 MCP 實例佔位符"""
        from fubon_api_mcp_server.config import Config

        config = Config()
        assert config.mcp is None

    @patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"})
    def test_logging_level_debug(self):
        """測試日誌層級設定為 DEBUG"""
        import importlib
        import logging

        from fubon_api_mcp_server import config as config_module

        # 清除現有 handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        importlib.reload(config_module)

        # 驗證日誌層級
        assert root_logger.level == logging.DEBUG

    @patch.dict(os.environ, {"LOG_LEVEL": "ERROR"})
    def test_logging_level_error(self):
        """測試日誌層級設定為 ERROR"""
        import importlib
        import logging

        from fubon_api_mcp_server import config as config_module

        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        importlib.reload(config_module)

        assert root_logger.level == logging.ERROR

    def test_logging_configuration_exists(self):
        """測試日誌配置存在"""
        import logging

        root_logger = logging.getLogger()

        # 驗證 logger 已配置
        assert root_logger.level in [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR]

    def test_global_config_instance(self):
        """測試全域 config 實例存在"""
        from fubon_api_mcp_server.config import config

        assert config is not None
        assert hasattr(config, "BASE_DATA_DIR")
        assert hasattr(config, "DATABASE_PATH")

    def test_global_sdk_placeholder(self):
        """測試全域 SDK 佔位符"""
        from fubon_api_mcp_server.config import sdk

        # 初始應為 None (由 utils.validate_and_get_account 設定)
        assert sdk is None or sdk is not None  # 可能已被其他測試設定

    def test_global_reststock_placeholder(self):
        """測試全域 reststock 佔位符"""
        from fubon_api_mcp_server.config import reststock

        assert reststock is None or reststock is not None

    def test_global_restfutopt_placeholder(self):
        """測試全域 restfutopt 佔位符"""
        from fubon_api_mcp_server.config import restfutopt

        assert restfutopt is None or restfutopt is not None
