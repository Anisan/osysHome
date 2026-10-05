"""Wind speed conversions."""

def ms_to_kmh(m_s):
    """Convert meters per second to kilometers per hour.

    Args:
        m_s (float): Speed in m/s

    Returns:
        float: Speed in km/h
    """
    return m_s * 3.6

def kmh_to_ms(kmh):
    """Convert kilometers per hour to meters per second.

    Args:
        kmh (float): Speed in km/h

    Returns:
        float: Speed in m/s
    """
    return kmh / 3.6

def ms_to_mph(m_s):
    """Convert meters per second to miles per hour.

    Args:
        m_s (float): Speed in m/s

    Returns:
        float: Speed in mph
    """
    return m_s * 2.23694

def mph_to_ms(mph):
    """Convert miles per hour to meters per second.

    Args:
        mph (float): Speed in mph

    Returns:
        float: Speed in m/s
    """
    return mph / 2.23694
