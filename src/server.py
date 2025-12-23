"""Cloudflare Worker entrypoint for the MCP server."""

from server import app

__all__ = ['app']
