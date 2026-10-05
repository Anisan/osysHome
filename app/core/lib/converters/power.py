"""Electrical power and energy conversions."""

def watts_to_va(watts, power_factor=0.8):
    """Convert watts to volt-amperes using a power factor.

    Args:
        watts (float): Active power in watts
        power_factor (float, optional): Power factor. Defaults to 0.8.

    Returns:
        float: Apparent power in VA
    """
    return watts / power_factor

def va_to_watts(va, power_factor=0.8):
    """Convert volt-amperes to watts using a power factor.

    Args:
        va (float): Apparent power in VA
        power_factor (float, optional): Power factor. Defaults to 0.8.

    Returns:
        float: Active power in watts
    """
    return va * power_factor

def wh_to_kwh(wh):
    """Convert watt-hours to kilowatt-hours.

    Args:
        wh (float): Energy in Wh

    Returns:
        float: Energy in kWh
    """
    return wh / 1000.0

def kwh_to_wh(kwh):
    """Convert kilowatt-hours to watt-hours.

    Args:
        kwh (float): Energy in kWh

    Returns:
        float: Energy in Wh
    """
    return kwh * 1000.0
