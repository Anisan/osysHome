"""Illuminance conversions."""

def lux_to_footcandle(lux):
    """Convert lux to foot-candles.

    Args:
        lux (float): Illuminance in lux

    Returns:
        float: Illuminance in foot-candles
    """
    return lux * 0.092903

def footcandle_to_lux(fc):
    """Convert foot-candles to lux.

    Args:
        fc (float): Illuminance in foot-candles

    Returns:
        float: Illuminance in lux
    """
    return fc / 0.092903
