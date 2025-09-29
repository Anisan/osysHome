import math

def calculate_dew_point(temperature_celsius, humidity_percent):
    """
    Рассчитывает точку росы по температуре и влажности.

    Args:
        temperature_celsius (float): температура в градусах Цельсия
        humidity_percent (float): влажность в процентах (0-100)

    Returns:
        float: точка росы в градусах Цельсия
    """
    a = 17.27
    b = 237.7
    alpha = (a * temperature_celsius) / (b + temperature_celsius) + math.log(humidity_percent / 100.0)
    dew_point = (b * alpha) / (a - alpha)
    return dew_point

def absolute_humidity(temperature_celsius, humidity_percent):
    """
    Рассчитывает абсолютную влажность в г/м³.

    Args:
        temperature_celsius (float): температура в градусах Цельсия
        humidity_percent (float): относительная влажность в процентах (0-100)

    Returns:
        float: абсолютная влажность в г/м³
    """
    saturation_pressure = 6.112 * math.exp((17.67 * temperature_celsius) / (temperature_celsius + 243.5))
    vapor_pressure = saturation_pressure * (humidity_percent / 100.0)
    absolute_humidity = (216.7 * vapor_pressure) / (273.15 + temperature_celsius)
    return absolute_humidity
