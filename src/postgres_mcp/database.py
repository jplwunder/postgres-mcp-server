"""Database connection pool management and query execution."""

from typing import Any, Optional

import asyncpg
from loguru import logger

from .types import DatabaseConfig


class DatabasePool:
    """Manages PostgreSQL connection pool with read-only transaction support."""

    def __init__(self, config: DatabaseConfig):
        """
        Initialize database pool manager.

        Args:
            config: Database configuration
        """
        self.config = config
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self) -> None:
        """
        Initialize the connection pool.

        Raises:
            Exception: If pool initialization fails
        """
        try:
            logger.info("Initializing database connection pool...")

            self.pool = await asyncpg.create_pool(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
                min_size=self.config.pool_min_size,
                max_size=self.config.pool_max_size,
                command_timeout=self.config.command_timeout,
                timeout=self.config.connection_timeout,
            )

            # Test connection
            async with self.pool.acquire() as conn:
                version = await conn.fetchval("SELECT version()")
                logger.info(f"Database connection successful: {version}")

            logger.success(
                f"Connection pool initialized (min={self.config.pool_min_size}, max={self.config.pool_max_size})"
            )

        except asyncpg.InvalidPasswordError:
            logger.error("Database authentication failed: Invalid password")
            raise ValueError("Invalid database credentials")
        except asyncpg.InvalidCatalogNameError:
            logger.error(f"Database '{self.config.database}' does not exist")
            raise ValueError(f"Database '{self.config.database}' not found")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise

    async def close(self) -> None:
        """Close the connection pool gracefully."""
        if self.pool:
            logger.info("Closing database connection pool...")
            await self.pool.close()
            logger.success("Connection pool closed")

    async def execute_readonly_query(
        self, query: str, timeout: Optional[float] = None
    ) -> list[dict[str, Any]]:
        """
        Execute a read-only query and return results as a list of dictionaries.

        Args:
            query: SQL query to execute
            timeout: Optional query timeout in seconds

        Returns:
            List of rows as dictionaries

        Raises:
            ValueError: If pool is not initialized or query is not allowed
            Exception: For database errors
        """
        if not self.pool:
            raise ValueError("Database pool not initialized")

        try:
            # Use custom timeout if provided, otherwise use pool default
            async with self.pool.acquire() as conn:
                # Set transaction to read-only
                async with conn.transaction(readonly=True, isolation="read_committed"):
                    if timeout:
                        # Set statement timeout for this query
                        await conn.execute(f"SET LOCAL statement_timeout = {int(timeout * 1000)}")

                    # Execute query
                    rows = await conn.fetch(query)

                    # Convert rows to list of dictionaries
                    return [dict(row) for row in rows]

        except asyncpg.exceptions.QueryCanceledError:
            logger.warning(f"Query canceled due to timeout: {timeout}s")
            raise ValueError(f"Query execution timeout after {timeout} seconds")
        except asyncpg.exceptions.ReadOnlySQLTransactionError:
            logger.warning("Write operation attempted in read-only transaction")
            raise ValueError(
                "Write operations (INSERT, UPDATE, DELETE, etc.) are not allowed"
            )
        except asyncpg.exceptions.UndefinedTableError as e:
            logger.warning(f"Table not found: {e}")
            raise ValueError(f"Table does not exist: {e}")
        except asyncpg.exceptions.SyntaxOrAccessError as e:
            logger.warning(f"SQL syntax or access error: {e}")
            raise ValueError(f"SQL error: {e}")
        except Exception as e:
            logger.error(f"Database query error: {e}")
            raise

    async def execute_fetchval(self, query: str) -> Any:
        """
        Execute a query and return a single value.

        Args:
            query: SQL query to execute

        Returns:
            Single value from the query result

        Raises:
            ValueError: If pool is not initialized
        """
        if not self.pool:
            raise ValueError("Database pool not initialized")

        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction(readonly=True):
                    return await conn.fetchval(query)
        except Exception as e:
            logger.error(f"Database query error: {e}")
            raise

    async def execute_fetchrow(self, query: str) -> Optional[dict[str, Any]]:
        """
        Execute a query and return a single row as a dictionary.

        Args:
            query: SQL query to execute

        Returns:
            Single row as a dictionary, or None if no results

        Raises:
            ValueError: If pool is not initialized
        """
        if not self.pool:
            raise ValueError("Database pool not initialized")

        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction(readonly=True):
                    row = await conn.fetchrow(query)
                    return dict(row) if row else None
        except Exception as e:
            logger.error(f"Database query error: {e}")
            raise

    async def get_connection_count(self) -> int:
        """
        Get the current number of active connections.

        Returns:
            Number of active connections
        """
        if not self.pool:
            return 0
        return self.pool.get_size()

    async def health_check(self) -> bool:
        """
        Perform a health check on the database connection.

        Returns:
            True if database is healthy, False otherwise
        """
        try:
            if not self.pool:
                return False

            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


# Global database pool instance
_db_pool: Optional[DatabasePool] = None


def get_database_pool() -> DatabasePool:
    """
    Get the global database pool instance.

    Returns:
        DatabasePool instance

    Raises:
        ValueError: If pool has not been initialized
    """
    if _db_pool is None:
        raise ValueError("Database pool not initialized. Call initialize_pool() first.")
    return _db_pool


async def initialize_pool(config: DatabaseConfig) -> DatabasePool:
    """
    Initialize the global database pool.

    Args:
        config: Database configuration

    Returns:
        Initialized DatabasePool instance
    """
    global _db_pool
    _db_pool = DatabasePool(config)
    await _db_pool.initialize()
    return _db_pool


async def close_pool() -> None:
    """Close the global database pool."""
    global _db_pool
    if _db_pool:
        await _db_pool.close()
        _db_pool = None
