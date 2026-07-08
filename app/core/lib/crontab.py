""" Cron module"""
import croniter
from app.database import convert_utc_to_local
from datetime import datetime, timezone

def nextStartCronJob(cron_string: str) -> datetime:
    """ Get next datetime

    Args:
        cron_string (str): Cron string

    Returns:
        datetime: Next datetime
    """
    current_datetime = datetime.now(timezone.utc)
    current_datetime = convert_utc_to_local(current_datetime)
    cron = croniter.croniter(cron_string, current_datetime)
    return cron.get_next(datetime)


def validate_cron_expression(cron_string: str, preview_count: int = 3) -> dict:
    """Validate cron expression and return upcoming run times in local timezone."""
    text = str(cron_string or "").strip()
    if not text:
        return {"ok": True, "crontab": None, "next_runs": []}

    preview_count = max(1, min(int(preview_count or 3), 10))
    try:
        current_datetime = convert_utc_to_local(datetime.now(timezone.utc))
        cron = croniter.croniter(text, current_datetime)
        next_runs = []
        for _ in range(preview_count):
            next_runs.append(cron.get_next(datetime).isoformat(sep=" ", timespec="seconds"))
        return {"ok": True, "crontab": text, "next_runs": next_runs}
    except Exception as ex:  # pylint: disable=broad-except
        return {"ok": False, "crontab": text, "errors": [{"message": str(ex)}], "next_runs": []}
