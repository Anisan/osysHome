from datetime import datetime


def seconds_to_mm_ss(seconds):
    """
    Преобразует секунды в формат MM:SS.

    Args:
        seconds (int): количество секунд

    Returns:
        str: строка в формате MM:SS
    """
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def mm_ss_to_seconds(mm_ss):
    """
    Преобразует MM:SS в секунды.

    Args:
        mm_ss (str): время в формате MM:SS

    Returns:
        int: количество секунд
    """
    minutes, seconds = map(int, mm_ss.split(":"))
    return minutes * 60 + seconds

def timestamp_to_iso(timestamp):
    """
    Преобразует Unix timestamp в ISO-формат даты.

    Args:
        timestamp (float): Unix timestamp

    Returns:
        str: дата в формате ISO
    """
    return datetime.fromtimestamp(timestamp).isoformat()


def iso_to_timestamp(iso_str):
    """
    Преобразует ISO-строку в Unix timestamp.

    Args:
        iso_str (str): дата в формате ISO

    Returns:
        float: Unix timestamp
    """
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).timestamp()
