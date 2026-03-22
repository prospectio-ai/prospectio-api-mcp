"""
Tests for application/api/mcp_routes.py - MCP FastMCP instance.
"""
from mcp.server.fastmcp import FastMCP
from application.api.mcp_routes import mcp_prospectio


class TestMcpRoutes:
    """Test suite for MCP routes module."""

    def test_mcp_prospectio_is_fastmcp_instance(self):
        """mcp_prospectio should be a FastMCP instance."""
        assert isinstance(mcp_prospectio, FastMCP)

    def test_mcp_prospectio_has_correct_name(self):
        """mcp_prospectio should be named 'Prospectio MCP'."""
        assert mcp_prospectio.name == "Prospectio MCP"
