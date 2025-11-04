"""
Configuration module for Fubon API MCP Server.

This module contains all configuration constants, environment variables,
and global SDK instances used throughout the application.
"""

import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastmcp import FastMCP

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# Data Directory Configuration
# =============================================================================

# Default data directory for storing local stock historical data
DEFAULT_DATA_DIR = Path.home() / "Library" / "Application Support" / "fubon-mcp" / "data"
BASE_DATA_DIR = Path(os.getenv("FUBON_DATA_DIR", DEFAULT_DATA_DIR))

# Ensure data directory exists
BASE_DATA_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# Environment Variables for Authentication
# =============================================================================

# Fubon API credentials from environment variables
username: Optional[str] = os.getenv("FUBON_USERNAME")
password: Optional[str] = os.getenv("FUBON_PASSWORD")
pfx_path: Optional[str] = os.getenv("FUBON_PFX_PATH")
pfx_password: Optional[str] = os.getenv("FUBON_PFX_PASSWORD")

# =============================================================================
# MCP Server Instance
# =============================================================================

# FastMCP server instance - shared across all service modules
mcp = FastMCP("fubon-api-mcp-server")

# =============================================================================
# Global SDK Instances (initialized in main())
# =============================================================================

# Fubon SDK instance - initialized in main() to avoid import-time errors
sdk: Optional[Any] = None

# Account information after login
accounts: Optional[Any] = None

# REST API client for stock data queries
reststock: Optional[Any] = None
