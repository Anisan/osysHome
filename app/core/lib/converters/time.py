"""Time and timestamp conversion helpers."""
from datetime import datetime


def seconds_to_mm_ss(seconds):
    """Convert seconds to an ``MM:SS`` string.

    Args:
        seconds (int): Duration in seconds

    Returns:
        str: Formatted ``MM:SS`` string
    """
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def mm_ss_to_seconds(mm_ss):
    """Convert an ``MM:SS`` string to seconds.

    Args:
        mm_ss (str): Time in ``MM:SS`` format

    Returns:
        int: Duration in seconds
    """
    minutes, seconds = map(int, mm_ss.split(":"))
    return minutes * 60 + seconds

def timestamp_to_iso(timestamp):
    """Convert a Unix timestamp to an ISO datetime string.

    Args:
        timestamp (float): Unix timestamp

    Returns:
        str: ISO-formatted datetime
    """
    return datetime.fromtimestamp(timestamp).isoformat()


def iso_to_timestamp(iso_str):
    """Convert an ISO datetime string to a Unix timestamp.

    Args:
        iso_str (str): ISO datetime (``Z`` suffix allowed)

    Returns:
        float: Unix timestamp
    """
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).timestamp()
