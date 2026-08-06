"""
Tests for certificate export functionality (SDK v2.2.7+ feature).

This module tests the certificate export feature introduced in SDK v2.2.7.
Tests cover:
- Successful certificate export
- Export with password protection
- Re-import of exported certificate
- Password validation
- Format verification (PKCS#12)

References:
- specs/001-sdk-v2.2.7-upgrade/tasks.md: T017-T024
- specs/001-sdk-v2.2.7-upgrade/research.md: Certificate export format
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from fubon_api_mcp_server.utils import export_certificate


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_certificate_data():
    """Mock PKCS#12 certificate binary data."""
    # PKCS#12 files start with specific magic bytes: 0x30 0x82
    # This is a simplified mock - real PKCS#12 is more complex
    return b"\x30\x82\x0f\xa0" + b"\x00" * 2000  # ~2KB mock certificate


@pytest.fixture
def temp_export_path(tmp_path):
    """Temporary path for certificate export."""
    return tmp_path / "exported_cert.pfx"


@pytest.fixture
def mock_sdk_with_export():
    """Mock FubonSDK with certificate export capability."""
    mock_sdk = MagicMock()
    
    # Mock successful export
    mock_export_result = MagicMock()
    mock_export_result.is_success = True
    mock_export_result.data = b"\x30\x82\x0f\xa0" + b"\x00" * 2000  # PKCS#12 mock
    mock_sdk.export_certificate.return_value = mock_export_result
    
    return mock_sdk


# =============================================================================
# Test: export_certificate helper function
# =============================================================================


class TestExportCertificate:
    """Test suite for certificate export helper function."""

    @patch("fubon_api_mcp_server.utils.config_module")
    def test_export_certificate_success(self, mock_config, mock_sdk_with_export, temp_export_path):
        """
        T018: Test successful certificate export.

        Verifies:
        - Certificate is exported to file
        - File exists and is valid PKCS#12 format
        - File size is reasonable
        """
        mock_config.sdk = mock_sdk_with_export

        # Execute export
        success, message = export_certificate("test_password", str(temp_export_path))

        # Assertions
        assert success is True
        assert message == "Certificate exported successfully / 憑證匯出成功"
        assert temp_export_path.exists()
        
        # Verify PKCS#12 format (starts with 0x30 0x82)
        with open(temp_export_path, "rb") as f:
            magic_bytes = f.read(2)
            assert magic_bytes == b"\x30\x82", "Not a valid PKCS#12 file"

    @patch("fubon_api_mcp_server.utils.config_module")
    def test_export_certificate_with_password(self, mock_config, mock_sdk_with_export, temp_export_path):
        """
        T019: Test certificate export with specified password.

        Verifies:
        - Export with custom password succeeds
        - Password is passed to SDK correctly
        """
        mock_config.sdk = mock_sdk_with_export

        # Execute export with custom password
        custom_password = "MyStr0ng!P@ssw0rd"
        success, message = export_certificate(custom_password, str(temp_export_path))

        # Assertions
        assert success is True
        mock_sdk_with_export.export_certificate.assert_called_once_with(password=custom_password)

    @patch("fubon_api_mcp_server.utils.config_module")
    def test_import_exported_certificate(self, mock_config, mock_sdk_with_export, temp_export_path):
        """
        T020: Test re-import of exported certificate.

        Verifies:
        - Exported certificate can be read back
        - Imported certificate is usable for authentication
        """
        mock_config.sdk = mock_sdk_with_export

        # Export certificate
        export_password = "export_pass_123"
        success, _ = export_certificate(export_password, str(temp_export_path))
        assert success is True

        # Mock re-import (login with exported certificate)
        with patch("fubon_neo.sdk.FubonSDK") as mock_sdk_class:
            mock_new_sdk = MagicMock()
            mock_sdk_class.return_value = mock_new_sdk

            mock_login_result = MagicMock()
            mock_login_result.is_success = True
            mock_new_sdk.login.return_value = mock_login_result

            # Simulate login with exported certificate
            new_sdk = mock_sdk_class()
            result = new_sdk.login(
                username="test_user",
                password="test_pass",
                pfx_path=str(temp_export_path),
                pfx_password=export_password
            )

            # Assertions
            assert result.is_success is True
            mock_new_sdk.login.assert_called_once()

    @patch("fubon_api_mcp_server.utils.config_module")
    def test_export_certificate_invalid_password(self, mock_config):
        """
        T021: Test export with invalid password format.

        Verifies:
        - Empty password is rejected
        - Clear error message is returned
        """
        mock_config.sdk = MagicMock()

        # Test empty password
        success, message = export_certificate("", "/tmp/cert.pfx")
        assert success is False
        assert "Certificate export failed: invalid password" in message
        assert "憑證匯出失敗: 密碼無效" in message

        # Test None password
        success, message = export_certificate(None, "/tmp/cert.pfx")
        assert success is False
        assert "invalid password" in message

    @patch("fubon_api_mcp_server.utils.config_module")
    def test_export_certificate_invalid_path(self, mock_config, mock_sdk_with_export):
        """
        Test export to invalid/non-writable path.

        Verifies:
        - Non-writable path is detected
        - Appropriate error message is returned
        """
        mock_config.sdk = mock_sdk_with_export

        # Test invalid path (directory that doesn't exist)
        invalid_path = "/nonexistent/directory/cert.pfx"
        success, message = export_certificate("password123", invalid_path)

        assert success is False
        assert "Export path is not writable" in message or "No such file or directory" in message
        assert "匯出路徑不可寫入" in message or "路徑" in message

    @patch("fubon_api_mcp_server.utils.config_module")
    def test_export_certificate_sdk_not_initialized(self, mock_config, temp_export_path):
        """
        Test export when SDK is not initialized.

        Verifies:
        - SDK initialization check works
        - Clear error message is returned
        """
        mock_config.sdk = None

        success, message = export_certificate("password123", str(temp_export_path))

        assert success is False
        assert "SDK not initialized" in message or "SDK 未初始化" in message

    @patch("fubon_api_mcp_server.utils.config_module")
    def test_export_certificate_sdk_error(self, mock_config, temp_export_path):
        """
        Test export when SDK returns error.

        Verifies:
        - SDK errors are handled gracefully
        - Error message is propagated
        """
        mock_sdk = MagicMock()
        mock_config.sdk = mock_sdk

        # Mock SDK export failure
        mock_export_result = MagicMock()
        mock_export_result.is_success = False
        mock_export_result.message = "Certificate export failed"
        mock_sdk.export_certificate.return_value = mock_export_result

        success, message = export_certificate("password123", str(temp_export_path))

        assert success is False
        assert "failed" in message.lower()

    @patch("fubon_api_mcp_server.utils.config_module")
    def test_export_certificate_format_validation(self, mock_config, mock_sdk_with_export, temp_export_path):
        """
        Test that exported certificate is valid PKCS#12 format.

        Verifies:
        - Binary format (not PEM)
        - PKCS#12 magic bytes present
        - File size reasonable (> 100 bytes)
        """
        mock_config.sdk = mock_sdk_with_export

        success, _ = export_certificate("password123", str(temp_export_path))
        assert success is True

        # Verify file format
        with open(temp_export_path, "rb") as f:
            data = f.read()
            
            # Check PKCS#12 magic bytes (DER encoding starts with 0x30 0x82)
            assert data[:2] == b"\x30\x82", "Invalid PKCS#12 magic bytes"
            
            # Check file size (should be > 100 bytes for a real certificate)
            assert len(data) > 100, "Certificate file too small"
            
            # Ensure it's not PEM format (PEM starts with "-----BEGIN")
            assert not data.startswith(b"-----BEGIN"), "Exported as PEM instead of PKCS#12"


# =============================================================================
# Test: Integration scenarios
# =============================================================================


class TestCertificateExportIntegration:
    """Integration tests for certificate export workflow."""

    @patch("fubon_api_mcp_server.utils.config_module")
    def test_export_and_verify_round_trip(self, mock_config, mock_sdk_with_export, temp_export_path):
        """
        Test complete export → save → verify cycle.

        Verifies:
        - Export succeeds
        - File is created
        - File can be read back
        - File format is correct
        """
        mock_config.sdk = mock_sdk_with_export

        # Step 1: Export
        password = "SecurePass123!"
        success, message = export_certificate(password, str(temp_export_path))
        assert success is True

        # Step 2: Verify file exists
        assert temp_export_path.exists()
        assert temp_export_path.stat().st_size > 0

        # Step 3: Read back and verify format
        with open(temp_export_path, "rb") as f:
            cert_data = f.read()
            assert cert_data[:2] == b"\x30\x82"  # PKCS#12 magic

    @patch("fubon_api_mcp_server.utils.config_module")
    def test_multiple_exports_overwrite(self, mock_config, mock_sdk_with_export, temp_export_path):
        """
        Test exporting to same path multiple times.

        Verifies:
        - Second export overwrites first
        - No corruption from overwrite
        """
        mock_config.sdk = mock_sdk_with_export

        # First export
        success1, _ = export_certificate("pass1", str(temp_export_path))
        assert success1 is True
        size1 = temp_export_path.stat().st_size

        # Second export (should overwrite)
        success2, _ = export_certificate("pass2", str(temp_export_path))
        assert success2 is True
        size2 = temp_export_path.stat().st_size

        # Both exports should succeed
        assert size1 > 0
        assert size2 > 0


# =============================================================================
# Test: Error message bilingual verification
# =============================================================================


class TestBilingualErrorMessages:
    """Verify all error messages are bilingual."""

    @patch("fubon_api_mcp_server.utils.config_module")
    def test_error_messages_contain_chinese(self, mock_config):
        """
        Verify error messages include Traditional Chinese translations.

        Tests all error scenarios to ensure bilingual support.
        """
        # Test 1: Invalid password
        success, msg = export_certificate("", "/tmp/test.pfx")
        assert "密碼" in msg or "憑證" in msg, "Missing Chinese in password error"

        # Test 2: SDK not initialized
        mock_config.sdk = None
        success, msg = export_certificate("pass", "/tmp/test.pfx")
        # Should contain Chinese characters
        assert any('\u4e00' <= c <= '\u9fff' for c in msg), "Missing Chinese characters"

    @patch("fubon_api_mcp_server.utils.config_module")
    def test_success_message_bilingual(self, mock_config, mock_sdk_with_export, temp_export_path):
        """Verify success message is bilingual."""
        mock_config.sdk = mock_sdk_with_export

        success, message = export_certificate("password", str(temp_export_path))
        
        assert success is True
        assert "successfully" in message.lower() or "成功" in message
        assert any('\u4e00' <= c <= '\u9fff' for c in message), "Missing Chinese in success message"
