""" Cron module"""
import croniter
from datetime import datetime

def nextStartCronJob(cron_string: str) -> datetime:
    """ Get next datetime

    Args:
        cron_string (str): Cron string

    Returns:
        datetime: Next datetime
    """
    current_datetime = datetime.now()
    cron = croniter.croniter(cron_string, current_datetime)
    return cron.get_next(datetime)
