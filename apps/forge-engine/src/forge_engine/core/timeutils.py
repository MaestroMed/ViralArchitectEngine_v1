"""Time helpers.

`datetime.utcnow()` is deprecated (Python 3.12+) but the codebase stores NAIVE
UTC datetimes in SQLite — switching to timezone-aware values would change stored
data and break naive comparisons. `utcnow()` is the deprecation-free, behaviour-
preserving equivalent: the same naive-UTC value, no warning.
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC now (tzinfo=None) — drop-in for the deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
