from datetime import datetime, timedelta, timezone
def get_date_range(days: int = 1) -> tuple[str, str]:
    """
    Returns a tuple of (start_date, end_date) in Toast API required format: yyyy-MM-dd'T'HH:mm:ss.SSSZ
    Example: 2016-01-01T14:13:12.000+0400
    """
    end_dt = datetime.now(timezone.utc).replace(microsecond=0)
    start_dt = end_dt - timedelta(days=days)

    # Format with milliseconds and timezone offset (+0000 for UTC)
    end_date = end_dt.strftime("%Y-%m-%dT%H:%M:%S.000+0000")
    start_date = start_dt.strftime("%Y-%m-%dT%H:%M:%S.000+0000")

    return start_date, end_date