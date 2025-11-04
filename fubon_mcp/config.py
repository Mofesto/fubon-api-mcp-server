"""
Configuration module for Fubon API MCP Server.

This module contains all configuration constants, environment variables,
and global SDK instances used throughout the application.
"""

import os
from pathlib import Path

from fastmcp import FastMCP

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
username = os.getenv("FUBON_USERNAME")
password = os.getenv("FUBON_PASSWORD")
pfx_path = os.getenv("FUBON_PFX_PATH")
pfx_password = os.getenv("FUBON_PFX_PASSWORD")

# =============================================================================
# MCP Server Instance
# =============================================================================

# FastMCP server instance - shared across all service modules
mcp = FastMCP("fubon-api-mcp-server")

# =============================================================================
# Global SDK Instances (initialized in main())
# =============================================================================

# Fubon SDK instance - initialized in main() to avoid import-time errors
sdk = None

# Account information after login
accounts = None

# REST API client for stock data queries
reststock = None
