""" Cron module"""
import croniter
from app.database import convert_utc_to_local, get_default_timezone
from datetime import datetime, timezone

def nextStartCronJob(cron_string: str) -> datetime:
    """Next cron fire in server DEFAULT_TIMEZONE (naive local wall time).

    Scheduler cycle has no HTTP user; cron wall-clock must follow server timezone,
    not the browser or a random request user.
    """
    server_tz = get_default_timezone()
    current_datetime = convert_utc_to_local(
        datetime.now(timezone.utc),
        timezone=server_tz,
    )
    cron = croniter.croniter(cron_string, current_datetime)
    return cron.get_next(datetime)


def validate_cron_expression(cron_string: str, preview_count: int = 3) -> dict:
    """Validate cron expression and preview next runs in server timezone."""
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
