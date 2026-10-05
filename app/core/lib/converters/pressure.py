"""Pressure unit conversions."""

def pascals_to_mmhg(pascals):
    """Convert pascals to mmHg.

    Args:
        pascals (float): Pressure in pascals

    Returns:
        float: Pressure in mmHg
    """
    return pascals * 0.00750062


def mmhg_to_pascals(mmhg):
    """Convert mmHg to pascals.

    Args:
        mmhg (float): Pressure in mmHg

    Returns:
        float: Pressure in pascals
    """
    return mmhg / 0.00750062

def hpa_to_mmhg(hpa):
    """Convert hectopascals to mmHg.

    Args:
        hpa (float): Pressure in hPa

    Returns:
        float: Pressure in mmHg
    """
    return hpa * 0.750062

def mmhg_to_hpa(mmhg):
    """Convert mmHg to hectopascals.

    Args:
        mmhg (float): Pressure in mmHg

    Returns:
        float: Pressure in hPa
    """
    return mmhg / 0.750062

def hpa_to_inhg(hpa):
    """Convert hectopascals to inches of mercury.

    Args:
        hpa (float): Pressure in hPa

    Returns:
        float: Pressure in inHg
    """
    return hpa * 0.02953

def inhg_to_hpa(inhg):
    """Convert inches of mercury to hectopascals.

    Args:
        inhg (float): Pressure in inHg

    Returns:
        float: Pressure in hPa
    """
    return inhg / 0.02953
