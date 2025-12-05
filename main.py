"""Entry point for the PostgreSQL MCP Server."""

import asyncio

from src.postgres_mcp.server import run_server


def main():
    """Main entry point for the server."""
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
