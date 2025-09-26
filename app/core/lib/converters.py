def convert_to_boolean(self, value):
    """Convert various value types to boolean"""
    if isinstance(value, bool):
        return value
    elif isinstance(value, (int, float)):
        return bool(value)
    elif isinstance(value, str):
        return value.lower() in ["true", "1", "on", "yes"]
    else:
        return bool(value)

# Color convertors
def hex_to_rgb(hex_str):
    """
    Преобразует HEX-строку вида '#FF5733' в кортеж (R, G, B) как целые числа 0-255.
    Поддерживает форматы: '#RRGGBB', 'RRGGBB'
    """
    hex_str = hex_str.lstrip("#")
    if len(hex_str) != 6:
        raise ValueError(f"Некорректный HEX-цвет: {hex_str}")
    return tuple(int(hex_str[i: i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(r, g, b):
    """
    Преобразует RGB (0-255) в HEX-строку вида 'FF5733'.
    """
    return f"{r:02X}{g:02X}{b:02X}"


def hex_to_rgb_float(hex_str):
    """
    Преобразует HEX в RGB как float значения от 0.0 до 1.0 (как в ESPHome).
    """
    r, g, b = hex_to_rgb(hex_str)
    return r / 255.0, g / 255.0, b / 255.0


def rgb_float_to_hex(r, g, b):
    """
    Преобразует RGB float (0.0–1.0) в HEX строку.
    """
    return rgb_to_hex(int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


# Percent convertors
def percent_to_decimal(percent):
    """
    Преобразует процент (строку или число) в десятичную дробь.
    Примеры:
        "75%" → 0.75
        50 → 0.5
        "100.5%" → 1.005
    """
    if isinstance(percent, str):
        percent = percent.strip().rstrip('%')
    return float(percent) / 100.0


def decimal_to_percent(decimal, with_symbol=False):
    """
    Преобразует десятичную дробь в процент.
    Примеры:
        0.75 → 75 или "75%"
        1.2 → 120 или "120%"
    """
    p = decimal * 100
    return f"{p}%" if with_symbol else p


def percent_of(percent, max_value):
    """
    Вычисляет абсолютное значение по проценту от заданного максимума (100%).
    Примеры:
        percent_of("75%", 200) → 150.0
        percent_of(25, 80) → 20.0
        percent_of("10%", 1000) → 100.0
    """
    ratio = percent_to_decimal(percent)
    return ratio * max_value


def value_to_percent(value, max_value, with_symbol=False):
    """
    Вычисляет, какой процент составляет value от max_value.
    Примеры:
        value_to_percent(150, 200) → 75.0 или "75.0%"
        value_to_percent(30, 50, True) → "60.0%"
    """
    if max_value == 0:
        raise ValueError("max_value не может быть 0 при вычислении процента")
    ratio = value / max_value
    return decimal_to_percent(ratio, with_symbol)