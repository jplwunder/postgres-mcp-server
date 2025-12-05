"""Query history tracking."""

from collections import deque
from datetime import datetime
from threading import Lock
from typing import Optional

from .config import get_query_history_size
from .types import OutputFormat, QueryHistoryEntry


class QueryHistory:
    """Thread-safe query history tracker."""

    def __init__(self, max_size: Optional[int] = None):
        """
        Initialize query history.

        Args:
            max_size: Maximum number of queries to keep (default from config)
        """
        if max_size is None:
            max_size = get_query_history_size()

        self._history: deque[QueryHistoryEntry] = deque(maxlen=max_size)
        self._lock = Lock()

    def add_query(
        self,
        query: str,
        execution_time_ms: float,
        row_count: int,
        format_type: OutputFormat,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """
        Add a query to the history.

        Args:
            query: SQL query that was executed
            execution_time_ms: Execution time in milliseconds
            row_count: Number of rows returned
            format_type: Output format used
            success: Whether the query succeeded
            error: Error message if query failed
        """
        entry = QueryHistoryEntry(
            query=query,
            timestamp=datetime.now(),
            execution_time_ms=execution_time_ms,
            row_count=row_count,
            format=format_type,
            success=success,
            error=error,
        )

        with self._lock:
            self._history.append(entry)

    def get_recent(self, limit: int = 20) -> list[QueryHistoryEntry]:
        """
        Get recent queries from history.

        Args:
            limit: Maximum number of queries to return

        Returns:
            List of recent query history entries (newest first)
        """
        with self._lock:
            # Return newest entries first
            all_entries = list(self._history)
            all_entries.reverse()
            return all_entries[:limit]

    def clear(self) -> None:
        """Clear all query history."""
        with self._lock:
            self._history.clear()

    def get_count(self) -> int:
        """
        Get the current number of queries in history.

        Returns:
            Number of queries in history
        """
        with self._lock:
            return len(self._history)


# Global query history instance
_query_history: Optional[QueryHistory] = None


def get_query_history() -> QueryHistory:
    """
    Get the global query history instance.

    Returns:
        QueryHistory instance
    """
    global _query_history
    if _query_history is None:
        _query_history = QueryHistory()
    return _query_history
