"""Type definitions and Pydantic models for the PostgreSQL MCP server."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict


class OutputFormat(str, Enum):
    """Supported output formats for query results."""

    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


class DatabaseConfig(BaseModel):
    """Database connection configuration."""

    host: str = Field(..., description="PostgreSQL host")
    port: int = Field(5432, description="PostgreSQL port")
    database: str = Field(..., description="Database name")
    user: str = Field(..., description="Database user")
    password: str = Field(..., description="Database password")
    pool_min_size: int = Field(2, description="Minimum pool size")
    pool_max_size: int = Field(10, description="Maximum pool size")
    command_timeout: float = Field(60.0, description="Command timeout in seconds")
    connection_timeout: float = Field(10.0, description="Connection timeout in seconds")

    @field_validator("port")
    @classmethod
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v

    @field_validator("pool_min_size", "pool_max_size")
    @classmethod
    def validate_pool_size(cls, v):
        if v < 1:
            raise ValueError("Pool size must be at least 1")
        return v

    @field_validator("command_timeout", "connection_timeout")
    @classmethod
    def validate_timeout(cls, v):
        if v <= 0:
            raise ValueError("Timeout must be positive")
        return v


class QueryDatabaseInput(BaseModel):
    """Input schema for query_database tool."""

    query: str = Field(..., description="SQL SELECT query to execute")
    format: OutputFormat = Field(
        OutputFormat.JSON, description="Output format: json, csv, or markdown"
    )
    timeout: Optional[float] = Field(
        None, description="Optional query timeout in seconds (max 300)"
    )

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v):
        if v is not None:
            if v <= 0:
                raise ValueError("Timeout must be positive")
            if v > 300:
                raise ValueError("Timeout cannot exceed 300 seconds")
        return v


class ListTablesInput(BaseModel):
    """Input schema for list_tables tool."""

    schema_name: Optional[str] = Field(None, description="Schema name to filter by", alias="schema")


class DescribeTableInput(BaseModel):
    """Input schema for describe_table tool."""

    table_name: str = Field(..., description="Name of the table to describe")
    schema_name: Optional[str] = Field("public", description="Schema name", alias="schema")


class GetTableIndexesInput(BaseModel):
    """Input schema for get_table_indexes tool."""

    table_name: str = Field(..., description="Name of the table")
    schema_name: Optional[str] = Field("public", description="Schema name", alias="schema")


class GetQueryHistoryInput(BaseModel):
    """Input schema for get_query_history tool."""

    limit: int = Field(20, description="Maximum number of queries to return")

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v):
        if v < 1:
            raise ValueError("Limit must be at least 1")
        if v > 100:
            raise ValueError("Limit cannot exceed 100")
        return v


class TableInfo(BaseModel):
    """Information about a database table."""

    schema_name: str = Field(alias="schema")
    name: str
    row_count_estimate: Optional[int] = None
    size: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class ColumnInfo(BaseModel):
    """Information about a table column."""

    name: str
    type: str
    nullable: bool
    default: Optional[str] = None
    primary_key: bool = False


class IndexInfo(BaseModel):
    """Information about a table index."""

    name: str
    type: str
    columns: list[str]
    unique: bool
    primary: bool = False


class ForeignKeyInfo(BaseModel):
    """Information about a foreign key constraint."""

    name: str
    columns: list[str]
    referenced_table: str
    referenced_columns: list[str]


class TableDescription(BaseModel):
    """Complete description of a table."""

    schema_name: str = Field(alias="schema")
    table: str
    columns: list[ColumnInfo]
    indexes: list[IndexInfo]
    foreign_keys: list[ForeignKeyInfo]

    model_config = ConfigDict(populate_by_name=True)


class QueryResult(BaseModel):
    """Result of a database query."""

    rows: list[dict[str, Any]]
    row_count: int
    columns: list[str]
    execution_time_ms: float
    format: OutputFormat


class QueryHistoryEntry(BaseModel):
    """Entry in the query history."""

    query: str
    timestamp: datetime
    execution_time_ms: float
    row_count: int
    format: OutputFormat
    success: bool
    error: Optional[str] = None


class DatabaseStats(BaseModel):
    """Overall database statistics."""

    database_name: str
    size: str
    table_count: int
    connection_count: int
    version: str
