"""Result formatters for different output formats."""

import csv
import json
from datetime import datetime, date
from decimal import Decimal
from io import StringIO
from typing import Any

from .types import OutputFormat


def serialize_value(value: Any) -> Any:
    """
    Serialize a database value to a JSON-compatible format.

    Args:
        value: Database value

    Returns:
        JSON-compatible value
    """
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    elif isinstance(value, Decimal):
        return float(value)
    elif isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    elif value is None:
        return None
    else:
        return value


def format_as_json(rows: list[dict[str, Any]]) -> str:
    """
    Format rows as JSON string.

    Args:
        rows: List of row dictionaries

    Returns:
        JSON formatted string
    """
    # Serialize special types
    serialized_rows = []
    for row in rows:
        serialized_row = {key: serialize_value(value) for key, value in row.items()}
        serialized_rows.append(serialized_row)

    return json.dumps(serialized_rows, indent=2)


def format_as_csv(rows: list[dict[str, Any]]) -> str:
    """
    Format rows as CSV string.

    Args:
        rows: List of row dictionaries

    Returns:
        CSV formatted string
    """
    if not rows:
        return ""

    output = StringIO()
    columns = list(rows[0].keys())
    writer = csv.DictWriter(output, fieldnames=columns)

    # Write header
    writer.writeheader()

    # Write rows with serialized values
    for row in rows:
        serialized_row = {key: serialize_value(value) for key, value in row.items()}
        writer.writerow(serialized_row)

    return output.getvalue()


def format_as_markdown(rows: list[dict[str, Any]]) -> str:
    """
    Format rows as Markdown table.

    Args:
        rows: List of row dictionaries

    Returns:
        Markdown table formatted string
    """
    if not rows:
        return "No results"

    columns = list(rows[0].keys())

    # Calculate column widths
    col_widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            value_str = str(serialize_value(row[col]))
            col_widths[col] = max(col_widths[col], len(value_str))

    # Build header
    header_parts = []
    separator_parts = []
    for col in columns:
        width = col_widths[col]
        header_parts.append(f" {col.ljust(width)} ")
        separator_parts.append("-" * (width + 2))

    lines = []
    lines.append("|" + "|".join(header_parts) + "|")
    lines.append("|" + "|".join(separator_parts) + "|")

    # Build rows
    for row in rows:
        row_parts = []
        for col in columns:
            width = col_widths[col]
            value_str = str(serialize_value(row[col]))
            row_parts.append(f" {value_str.ljust(width)} ")
        lines.append("|" + "|".join(row_parts) + "|")

    return "\n".join(lines)


def format_rows(rows: list[dict[str, Any]], format_type: OutputFormat) -> str:
    """
    Format rows according to the specified format type.

    Args:
        rows: List of row dictionaries
        format_type: Output format (json, csv, or markdown)

    Returns:
        Formatted string

    Raises:
        ValueError: If format type is unsupported
    """
    if format_type == OutputFormat.JSON:
        return format_as_json(rows)
    elif format_type == OutputFormat.CSV:
        return format_as_csv(rows)
    elif format_type == OutputFormat.MARKDOWN:
        return format_as_markdown(rows)
    else:
        raise ValueError(f"Unsupported format type: {format_type}")
