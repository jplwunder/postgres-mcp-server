"""MCP Server setup and lifecycle management."""

import sys
from typing import Any

from loguru import logger
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .config import get_config, get_log_level
from .database import initialize_pool, close_pool
from .tools import TOOLS


# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    level=get_log_level(),
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
)


def create_server() -> Server:
    """
    Create and configure the MCP server.

    Returns:
        Configured MCP Server instance
    """
    server = Server("postgres-mcp")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List all available tools."""
        return [
            Tool(
                name="query_database",
                description="Execute a SELECT query on the PostgreSQL database and return formatted results",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "SQL SELECT query to execute",
                        },
                        "format": {
                            "type": "string",
                            "enum": ["json", "csv", "markdown"],
                            "description": "Output format (default: json)",
                            "default": "json",
                        },
                        "timeout": {
                            "type": "number",
                            "description": "Optional query timeout in seconds (max 300)",
                            "minimum": 1,
                            "maximum": 300,
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="list_tables",
                description="List all tables in the database with metadata",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "schema": {
                            "type": "string",
                            "description": "Optional schema name to filter by",
                        },
                    },
                },
            ),
            Tool(
                name="describe_table",
                description="Get detailed information about a table including columns, types, indexes, and constraints",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Name of the table to describe",
                        },
                        "schema": {
                            "type": "string",
                            "description": "Schema name (default: public)",
                            "default": "public",
                        },
                    },
                    "required": ["table_name"],
                },
            ),
            Tool(
                name="list_schemas",
                description="List all schemas in the database",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="get_table_indexes",
                description="Get all indexes for a specific table",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Name of the table",
                        },
                        "schema": {
                            "type": "string",
                            "description": "Schema name (default: public)",
                            "default": "public",
                        },
                    },
                    "required": ["table_name"],
                },
            ),
            Tool(
                name="get_query_history",
                description="Retrieve recent query history with execution metadata",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of queries to return (default: 20, max: 100)",
                            "default": 20,
                            "minimum": 1,
                            "maximum": 100,
                        },
                    },
                },
            ),
            Tool(
                name="get_database_stats",
                description="Get overall database statistics and metadata",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Any) -> list[TextContent]:
        """
        Handle tool calls.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            List of text content with results
        """
        logger.info(f"Tool called: {name}")
        logger.debug(f"Arguments: {arguments}")

        if name not in TOOLS:
            raise ValueError(f"Unknown tool: {name}")

        try:
            # Call the tool implementation
            result = await TOOLS[name](arguments)

            # Convert result to JSON string
            import json

            result_text = json.dumps(result, indent=2)

            return [TextContent(type="text", text=result_text)]

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            error_result = {"error": str(e), "tool": name}
            import json

            return [TextContent(type="text", text=json.dumps(error_result, indent=2))]

    return server


async def run_server():
    """Run the MCP server with stdio transport."""
    logger.info("Starting PostgreSQL MCP Server...")

    try:
        # Get configuration
        config = get_config()

        # Initialize database pool
        await initialize_pool(config)

        # Create and run server
        server = create_server()

        logger.success("PostgreSQL MCP Server started successfully")
        logger.info("Listening for requests on stdio...")

        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
    finally:
        # Cleanup
        logger.info("Shutting down server...")
        await close_pool()
        logger.success("Server shutdown complete")
