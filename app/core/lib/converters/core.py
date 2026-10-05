"""Core type and angle/frequency conversions."""
import math

def convert_to_boolean(value):
    """Convert various value types to a boolean.

    Args:
        value: Any value (str, int, float, bool, etc.)

    Returns:
        bool: Converted boolean
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
    """Convert degrees to radians.

    Args:
        degrees (float): Angle in degrees

    Returns:
        float: Angle in radians
    """
    return math.radians(degrees)


def radians_to_degrees(radians):
    """Convert radians to degrees.

    Args:
        radians (float): Angle in radians

    Returns:
        float: Angle in degrees
    """
    return math.degrees(radians)


def rpm_to_hz(rpm):
    """Convert revolutions per minute to hertz.

    Args:
        rpm (float): Revolutions per minute

    Returns:
        float: Frequency in hertz
    """
    return rpm / 60


def hz_to_rpm(hz):
    """Convert hertz to revolutions per minute.

    Args:
        hz (float): Frequency in hertz

    Returns:
        float: Revolutions per minute
    """
    return hz * 60
