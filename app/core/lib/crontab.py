"""Cron helpers for scheduler (server timezone)."""
import croniter
from app.database import convert_utc_to_local, get_default_timezone
from datetime import datetime, timezone

def nextStartCronJob(cron_string: str) -> datetime:
    """Compute the next cron fire time in the server default timezone.

    Scheduler has no HTTP user context; wall-clock must follow the server
    timezone, not the browser or a request user.

    Args:
        cron_string (str): Cron expression

    Returns:
        datetime: Next fire time as naive local wall time
    """
    server_tz = get_default_timezone()
    current_datetime = convert_utc_to_local(
        datetime.now(timezone.utc),
        timezone=server_tz,
    )
    cron = croniter.croniter(cron_string, current_datetime)
    return cron.get_next(datetime)


def validate_cron_expression(cron_string: str, preview_count: int = 3) -> dict:
    """Validate a cron expression and preview upcoming runs.

    Args:
        cron_string (str): Cron expression (empty is treated as valid/no schedule)
        preview_count (int, optional): Number of next runs to preview (1-10).
            Defaults to 3.

    Returns:
        dict: On success: ``ok``, ``crontab``, ``next_runs``, ``timezone``.
            On failure: ``ok``, ``crontab``, ``errors``, ``next_runs``.
    """
    text = str(cron_string or "").strip()
    if not text:
        return {"ok": True, "crontab": None, "next_runs": []}

    preview_count = max(1, min(int(preview_count or 3), 10))
    try:
        server_tz = get_default_timezone()
        current_datetime = convert_utc_to_local(
            datetime.now(timezone.utc),
            timezone=server_tz,
        )
        cron = croniter.croniter(text, current_datetime)
        next_runs = []
        for _ in range(preview_count):
            next_runs.append(cron.get_next(datetime).isoformat(sep=" ", timespec="seconds"))
        return {"ok": True, "crontab": text, "next_runs": next_runs, "timezone": server_tz}
    except Exception as ex:  # pylint: disable=broad-except
        return {"ok": False, "crontab": text, "errors": [{"message": str(ex)}], "next_runs": []}
