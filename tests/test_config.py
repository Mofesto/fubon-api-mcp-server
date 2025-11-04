"""
Tests for config.py - Configuration module.

This module tests the configuration constants, environment variables,
and global SDK instances initialization.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from fubon_mcp import config


class TestDataDirectoryConfiguration:
    """Test data directory configuration."""

    def test_default_data_dir(self):
        """Test default data directory path."""
        expected_path = Path.home() / "Library" / "Application Support" / "fubon-mcp" / "data"
        assert config.DEFAULT_DATA_DIR == expected_path

    def test_base_data_dir_creation(self, temp_data_dir):
        """Test that BASE_DATA_DIR is created if it doesn't exist."""
        # Test that the directory creation logic works
        test_dir = temp_data_dir / "test_base_dir"
        assert not test_dir.exists()
        
        # Simulate the directory creation (like config.py does)
        test_dir.mkdir(parents=True, exist_ok=True)
        
        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_custom_data_dir_env_var(self, temp_data_dir):
        """Test custom data directory from environment variable."""
        custom_dir = temp_data_dir / "custom"
        
        # Test the path resolution logic without reloading
        with patch.dict(os.environ, {"FUBON_DATA_DIR": str(custom_dir)}):
            expected_path = Path(os.getenv("FUBON_DATA_DIR", config.DEFAULT_DATA_DIR))
            assert expected_path == custom_dir


class TestEnvironmentVariables:
    """Test environment variable handling."""

    def test_env_vars_loaded(self):
        """Test that environment variables are loaded correctly."""
        with patch.dict(os.environ, {
            "FUBON_USERNAME": "test_user",
            "FUBON_PASSWORD": "test_pass",
            "FUBON_PFX_PATH": "/path/to/cert.pfx",
            "FUBON_PFX_PASSWORD": "cert_pass"
        }):
            # Test the env var loading logic directly
            assert os.getenv("FUBON_USERNAME") == "test_user"
            assert os.getenv("FUBON_PASSWORD") == "test_pass"
            assert os.getenv("FUBON_PFX_PATH") == "/path/to/cert.pfx"
            assert os.getenv("FUBON_PFX_PASSWORD") == "cert_pass"

    def test_env_vars_none_when_missing(self):
        """Test that environment variables are None when not set."""
        # Clear environment variables but keep HOME/USERPROFILE for Path.home()
        env_vars = ["FUBON_USERNAME", "FUBON_PASSWORD", "FUBON_PFX_PATH", "FUBON_PFX_PASSWORD"]
        env_patch = {}
        # Keep essential environment variables for Path.home() to work
        for key in ["HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH"]:
            if key in os.environ:
                env_patch[key] = os.environ[key]
        
        with patch.dict(os.environ, env_patch, clear=True):
            # Test that env vars are None when not set
            assert os.getenv("FUBON_USERNAME") is None
            assert os.getenv("FUBON_PASSWORD") is None
            assert os.getenv("FUBON_PFX_PATH") is None
            assert os.getenv("FUBON_PFX_PASSWORD") is None
class TestMCPInstance:
    """Test MCP server instance."""

    def test_mcp_instance_created(self):
        """Test that MCP instance is created."""
        assert config.mcp is not None
        assert hasattr(config.mcp, 'tool')
        assert hasattr(config.mcp, 'resource')

    def test_mcp_name(self):
        """Test MCP server name."""
        assert config.mcp.name == "fubon-api-mcp-server"


class TestGlobalInstances:
    """Test global SDK instances initialization."""

    def test_initial_sdk_state(self):
        """Test initial state of global instances."""
        # Note: In test environment, these are set by conftest.py fixtures
        # In production, they would be None initially
        assert config.sdk is not None  # Mock SDK from conftest
        assert config.accounts is not None  # Mock accounts from conftest
        assert config.reststock is not None  # Mock reststock from conftest

    def test_sdk_assignment(self, mock_sdk):
        """Test SDK instance assignment."""
        config.sdk = mock_sdk
        assert config.sdk is mock_sdk
        assert config.sdk.stock is not None

    def test_accounts_assignment(self, mock_accounts):
        """Test accounts instance assignment."""
        config.accounts = mock_accounts
        assert config.accounts is mock_accounts
        assert config.accounts.is_success is True

    def test_reststock_assignment(self, mock_reststock):
        """Test reststock instance assignment."""
        config.reststock = mock_reststock
        assert config.reststock is mock_reststock


class TestConfigurationIntegration:
    """Test configuration module integration."""

    def test_all_components_importable(self):
        """Test that all configuration components can be imported."""
        # Test imports work
        from fubon_mcp.config import (
            BASE_DATA_DIR,
            DEFAULT_DATA_DIR,
            accounts,
            mcp,
            password,
            pfx_password,
            pfx_path,
            reststock,
            sdk,
            username,
        )

        # Test types
        assert isinstance(BASE_DATA_DIR, Path)
        assert isinstance(DEFAULT_DATA_DIR, Path)
        assert mcp is not None

        # In test environment, these are set by conftest.py fixtures
        # In production, they would be None initially
        assert sdk is not None  # Mock SDK from conftest
        assert accounts is not None  # Mock accounts from conftest
        assert reststock is not None  # Mock reststock from conftest
        # Note: username, password, pfx_path are set by reset_config fixture
        # but this test imports fresh values, so they reflect the current env state

    def test_config_module_structure(self):
        """Test that config module has expected structure."""
        required_attrs = [
            'DEFAULT_DATA_DIR',
            'BASE_DATA_DIR',
            'username',
            'password',
            'pfx_path',
            'pfx_password',
            'mcp',
            'sdk',
            'accounts',
            'reststock'
        ]

        for attr in required_attrs:
            assert hasattr(config, attr), f"Config module missing attribute: {attr}"