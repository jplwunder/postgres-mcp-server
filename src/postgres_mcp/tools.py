"""MCP tool implementations for PostgreSQL operations."""

import time
from typing import Any

from loguru import logger

from .database import get_database_pool
from .formatters import format_rows
from .history import get_query_history
from .types import (
    ColumnInfo,
    DatabaseStats,
    DescribeTableInput,
    ForeignKeyInfo,
    GetQueryHistoryInput,
    GetTableIndexesInput,
    IndexInfo,
    ListTablesInput,
    OutputFormat,
    QueryDatabaseInput,
    TableDescription,
    TableInfo,
)
from .validators import sanitize_identifier, validate_query


async def query_database_tool(args: dict[str, Any]) -> dict[str, Any]:
    """
    Execute a SELECT query and return formatted results.

    Args:
        args: Tool arguments containing query, format, and optional timeout

    Returns:
        Query result with rows, metadata, and formatted output
    """
    # Validate input
    input_data = QueryDatabaseInput(**args)

    # Validate query
    validate_query(input_data.query)

    # Get database pool
    db = get_database_pool()

    # Execute query and measure time
    start_time = time.time()
    try:
        rows = await db.execute_readonly_query(
            input_data.query, timeout=input_data.timeout
        )
        execution_time_ms = (time.time() - start_time) * 1000

        # Extract column names
        columns = list(rows[0].keys()) if rows else []

        # Format results
        formatted_output = format_rows(rows, input_data.format)

        # Track in history
        history = get_query_history()
        history.add_query(
            query=input_data.query,
            execution_time_ms=execution_time_ms,
            row_count=len(rows),
            format_type=input_data.format,
            success=True,
        )

        return {
            "rows": rows,
            "row_count": len(rows),
            "columns": columns,
            "execution_time_ms": round(execution_time_ms, 2),
            "format": input_data.format.value,
            "formatted_output": formatted_output,
        }

    except Exception as e:
        execution_time_ms = (time.time() - start_time) * 1000

        # Track failed query in history
        history = get_query_history()
        history.add_query(
            query=input_data.query,
            execution_time_ms=execution_time_ms,
            row_count=0,
            format_type=input_data.format,
            success=False,
            error=str(e),
        )

        logger.error(f"Query execution failed: {e}")
        raise


async def list_tables_tool(args: dict[str, Any]) -> dict[str, Any]:
    """
    List all tables in the database with optional schema filtering.

    Args:
        args: Tool arguments containing optional schema filter

    Returns:
        List of tables with metadata
    """
    input_data = ListTablesInput(**args)
    db = get_database_pool()

    # Build query to list tables
    if input_data.schema_name:
        sanitize_identifier(input_data.schema_name)
        query = f"""
            SELECT
                schemaname as schema,
                tablename as name,
                pg_total_relation_size(schemaname || '.' || tablename)::text as size
            FROM pg_tables
            WHERE schemaname = '{input_data.schema_name}'
            ORDER BY schemaname, tablename
        """
    else:
        query = """
            SELECT
                schemaname as schema,
                tablename as name,
                pg_total_relation_size(schemaname || '.' || tablename)::text as size
            FROM pg_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schemaname, tablename
        """

    rows = await db.execute_readonly_query(query)

    # Get row count estimates
    tables = []
    for row in rows:
        # Get approximate row count
        count_query = f"""
            SELECT reltuples::bigint as estimate
            FROM pg_class
            WHERE oid = '{row['schema']}.{row['name']}'::regclass
        """
        count_result = await db.execute_fetchval(count_query)

        tables.append(
            TableInfo(
                schema_name=row["schema"],
                name=row["name"],
                row_count_estimate=int(count_result) if count_result else None,
                size=row["size"] if row["size"] else None,
            ).model_dump(by_alias=True)
        )

    return {"tables": tables}


async def describe_table_tool(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get detailed table structure including columns, types, and constraints.

    Args:
        args: Tool arguments containing table_name and optional schema

    Returns:
        Complete table description
    """
    input_data = DescribeTableInput(**args)
    sanitize_identifier(input_data.table_name)
    if input_data.schema_name:
        sanitize_identifier(input_data.schema_name)

    db = get_database_pool()

    # Query column information
    columns_query = f"""
        SELECT
            c.column_name as name,
            c.data_type as type,
            c.is_nullable = 'YES' as nullable,
            c.column_default as default_value,
            CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_primary_key
        FROM information_schema.columns c
        LEFT JOIN (
            SELECT ku.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage ku
                ON tc.constraint_name = ku.constraint_name
                AND tc.table_schema = ku.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_name = '{input_data.table_name}'
                AND tc.table_schema = '{input_data.schema_name}'
        ) pk ON c.column_name = pk.column_name
        WHERE c.table_name = '{input_data.table_name}'
            AND c.table_schema = '{input_data.schema_name}'
        ORDER BY c.ordinal_position
    """

    column_rows = await db.execute_readonly_query(columns_query)
    columns = [
        ColumnInfo(
            name=row["name"],
            type=row["type"],
            nullable=row["nullable"],
            default=row["default_value"],
            primary_key=row["is_primary_key"],
        )
        for row in column_rows
    ]

    # Query index information
    indexes_query = f"""
        SELECT
            i.relname as index_name,
            am.amname as index_type,
            ARRAY_AGG(a.attname ORDER BY k.ordinality) as columns,
            ix.indisunique as is_unique,
            ix.indisprimary as is_primary
        FROM pg_index ix
        JOIN pg_class t ON t.oid = ix.indrelid
        JOIN pg_class i ON i.oid = ix.indexrelid
        JOIN pg_am am ON i.relam = am.oid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        CROSS JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS k(attnum, ordinality)
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum
        WHERE t.relname = '{input_data.table_name}'
            AND n.nspname = '{input_data.schema_name}'
        GROUP BY i.relname, am.amname, ix.indisunique, ix.indisprimary
        ORDER BY i.relname
    """

    index_rows = await db.execute_readonly_query(indexes_query)
    indexes = [
        IndexInfo(
            name=row["index_name"],
            type=row["index_type"],
            columns=row["columns"],
            unique=row["is_unique"],
            primary=row["is_primary"],
        )
        for row in index_rows
    ]

    # Query foreign key information
    fk_query = f"""
        SELECT
            tc.constraint_name as fk_name,
            ARRAY_AGG(kcu.column_name ORDER BY kcu.ordinal_position) as columns,
            ccu.table_name as referenced_table,
            ARRAY_AGG(ccu.column_name ORDER BY kcu.ordinal_position) as referenced_columns
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_name = '{input_data.table_name}'
            AND tc.table_schema = '{input_data.schema_name}'
        GROUP BY tc.constraint_name, ccu.table_name
    """

    fk_rows = await db.execute_readonly_query(fk_query)
    foreign_keys = [
        ForeignKeyInfo(
            name=row["fk_name"],
            columns=row["columns"],
            referenced_table=row["referenced_table"],
            referenced_columns=row["referenced_columns"],
        )
        for row in fk_rows
    ]

    description = TableDescription(
        schema_name=input_data.schema_name,
        table=input_data.table_name,
        columns=columns,
        indexes=indexes,
        foreign_keys=foreign_keys,
    )

    return description.model_dump(by_alias=True)


async def list_schemas_tool(args: dict[str, Any]) -> dict[str, Any]:
    """
    List all schemas in the database.

    Args:
        args: Tool arguments (empty for this tool)

    Returns:
        List of schema names
    """
    db = get_database_pool()

    query = """
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
        ORDER BY schema_name
    """

    rows = await db.execute_readonly_query(query)
    schemas = [row["schema_name"] for row in rows]

    return {"schemas": schemas}


async def get_table_indexes_tool(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get indexes for a specific table.

    Args:
        args: Tool arguments containing table_name and optional schema

    Returns:
        List of indexes for the table
    """
    input_data = GetTableIndexesInput(**args)
    sanitize_identifier(input_data.table_name)
    if input_data.schema_name:
        sanitize_identifier(input_data.schema_name)

    db = get_database_pool()

    query = f"""
        SELECT
            i.relname as index_name,
            am.amname as index_type,
            ARRAY_AGG(a.attname ORDER BY k.ordinality) as columns,
            ix.indisunique as is_unique,
            ix.indisprimary as is_primary
        FROM pg_index ix
        JOIN pg_class t ON t.oid = ix.indrelid
        JOIN pg_class i ON i.oid = ix.indexrelid
        JOIN pg_am am ON i.relam = am.oid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        CROSS JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS k(attnum, ordinality)
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum
        WHERE t.relname = '{input_data.table_name}'
            AND n.nspname = '{input_data.schema_name}'
        GROUP BY i.relname, am.amname, ix.indisunique, ix.indisprimary
        ORDER BY i.relname
    """

    rows = await db.execute_readonly_query(query)
    indexes = [
        IndexInfo(
            name=row["index_name"],
            type=row["index_type"],
            columns=row["columns"],
            unique=row["is_unique"],
            primary=row["is_primary"],
        ).model_dump()
        for row in rows
    ]

    return {"indexes": indexes}


async def get_query_history_tool(args: dict[str, Any]) -> dict[str, Any]:
    """
    Retrieve recent query history.

    Args:
        args: Tool arguments containing optional limit

    Returns:
        List of recent queries with metadata
    """
    input_data = GetQueryHistoryInput(**args)
    history = get_query_history()

    recent_queries = history.get_recent(limit=input_data.limit)

    # Convert to dict format
    queries = [
        {
            "query": entry.query,
            "timestamp": entry.timestamp.isoformat(),
            "execution_time_ms": entry.execution_time_ms,
            "row_count": entry.row_count,
            "format": entry.format.value,
            "success": entry.success,
            "error": entry.error,
        }
        for entry in recent_queries
    ]

    return {"queries": queries}


async def get_database_stats_tool(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get overall database statistics.

    Args:
        args: Tool arguments (empty for this tool)

    Returns:
        Database statistics and metadata
    """
    db = get_database_pool()

    # Get database name, size, and version
    stats_query = """
        SELECT
            current_database() as db_name,
            pg_size_pretty(pg_database_size(current_database())) as db_size,
            version() as db_version
    """
    stats_row = await db.execute_fetchrow(stats_query)

    # Get table count
    table_count_query = """
        SELECT COUNT(*) as count
        FROM pg_tables
        WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
    """
    table_count = await db.execute_fetchval(table_count_query)

    # Get connection count
    connection_count = await db.get_connection_count()

    stats = DatabaseStats(
        database_name=stats_row["db_name"],
        size=stats_row["db_size"],
        table_count=int(table_count),
        connection_count=connection_count,
        version=stats_row["db_version"],
    )

    return stats.model_dump()


# Tool registry mapping tool names to their implementations
TOOLS = {
    "query_database": query_database_tool,
    "list_tables": list_tables_tool,
    "describe_table": describe_table_tool,
    "list_schemas": list_schemas_tool,
    "get_table_indexes": get_table_indexes_tool,
    "get_query_history": get_query_history_tool,
    "get_database_stats": get_database_stats_tool,
}
