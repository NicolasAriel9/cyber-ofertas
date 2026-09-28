from datetime import datetime, timezone


def ensure_aware(dt: datetime) -> datetime:
    """SQLite (used in local dev) doesn't persist tzinfo on DateTime(timezone=True)
    columns, so values read back are naive even though they were stored as UTC.
    Postgres (prod) preserves tzinfo correctly. Normalize here so comparisons
    against datetime.now(timezone.utc) work on both backends."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
