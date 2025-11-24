"""
Configuration module for fubon_api_mcp_server.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional


class Config:
    """Configuration class for fubon_api_mcp_server."""

    def __init__(self) -> None:
        # Load environment variables
        self.username: Optional[str] = os.getenv("FUBON_USERNAME")
        self.password: Optional[str] = os.getenv("FUBON_PASSWORD")
        self.pfx_path: Optional[str] = os.getenv("FUBON_PFX_PATH")
        self.pfx_password: Optional[str] = os.getenv("FUBON_PFX_PASSWORD")

        # Data directory configuration - platform-specific defaults
        if sys.platform == "win32":
            self.DEFAULT_DATA_DIR: Path = Path.home() / "AppData" / "Local" / "fubon-mcp" / "data"
        elif sys.platform == "darwin":
            self.DEFAULT_DATA_DIR: Path = Path.home() / "Library" / "Application Support" / "fubon-mcp" / "data"
        else:  # Linux and other Unix-like systems
            self.DEFAULT_DATA_DIR: Path = Path.home() / ".local" / "share" / "fubon-mcp" / "data"

        self.BASE_DATA_DIR: Path = Path(os.getenv("FUBON_DATA_DIR", self.DEFAULT_DATA_DIR))

        # SQLite database path
        self.DATABASE_PATH: Path = self.BASE_DATA_DIR / "stock_data.db"

        # Ensure data directory exists
        self.BASE_DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Placeholder for MCP instance (will be set in server.py)
        self.mcp = None


# Create global config instance
config = Config()

# ---------------------------
# Global logging configuration
# - Use environment variable LOG_LEVEL (default: INFO)
# - Only configure basicConfig when no handlers are present to avoid
#   reconfiguring logging during imports or tests that set handlers.
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
root_logger = logging.getLogger()
if not root_logger.handlers:
    numeric_level = getattr(logging, LOG_LEVEL, logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logging.getLogger(__name__).info(f"Logging configured, level={LOG_LEVEL}")
else:
    # If handlers exist, set level only
    try:
        root_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    except Exception:
        pass


# Global variables for SDK and accounts (set by utils.validate_and_get_account)
sdk: Optional[Any] = None  # FubonSDK instance
accounts: Optional[Any] = None  # List of accounts

# REST API clients (set in server.py main())
reststock: Optional[Any] = None  # Stock REST client
restfutopt: Optional[Any] = None  # Futures/options REST client
