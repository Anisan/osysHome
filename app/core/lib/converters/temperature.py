"""Temperature unit conversions and heat index."""

def celsius_to_fahrenheit(celsius):
    """Convert Celsius to Fahrenheit.

    Args:
        celsius (float): Temperature in Celsius

    Returns:
        float: Temperature in Fahrenheit
    """
    return (celsius * 9 / 5) + 32

def fahrenheit_to_celsius(fahrenheit):
    """Convert Fahrenheit to Celsius.

    Args:
        fahrenheit (float): Temperature in Fahrenheit

    Returns:
        float: Temperature in Celsius
    """
    return (fahrenheit - 32) * 5 / 9

def celsius_to_kelvin(celsius):
    """Convert Celsius to Kelvin.

    Args:
        celsius (float): Temperature in Celsius

    Returns:
        float: Temperature in Kelvin
    """
    return celsius + 273.15

def kelvin_to_celsius(kelvin):
    """Convert Kelvin to Celsius.

    Args:
        kelvin (float): Temperature in Kelvin

    Returns:
        float: Temperature in Celsius
    """
    return kelvin - 273.15

def calculate_heat_index(temperature_fahrenheit, humidity_percent):
    """Calculate heat index (feels-like temperature) in Fahrenheit.

    Args:
        temperature_fahrenheit (float): Temperature in Fahrenheit
        humidity_percent (float): Relative humidity (0-100)

    Returns:
        float: Heat index in Fahrenheit
    """
    hi = (
        -42.379 +
        2.04901523 * temperature_fahrenheit +
        10.14333127 * humidity_percent -
        0.22475541 * temperature_fahrenheit * humidity_percent -
        0.00683783 * temperature_fahrenheit**2 -
        0.05481717 * humidity_percent**2 +
        0.00122874 * temperature_fahrenheit**2 * humidity_percent +
        0.00085282 * temperature_fahrenheit * humidity_percent**2 -
        0.00000199 * temperature_fahrenheit**2 * humidity_percent**2
    )
    return hi
