"""Humidity calculations (dew point, absolute humidity)."""
import math

def calculate_dew_point(temperature_celsius, humidity_percent):
    """Calculate dew point from temperature and relative humidity.

    Args:
        temperature_celsius (float): Temperature in Celsius
        humidity_percent (float): Relative humidity (0-100)

    Returns:
        float: Dew point in Celsius
    """
    a = 17.27
    b = 237.7
    alpha = (a * temperature_celsius) / (b + temperature_celsius) + math.log(humidity_percent / 100.0)
    dew_point = (b * alpha) / (a - alpha)
    return dew_point

def absolute_humidity(temperature_celsius, humidity_percent):
    """Calculate absolute humidity in g/m³.

    Args:
        temperature_celsius (float): Temperature in Celsius
        humidity_percent (float): Relative humidity (0-100)

    Returns:
        float: Absolute humidity in g/m³
    """
    saturation_pressure = 6.112 * math.exp((17.67 * temperature_celsius) / (temperature_celsius + 243.5))
    vapor_pressure = saturation_pressure * (humidity_percent / 100.0)
    absolute_humidity = (216.7 * vapor_pressure) / (273.15 + temperature_celsius)
    return absolute_humidity
