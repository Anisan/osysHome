import math


def hex_to_rgb(hex_str):
    """
    Преобразует HEX-строку вида '#FF5733' в кортеж (R, G, B) как целые числа 0-255.
    Поддерживает форматы: '#RRGGBB', 'RRGGBB'

    Args:
        hex_str (str): строка в формате HEX

    Returns:
        tuple: (R, G, B) как целые числа
    """
    hex_str = hex_str.lstrip("#")
    if len(hex_str) != 6:
        raise ValueError(f"Некорректный HEX-цвет: {hex_str}")
    return tuple(int(hex_str[i: i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(r, g, b):
    """
    Преобразует RGB (0-255) в HEX-строку вида 'FF5733'.

    Args:
        r, g, b (int): значения от 0 до 255

    Returns:
        str: HEX строка
    """
    return f"{r:02X}{g:02X}{b:02X}"


def hex_to_rgb_float(hex_str):
    """
    Преобразует HEX в RGB как float значения от 0.0 до 1.0 (как в ESPHome).

    Args:
        hex_str (str): строка в формате HEX

    Returns:
        tuple: (R, G, B) как float от 0.0 до 1.0
    """
    r, g, b = hex_to_rgb(hex_str)
    return r / 255.0, g / 255.0, b / 255.0


def rgb_float_to_hex(r, g, b):
    """
    Преобразует RGB float (0.0–1.0) в HEX строку.

    Args:
        r, g, b (float): значения от 0.0 до 1.0

    Returns:
        str: HEX строка
    """
    return rgb_to_hex(int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


def rgb_to_hsl(r, g, b):
    """
    Преобразует RGB в HSL.

    Args:
        r, g, b (int): значения от 0 до 255

    Returns:
        tuple: (H, S, L) - Hue (0-360), Saturation (0-100%), Lightness (0-100%)
    """
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    diff = max_c - min_c

    if diff == 0:
        h = 0
    elif max_c == r:
        h = (60 * ((g - b) / diff) + 360) % 360
    elif max_c == g:
        h = (60 * ((b - r) / diff) + 120) % 360
    elif max_c == b:
        h = (60 * ((r - g) / diff) + 240) % 360

    l = (max_c + min_c) / 2 # noqa

    if diff == 0:
        s = 0
    else:
        s = diff / (2 - max_c - min_c) if l > 0.5 else diff / (max_c + min_c)

    return round(h), round(s * 100), round(l * 100)


def hsl_to_rgb(h, s, l): # noqa
    """
    Преобразует HSL в RGB.

    Args:
        h (int): Hue (0-360)
        s (int): Saturation (0-100%)
        l (int): Lightness (0-100%)

    Returns:
        tuple: (R, G, B) как целые числа
    """
    h = h / 360.0
    s = s / 100.0
    l = l / 100.0 # noqa

    def hue_to_rgb(p, q, t):
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    if s == 0:
        r = g = b = l
    else:
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        r = hue_to_rgb(p, q, h + 1 / 3)
        g = hue_to_rgb(p, q, h)
        b = hue_to_rgb(p, q, h - 1 / 3)

    return round(r * 255), round(g * 255), round(b * 255)


def rgb_to_hsv(r, g, b):
    """
    Преобразует RGB в HSV.

    Args:
        r, g, b (int): значения от 0 до 255

    Returns:
        tuple: (H, S, V) - Hue (0-360), Saturation (0-100%), Value (0-100%)
    """
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    diff = max_c - min_c

    if max_c == 0:
        s = 0
    else:
        s = diff / max_c

    if diff == 0:
        h = 0
    else:
        if max_c == r:
            h = (60 * ((g - b) / diff) + 360) % 360
        elif max_c == g:
            h = (60 * ((b - r) / diff) + 120) % 360
        elif max_c == b:
            h = (60 * ((r - g) / diff) + 240) % 360

    v = max_c
    return round(h), round(s * 100), round(v * 100)


def hsv_to_rgb(h, s, v):
    """
    Преобразует HSV в RGB.

    Args:
        h (int): Hue (0-360)
        s (int): Saturation (0-100%)
        v (int): Value (0-100%)

    Returns:
        tuple: (R, G, B) как целые числа
    """
    h = h / 360.0
    s = s / 100.0
    v = v / 100.0

    i = int(h * 6)
    f = h * 6 - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)

    if i % 6 == 0:
        r, g, b = v, t, p
    elif i % 6 == 1:
        r, g, b = q, v, p
    elif i % 6 == 2:
        r, g, b = p, v, t
    elif i % 6 == 3:
        r, g, b = p, q, v
    elif i % 6 == 4:
        r, g, b = t, p, v
    elif i % 6 == 5:
        r, g, b = v, p, q

    return round(r * 255), round(g * 255), round(b * 255)


def xyz_to_rgb(x, y, z):
    """
    Преобразует XYZ в RGB.

    Args:
        x, y, z (float): значения XYZ (обычно 0-100)

    Returns:
        tuple: (R, G, B) как целые числа
    """
    x = x / 100.0
    y = y / 100.0
    z = z / 100.0

    r = x * 3.2406 + y * -1.5372 + z * -0.4986
    g = x * -0.9689 + y * 1.8758 + z * 0.0415
    b = x * 0.0557 + y * -0.2040 + z * 1.0570

    def gamma_correct(val):
        if val > 0.0031308:
            return 1.055 * (val ** (1 / 2.4)) - 0.055
        else:
            return 12.92 * val

    r = gamma_correct(r)
    g = gamma_correct(g)
    b = gamma_correct(b)

    return round(r * 255), round(g * 255), round(b * 255)


def rgb_to_xyz(r, g, b):
    """
    Преобразует RGB в XYZ.

    Args:
        r, g, b (int): значения от 0 до 255

    Returns:
        tuple: (X, Y, Z) как float
    """
    r = r / 255.0
    g = g / 255.0
    b = b / 255.0

    def gamma_reverse(val):
        if val > 0.04045:
            return ((val + 0.055) / 1.055) ** 2.4
        else:
            return val / 12.92

    r = gamma_reverse(r)
    g = gamma_reverse(g)
    b = gamma_reverse(b)

    x = r * 0.4124 + g * 0.3576 + b * 0.1805
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = r * 0.0193 + g * 0.1192 + b * 0.9505

    return x * 100, y * 100, z * 100


def xyz_to_xyY(x, y, z):
    """
    Преобразует XYZ в xyY.

    Args:
        x, y, z (float): значения XYZ

    Returns:
        tuple: (x, y, Y) - координаты хроматичности и яркость
    """
    sum_xyz = x + y + z
    if sum_xyz == 0:
        return 0, 0, y
    x_norm = x / sum_xyz
    y_norm = y / sum_xyz
    Y = y
    return x_norm, y_norm, Y


def xyY_to_xyz(x, y, Y):
    """
    Преобразует xyY в XYZ.

    Args:
        x, y (float): координаты хроматичности
        Y (float): яркость

    Returns:
        tuple: (X, Y, Z) как float
    """
    if y == 0:
        return 0, 0, 0
    X = (x / y) * Y
    Z = ((1 - x - y) / y) * Y
    return X, Y, Z


def rgb_to_xyY(r, g, b):
    """
    Преобразует RGB в xyY.

    Args:
        r, g, b (int): значения от 0 до 255

    Returns:
        tuple: (x, y, Y) - координаты хроматичности и яркость
    """
    x, y, z = rgb_to_xyz(r, g, b)
    return xyz_to_xyY(x, y, z)


def xyY_to_rgb(x, y, Y):
    """
    Преобразует xyY в RGB.

    Args:
        x, y (float): координаты хроматичности
        Y (float): яркость

    Returns:
        tuple: (R, G, B) как целые числа
    """
    X, Y, Z = xyY_to_xyz(x, y, Y)
    return xyz_to_rgb(X, Y, Z)


def xyz_to_lab(x, y, z):
    """
    Преобразует XYZ в CIE L*a*b*.

    Args:
        x, y, z (float): значения XYZ

    Returns:
        tuple: (L, a, b) - L* (0-100), a*, b*
    """
    x /= 95.047
    y /= 100.0
    z /= 108.883

    def lab_helper(val):
        return val ** (1 / 3) if val > 0.008856 else (7.787 * val) + (16 / 116)

    fx = lab_helper(x)
    fy = lab_helper(y)
    fz = lab_helper(z)

    L = (116 * fy) - 16
    a = 500 * (fx - fy)
    b = 200 * (fy - fz)

    return L, a, b


COLOR_MAP = {
    (255, 0, 0): "red",
    (0, 255, 0): "green",
    (0, 0, 255): "blue",
    (255, 255, 0): "yellow",
    (255, 0, 255): "magenta",
    (0, 255, 255): "cyan",
    (0, 0, 0): "black",
    (255, 255, 255): "white",
}


def rgb_to_color_name(r, g, b):
    """
    Возвращает имя цвета по RGB значению.

    Args:
        r, g, b (int): значения от 0 до 255

    Returns:
        str: название цвета или "unknown"
    """
    return COLOR_MAP.get((r, g, b), "unknown")


def is_light_color(r, g, b):
    """
    Проверяет, является ли цвет светлым (по яркости).

    Args:
        r, g, b (int): значения от 0 до 255

    Returns:
        bool: True, если цвет светлый
    """
    brightness = (r * 299 + g * 587 + b * 114) / 1000
    return brightness > 128


def rgb_to_kelvin(r, g, b):
    """
    Приближённо вычисляет температуру цвета в Кельвинах по значению RGB.
    Работает только для "белых" цветов (близких к нейтральному белому).

    Args:
        r, g, b (int): значения от 0 до 255

    Returns:
        int: температура в Кельвинах (примерно)
    """
    r, g, b = r / 255.0, g / 255.0, b / 255.0

    if r == 0 and g == 0 and b == 0:
        return 6500

    if g == 0:
        return 6500

    if r > b:
        t = (r - b) / g
        kelvin = 6600 - 3200 * t
    else:
        t = (b - r) / g
        kelvin = 6600 + 3200 * t

    return max(1000, min(40000, round(kelvin)))


def kelvin_to_rgb(kelvin):
    """
    Приближенно преобразует температуру в Кельвинах в RGB.
    Диапазон: 1000K - 40000K
    """
    temp = kelvin / 100.0
    if temp <= 66:
        r = 255
        g = temp
        g = 99.4708025861 * math.log(g) - 161.1195681661
    else:
        r = temp - 60
        r = 329.698727446 * (r**-0.1332047592)
        g = temp - 60
        g = 288.1221695283 * (g**-0.0755148492)

    if temp >= 66:
        b = 255
    elif temp <= 19:
        b = 0
    else:
        b = temp - 10
        b = 138.5177312231 * math.log(b) - 305.0447927307

    return (
        max(0, min(255, round(r))),
        max(0, min(255, round(g))),
        max(0, min(255, round(b))),
    )
