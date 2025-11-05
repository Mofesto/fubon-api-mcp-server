"""
Configuration module for fubon_api_mcp_server.
"""

import os
import sys
from pathlib import Path


class Config:
    """Configuration class for fubon_api_mcp_server."""

    def __init__(self):
        # Load environment variables
        self.username = os.getenv("FUBON_USERNAME")
        self.password = os.getenv("FUBON_PASSWORD")
        self.pfx_path = os.getenv("FUBON_PFX_PATH")
        self.pfx_password = os.getenv("FUBON_PFX_PASSWORD")

        # Data directory configuration - platform-specific defaults
        if sys.platform == "win32":
            self.DEFAULT_DATA_DIR = Path.home() / "AppData" / "Local" / "fubon-mcp" / "data"
        elif sys.platform == "darwin":
            self.DEFAULT_DATA_DIR = Path.home() / "Library" / "Application Support" / "fubon-mcp" / "data"
        else:  # Linux and other Unix-like systems
            self.DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "fubon-mcp" / "data"
        
        self.BASE_DATA_DIR = Path(os.getenv("FUBON_DATA_DIR", self.DEFAULT_DATA_DIR))

        # Ensure data directory exists
        self.BASE_DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Placeholder for MCP instance (will be set in server.py)
        self.mcp = None


# Create global config instance
config = Config()
