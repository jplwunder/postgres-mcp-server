"""Configuration management for the PostgreSQL MCP server."""

import os
from functools import lru_cache

from dotenv import load_dotenv
from loguru import logger

from .types import DatabaseConfig

# Load environment variables from .env file
load_dotenv()


@lru_cache()
def get_config() -> DatabaseConfig:
    """
    Get database configuration from environment variables.

    Returns:
        DatabaseConfig: Database configuration object

    Raises:
        ValueError: If required environment variables are missing
    """
    # Required parameters
    host = os.getenv("POSTGRES_HOST")
    database = os.getenv("POSTGRES_DATABASE")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")

    # Validate required parameters
    if not all([host, database, user]):
        missing = []
        if not host:
            missing.append("POSTGRES_HOST")
        if not database:
            missing.append("POSTGRES_DATABASE")
        if not user:
            missing.append("POSTGRES_USER")

        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Please create a .env file based on .env.example"
        )

    # Optional parameters with defaults
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    pool_min_size = int(os.getenv("POSTGRES_POOL_MIN_SIZE", "2"))
    pool_max_size = int(os.getenv("POSTGRES_POOL_MAX_SIZE", "10"))
    command_timeout = float(os.getenv("POSTGRES_COMMAND_TIMEOUT", "60.0"))
    connection_timeout = float(os.getenv("POSTGRES_CONNECTION_TIMEOUT", "10.0"))

    try:
        config = DatabaseConfig(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            pool_min_size=pool_min_size,
            pool_max_size=pool_max_size,
            command_timeout=command_timeout,
            connection_timeout=connection_timeout,
        )

        # Log configuration (without password)
        logger.info(
            f"Database configuration loaded: {config.user}@{config.host}:{config.port}/{config.database}"
        )
        logger.debug(
            f"Connection pool: min={config.pool_min_size}, max={config.pool_max_size}"
        )

        return config

    except Exception as e:
        logger.error(f"Failed to validate configuration: {e}")
        raise


def get_query_history_size() -> int:
    """Get the maximum size for query history from environment."""
    return int(os.getenv("QUERY_HISTORY_SIZE", "100"))


def get_log_level() -> str:
    """Get the log level from environment."""
    return os.getenv("LOG_LEVEL", "INFO").upper()
