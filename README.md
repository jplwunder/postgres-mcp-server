# PostgreSQL MCP Server

A Model Context Protocol (MCP) server that provides read-only access to PostgreSQL databases. Execute SELECT queries, inspect database schema, and track query history with built-in safety features.

## Features

- **Read-Only Query Execution**: Execute SELECT queries with automatic read-only transaction enforcement
- **Multiple Output Formats**: Results in JSON, CSV, or Markdown table format
- **Schema Inspection**: List tables, describe table structures, view indexes, and explore schemas
- **Query History**: Track recently executed queries with execution time and metadata
- **Connection Pooling**: Efficient connection management with configurable pool sizes
- **Security**: Query validation, SQL injection prevention, and read-only transaction guarantees
- **Database Statistics**: View database size, table counts, and connection information

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd postgres-mcp
```

2. Install dependencies using `uv`:
```bash
uv sync
```

## Configuration

### Environment Variables

Create a `.env` file in the project root (use `.env.example` as a template):

```bash
# Required: PostgreSQL Connection Parameters
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=myapp
POSTGRES_USER=readonly_user
POSTGRES_PASSWORD=secure_password

# Optional: Connection Pool Configuration
POSTGRES_POOL_MIN_SIZE=2          # Default: 2
POSTGRES_POOL_MAX_SIZE=10         # Default: 10
POSTGRES_COMMAND_TIMEOUT=60       # Default: 60 seconds
POSTGRES_CONNECTION_TIMEOUT=10    # Default: 10 seconds

# Optional: Query History Configuration
QUERY_HISTORY_SIZE=100            # Default: 100

# Optional: Logging Configuration
LOG_LEVEL=INFO                    # Default: INFO (DEBUG, INFO, WARNING, ERROR)
```

### Database User Setup

For security, create a dedicated read-only PostgreSQL user:

```sql
-- Create read-only user
CREATE USER readonly_user WITH PASSWORD 'secure_password';

-- Grant connect permission
GRANT CONNECT ON DATABASE myapp TO readonly_user;

-- Grant schema usage
GRANT USAGE ON SCHEMA public TO readonly_user;

-- Grant select on all tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_user;

-- Grant select on future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO readonly_user;
```

## Usage

### Running the Server

```bash
python main.py
```

The server communicates via stdio and can be integrated with MCP clients like Claude Desktop.

### Integrating with Claude Desktop

Add this configuration to your Claude Desktop config file:

**MacOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "postgres": {
      "command": "python",
      "args": ["/path/to/postgres-mcp/main.py"],
      "env": {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DATABASE": "myapp",
        "POSTGRES_USER": "readonly_user",
        "POSTGRES_PASSWORD": "secure_password"
      }
    }
  }
}
```

Alternatively, if using `uv`:

```json
{
  "mcpServers": {
    "postgres": {
      "command": "uv",
      "args": ["run", "python", "main.py"],
      "cwd": "/path/to/postgres-mcp"
    }
  }
}
```

## Available Tools

### 1. query_database

Execute SELECT queries on the database with formatted output.

**Input:**
```json
{
  "query": "SELECT * FROM users LIMIT 10",
  "format": "json",
  "timeout": 30
}
```

**Parameters:**
- `query` (required): SQL SELECT query to execute
- `format` (optional): Output format - `json` (default), `csv`, or `markdown`
- `timeout` (optional): Query timeout in seconds (max 300)

**Output:**
```json
{
  "rows": [...],
  "row_count": 10,
  "columns": ["id", "name", "email"],
  "execution_time_ms": 45.32,
  "format": "json",
  "formatted_output": "..."
}
```

### 2. list_tables

List all tables in the database with metadata.

**Input:**
```json
{
  "schema": "public"
}
```

**Parameters:**
- `schema` (optional): Filter tables by schema name

**Output:**
```json
{
  "tables": [
    {
      "schema": "public",
      "name": "users",
      "row_count_estimate": 1500,
      "size": "128 KB"
    }
  ]
}
```

### 3. describe_table

Get detailed table structure including columns, types, indexes, and constraints.

**Input:**
```json
{
  "table_name": "users",
  "schema": "public"
}
```

**Parameters:**
- `table_name` (required): Name of the table
- `schema` (optional): Schema name (default: `public`)

**Output:**
```json
{
  "schema": "public",
  "table": "users",
  "columns": [
    {
      "name": "id",
      "type": "integer",
      "nullable": false,
      "default": "nextval('users_id_seq')",
      "primary_key": true
    }
  ],
  "indexes": [...],
  "foreign_keys": [...]
}
```

### 4. list_schemas

List all schemas in the database.

**Input:**
```json
{}
```

**Output:**
```json
{
  "schemas": ["public", "auth", "analytics"]
}
```

### 5. get_table_indexes

Get all indexes for a specific table.

**Input:**
```json
{
  "table_name": "users",
  "schema": "public"
}
```

**Parameters:**
- `table_name` (required): Name of the table
- `schema` (optional): Schema name (default: `public`)

**Output:**
```json
{
  "indexes": [
    {
      "name": "users_pkey",
      "type": "btree",
      "columns": ["id"],
      "unique": true,
      "primary": true
    }
  ]
}
```

### 6. get_query_history

Retrieve recent query history with execution metadata.

**Input:**
```json
{
  "limit": 20
}
```

**Parameters:**
- `limit` (optional): Maximum queries to return (default: 20, max: 100)

**Output:**
```json
{
  "queries": [
    {
      "query": "SELECT * FROM users",
      "timestamp": "2025-12-04T10:30:00Z",
      "execution_time_ms": 45.32,
      "row_count": 10,
      "format": "json",
      "success": true,
      "error": null
    }
  ]
}
```

### 7. get_database_stats

Get overall database statistics and metadata.

**Input:**
```json
{}
```

**Output:**
```json
{
  "database_name": "myapp",
  "size": "45 MB",
  "table_count": 12,
  "connection_count": 5,
  "version": "PostgreSQL 15.3"
}
```

## Security Features

### Read-Only Enforcement

All queries are executed within read-only transactions:
```python
async with conn.transaction(readonly=True):
    result = await conn.fetch(query)
```

### Query Validation

Queries are validated before execution to prevent:
- INSERT, UPDATE, DELETE operations
- DROP, CREATE, ALTER operations
- TRUNCATE, GRANT, REVOKE operations
- Other write/admin operations

### SQL Injection Prevention

- Input sanitization for table and schema identifiers
- Parameterized queries where applicable
- Regex-based validation of identifiers

## Architecture

### Components

- **`config.py`**: Environment configuration and validation
- **`database.py`**: Connection pool management and read-only query execution
- **`validators.py`**: Query validation and sanitization
- **`formatters.py`**: Result formatting (JSON, CSV, Markdown)
- **`history.py`**: Thread-safe query history tracking
- **`tools.py`**: MCP tool implementations
- **`server.py`**: MCP server setup and lifecycle management
- **`types.py`**: Pydantic models for type safety

### Connection Pooling

- **Min Size**: 2 warm connections
- **Max Size**: 10 concurrent connections
- **Timeout**: 60 seconds command timeout, 10 seconds connection timeout
- **Idle Lifetime**: Automatic cleanup of inactive connections

## Troubleshooting

### Connection Errors

**Error**: "Database authentication failed"
- Verify `POSTGRES_USER` and `POSTGRES_PASSWORD` are correct
- Check if the user exists in PostgreSQL
- Ensure the user has CONNECT permission

**Error**: "Database 'myapp' not found"
- Verify `POSTGRES_DATABASE` matches an existing database
- Check database name spelling

**Error**: "Connection refused"
- Verify PostgreSQL is running on the specified host and port
- Check firewall settings
- Verify `POSTGRES_HOST` and `POSTGRES_PORT` are correct

### Query Errors

**Error**: "Query contains forbidden keyword: INSERT"
- This server only allows SELECT queries
- Use a different tool for write operations

**Error**: "Table does not exist"
- Verify table name and schema are correct
- Use `list_tables` to see available tables
- Check if user has SELECT permission on the table

**Error**: "Query execution timeout"
- Query took longer than the specified timeout
- Optimize the query or increase timeout parameter
- Check for missing indexes on large tables

### Permission Errors

**Error**: "permission denied for table X"
- The database user lacks SELECT permission
- Grant appropriate permissions (see Database User Setup)

## Development

### Running Tests

```bash
# Add your test commands here
pytest
```

### Project Structure

```
postgres-mcp/
   .env                    # Configuration (not in git)
   .env.example            # Configuration template
   .gitignore
   README.md
   pyproject.toml
   main.py                 # Entry point
   src/
       postgres_mcp/
           __init__.py
           config.py       # Configuration
           database.py     # Connection pool
           formatters.py   # Output formatting
           history.py      # Query history
           server.py       # MCP server
           tools.py        # MCP tools
           types.py        # Pydantic models
           validators.py   # Query validation
```

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]
