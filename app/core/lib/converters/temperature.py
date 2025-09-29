def celsius_to_fahrenheit(celsius):
    """
    Преобразует температуру из Цельсия в Фаренгейт.

    Args:
        celsius (float): температура в градусах Цельсия

    Returns:
        float: температура в градусах Фаренгейта
    """
    return (celsius * 9 / 5) + 32

def fahrenheit_to_celsius(fahrenheit):
    """
    Преобразует температуру из Фаренгейта в Цельсий.

    Args:
        fahrenheit (float): температура в градусах Фаренгейта

    Returns:
        float: температура в градусах Цельсия
    """
    return (fahrenheit - 32) * 5 / 9

def celsius_to_kelvin(celsius):
    """Преобразует температуру из Цельсия в Кельвины."""
    return celsius + 273.15

def kelvin_to_celsius(kelvin):
    """Преобразует температуру из Кельвинов в Цельсии."""
    return kelvin - 273.15

def calculate_heat_index(temperature_fahrenheit, humidity_percent):
    """
    Рассчитывает температуру ощущения (Heat Index) в градусах Фаренгейта.

    Args:
        temperature_fahrenheit (float): температура в градусах Фаренгейта
        humidity_percent (float): влажность в процентах (0-100)

    Returns:
        float: температура ощущения в градусах Фаренгейта
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
