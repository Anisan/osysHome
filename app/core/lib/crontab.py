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
