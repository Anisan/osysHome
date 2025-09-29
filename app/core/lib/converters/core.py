import math

def convert_to_boolean(value):
    """
    Преобразует различные типы данных в boolean.

    Args:
        value: любое значение (str, int, float, bool и др.)

    Returns:
        bool: результат преобразования
    """
    if isinstance(value, bool):
        return value
    elif isinstance(value, (int, float)):
        return bool(value)
    elif isinstance(value, str):
        return value.lower() in ["true", "1", "on", "yes", "t", "y"]
    else:
        return bool(value)


def degrees_to_radians(degrees):
    """
    Преобразует градусы в радианы.

    Args:
        degrees (float): угол в градусах

    Returns:
        float: угол в радианах
    """
    return math.radians(degrees)


def radians_to_degrees(radians):
    """
    Преобразует радианы в градусы.

    Args:
        radians (float): угол в радианах

    Returns:
        float: угол в градусах
    """
    return math.degrees(radians)


def rpm_to_hz(rpm):
    """
    Преобразует обороты в минуту в герцы.

    Args:
        rpm (float): обороты в минуту

    Returns:
        float: частота в герцах
    """
    return rpm / 60


def hz_to_rpm(hz):
    """
    Преобразует герцы в обороты в минуту.

    Args:
        hz (float): частота в герцах

    Returns:
        float: обороты в минуту
    """
    return hz * 60
