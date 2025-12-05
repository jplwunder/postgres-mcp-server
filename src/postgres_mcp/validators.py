"""Query validation and sanitization for security."""

import re
from loguru import logger


# Forbidden SQL keywords that indicate write operations
FORBIDDEN_KEYWORDS = [
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "CREATE",
    "ALTER",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "EXECUTE",
    "CALL",
    "COPY",
]


def remove_sql_comments(query: str) -> str:
    """
    Remove SQL comments from a query.

    Args:
        query: SQL query string

    Returns:
        Query with comments removed
    """
    # Remove single-line comments (-- ...)
    query = re.sub(r"--.*$", "", query, flags=re.MULTILINE)

    # Remove multi-line comments (/* ... */)
    query = re.sub(r"/\*.*?\*/", "", query, flags=re.DOTALL)

    return query


def validate_query(query: str) -> None:
    """
    Validate that a query is safe for read-only execution.

    Args:
        query: SQL query to validate

    Raises:
        ValueError: If query is invalid or contains forbidden operations
    """
    if not query or not query.strip():
        raise ValueError("Query cannot be empty")

    # Remove comments for validation
    cleaned_query = remove_sql_comments(query)

    # Check for forbidden keywords
    for keyword in FORBIDDEN_KEYWORDS:
        # Use word boundary to avoid false positives (e.g., "INSERTED" column name)
        pattern = rf"\b{keyword}\b"
        if re.search(pattern, cleaned_query, re.IGNORECASE):
            logger.warning(f"Query validation failed: forbidden keyword '{keyword}' detected")
            raise ValueError(
                f"Query contains forbidden keyword: {keyword}. "
                f"Only SELECT queries and read-only operations are allowed."
            )

    logger.debug("Query validation passed")


def sanitize_identifier(identifier: str) -> str:
    """
    Sanitize a table or schema identifier.

    Args:
        identifier: Table or schema name

    Returns:
        Sanitized identifier

    Raises:
        ValueError: If identifier contains invalid characters
    """
    if not identifier:
        raise ValueError("Identifier cannot be empty")

    # Allow alphanumeric, underscore, and dot (for schema.table notation)
    if not re.match(r"^[a-zA-Z0-9_\.]+$", identifier):
        raise ValueError(
            f"Invalid identifier '{identifier}'. "
            f"Only alphanumeric characters, underscores, and dots are allowed."
        )

    return identifier


def validate_timeout(timeout: float) -> None:
    """
    Validate query timeout value.

    Args:
        timeout: Timeout in seconds

    Raises:
        ValueError: If timeout is invalid
    """
    if timeout <= 0:
        raise ValueError("Timeout must be positive")

    if timeout > 300:
        raise ValueError("Timeout cannot exceed 300 seconds (5 minutes)")
