"""Color space conversions, named colors, and Zigbee2MQTT payloads."""

import math
import json


def hex_to_rgb(hex_str):
    """Parse a hex color string into an RGB triplet.

    Supports ``#RRGGBB`` and ``RRGGBB``.

    Args:
        hex_str (str): Hex color string.

    Returns:
        tuple: ``(R, G, B)`` integers in 0–255.
    """
    hex_str = hex_str.lstrip("#")
    if len(hex_str) != 6:
        raise ValueError(f"Некорректный HEX-цвет: {hex_str}")
    return tuple(int(hex_str[i: i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(r, g, b):
    """Format RGB channels as a six-digit hex string (no leading ``#``).

    Args:
        r (int): Red channel (0–255).
        g (int): Green channel (0–255).
        b (int): Blue channel (0–255).

    Returns:
        str: Uppercase hex string ``RRGGBB``.
    """
    return f"{r:02X}{g:02X}{b:02X}"


def hex_to_rgb_float(hex_str):
    """Parse hex into normalized RGB floats (0.0–1.0), ESPHome-style.

    Args:
        hex_str (str): Hex color string.

    Returns:
        tuple: ``(R, G, B)`` floats in 0.0–1.0.
    """
    r, g, b = hex_to_rgb(hex_str)
    return r / 255.0, g / 255.0, b / 255.0


def rgb_float_to_hex(r, g, b):
    """Convert normalized RGB floats to a hex string.

    Args:
        r (float): Red channel (0.0–1.0).
        g (float): Green channel (0.0–1.0).
        b (float): Blue channel (0.0–1.0).

    Returns:
        str: Uppercase hex string ``RRGGBB``.
    """
    return rgb_to_hex(int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


def rgb_to_hsl(r, g, b):
    """Convert RGB to HSL.

    Args:
        r (int): Red channel (0–255).
        g (int): Green channel (0–255).
        b (int): Blue channel (0–255).

    Returns:
        tuple: ``(H, S, L)`` — hue 0–360, saturation and lightness 0–100%.
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
    """Convert HSL to RGB.

    Args:
        h (int): Hue (0–360).
        s (int): Saturation (0–100%).
        l (int): Lightness (0–100%).

    Returns:
        tuple: ``(R, G, B)`` integers in 0–255.
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
    """Convert RGB to HSV.

    Args:
        r (int): Red channel (0–255).
        g (int): Green channel (0–255).
        b (int): Blue channel (0–255).

    Returns:
        tuple: ``(H, S, V)`` — hue 0–360, saturation and value 0–100%.
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
    """Convert HSV to RGB.

    Args:
        h (int): Hue (0–360).
        s (int): Saturation (0–100%).
        v (int): Value (0–100%).

    Returns:
        tuple: ``(R, G, B)`` integers in 0–255.
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
    """Convert CIE XYZ to sRGB.

    Args:
        x (float): X component (typically 0–100).
        y (float): Y component (typically 0–100).
        z (float): Z component (typically 0–100).

    Returns:
        tuple: ``(R, G, B)`` integers in 0–255.
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

    return (
        max(0, min(255, round(r * 255))),
        max(0, min(255, round(g * 255))),
        max(0, min(255, round(b * 255))),
    )


def rgb_to_xyz(r, g, b):
    """Convert sRGB to CIE XYZ.

    Args:
        r (int): Red channel (0–255).
        g (int): Green channel (0–255).
        b (int): Blue channel (0–255).

    Returns:
        tuple: ``(X, Y, Z)`` floats (Y scale ~0–100).
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
    """Convert CIE XYZ to chromaticity xy and luminance Y.

    Args:
        x (float): X component.
        y (float): Y component.
        z (float): Z component.

    Returns:
        tuple: ``(x, y, Y)`` chromaticity and luminance.
    """
    sum_xyz = x + y + z
    if sum_xyz == 0:
        return 0, 0, y
    x_norm = x / sum_xyz
    y_norm = y / sum_xyz
    Y = y
    return x_norm, y_norm, Y


def xyY_to_xyz(x, y, Y):
    """Convert chromaticity xy and luminance Y to CIE XYZ.

    Args:
        x (float): Chromaticity x.
        y (float): Chromaticity y.
        Y (float): Luminance.

    Returns:
        tuple: ``(X, Y, Z)`` floats.
    """
    if y == 0:
        return 0, 0, 0
    X = (x / y) * Y
    Z = ((1 - x - y) / y) * Y
    return X, Y, Z


def rgb_to_xyY(r, g, b):
    """Convert RGB to chromaticity xy and luminance Y.

    Args:
        r (int): Red channel (0–255).
        g (int): Green channel (0–255).
        b (int): Blue channel (0–255).

    Returns:
        tuple: ``(x, y, Y)`` chromaticity and luminance.
    """
    x, y, z = rgb_to_xyz(r, g, b)
    return xyz_to_xyY(x, y, z)


def rgb_to_xy(r, g, b):
    """Convert RGB to CIE xy chromaticity (luminance omitted).

    Args:
        r (int): Red channel (0–255).
        g (int): Green channel (0–255).
        b (int): Blue channel (0–255).

    Returns:
        tuple: ``(x, y)`` chromaticity coordinates.
    """
    x, y, _ = rgb_to_xyY(r, g, b)
    return x, y


def xyY_to_rgb(x, y, Y):
    """Convert chromaticity xy and luminance Y to RGB.

    Args:
        x (float): Chromaticity x.
        y (float): Chromaticity y.
        Y (float): Luminance.

    Returns:
        tuple: ``(R, G, B)`` integers in 0–255.
    """
    X, Y, Z = xyY_to_xyz(x, y, Y)
    return xyz_to_rgb(X, Y, Z)


def xy_to_rgb(x, y, y_luminance=None):
    """Convert CIE xy chromaticity to RGB with optional luminance.

    Args:
        x (float): Chromaticity x.
        y (float): Chromaticity y.
        y_luminance (float, optional): Luminance Y; defaults to 1.0.

    Returns:
        tuple: ``(R, G, B)`` integers in 0–255.
    """
    luminance = 1.0 if y_luminance is None else float(y_luminance)
    return xyY_to_rgb(float(x), float(y), luminance)


def xyz_to_lab(x, y, z):
    """Convert CIE XYZ to CIE L*a*b*.

    Args:
        x (float): X component.
        y (float): Y component.
        z (float): Z component.

    Returns:
        tuple: ``(L, a, b)`` — L* roughly 0–100.
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


# English CSS-style color names only (language-neutral API contract).
COLOR_NAME_MAP = {
    # basics
    "red": (255, 0, 0),
    "green": (0, 128, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "magenta": (255, 0, 255),
    "fuchsia": (255, 0, 255),
    "cyan": (0, 255, 255),
    "aqua": (0, 255, 255),
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    # extended
    "orange": (255, 165, 0),
    "orangered": (255, 69, 0),
    "purple": (128, 0, 128),
    "violet": (238, 130, 238),
    "indigo": (75, 0, 130),
    "pink": (255, 192, 203),
    "hotpink": (255, 105, 180),
    "brown": (165, 42, 42),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
    "silver": (192, 192, 192),
    "gold": (255, 215, 0),
    "navy": (0, 0, 128),
    "teal": (0, 128, 128),
    "lime": (0, 255, 0),
    "limegreen": (50, 205, 50),
    "olive": (128, 128, 0),
    "maroon": (128, 0, 0),
    "coral": (255, 127, 80),
    "salmon": (250, 128, 114),
    "crimson": (220, 20, 60),
    "tomato": (255, 99, 71),
    "turquoise": (64, 224, 208),
    "skyblue": (135, 206, 235),
    "deepskyblue": (0, 191, 255),
    "lightblue": (173, 216, 230),
    "lightgreen": (144, 238, 144),
    "darkblue": (0, 0, 139),
    "darkgreen": (0, 100, 0),
    "darkred": (139, 0, 0),
    "darkgray": (169, 169, 169),
    "darkgrey": (169, 169, 169),
    "lightgray": (211, 211, 211),
    "lightgrey": (211, 211, 211),
    "beige": (245, 245, 220),
    "ivory": (255, 255, 240),
    "khaki": (240, 230, 140),
    "lavender": (230, 230, 250),
    "plum": (221, 160, 221),
    "orchid": (218, 112, 214),
    "tan": (210, 180, 140),
    "chocolate": (210, 105, 30),
    "sienna": (160, 82, 45),
    "peru": (205, 133, 63),
    "wheat": (245, 222, 179),
    "snow": (255, 250, 250),
    "mint": (189, 252, 201),
    "mintcream": (245, 255, 250),
    "chartreuse": (127, 255, 0),
    "springgreen": (0, 255, 127),
    "seagreen": (46, 139, 87),
    "forestgreen": (34, 139, 34),
    "royalblue": (65, 105, 225),
    "steelblue": (70, 130, 180),
    "slateblue": (106, 90, 205),
    "slategray": (112, 128, 144),
    "slategrey": (112, 128, 144),
    # HTML color names (https://htmlcolorcodes.com/color-names/)
    "aliceblue": (240, 248, 255),
    "antiquewhite": (250, 235, 215),
    "aquamarine": (127, 255, 212),
    "azure": (240, 255, 255),
    "bisque": (255, 228, 196),
    "blanchedalmond": (255, 235, 205),
    "blueviolet": (138, 43, 226),
    "burlywood": (222, 184, 135),
    "cadetblue": (95, 158, 160),
    "cornflowerblue": (100, 149, 237),
    "cornsilk": (255, 248, 220),
    "darkcyan": (0, 139, 139),
    "darkgoldenrod": (184, 134, 11),
    "darkkhaki": (189, 183, 107),
    "darkmagenta": (139, 0, 139),
    "darkolivegreen": (85, 107, 47),
    "darkorange": (255, 140, 0),
    "darkorchid": (153, 50, 204),
    "darksalmon": (233, 150, 122),
    "darkseagreen": (143, 188, 139),
    "darkslateblue": (72, 61, 139),
    "darkslategray": (47, 79, 79),
    "darkslategrey": (47, 79, 79),
    "darkturquoise": (0, 206, 209),
    "darkviolet": (148, 0, 211),
    "deeppink": (255, 20, 147),
    "dimgray": (105, 105, 105),
    "dimgrey": (105, 105, 105),
    "dodgerblue": (30, 144, 255),
    "firebrick": (178, 34, 34),
    "floralwhite": (255, 250, 240),
    "gainsboro": (220, 220, 220),
    "ghostwhite": (248, 248, 255),
    "goldenrod": (218, 165, 32),
    "greenyellow": (173, 255, 47),
    "honeydew": (240, 255, 240),
    "indianred": (205, 92, 92),
    "lavenderblush": (255, 240, 245),
    "lawngreen": (124, 252, 0),
    "lemonchiffon": (255, 250, 205),
    "lightcoral": (240, 128, 128),
    "lightcyan": (224, 255, 255),
    "lightgoldenrodyellow": (250, 250, 210),
    "lightpink": (255, 182, 193),
    "lightsalmon": (255, 160, 122),
    "lightseagreen": (32, 178, 170),
    "lightskyblue": (135, 206, 250),
    "lightslategray": (119, 136, 153),
    "lightslategrey": (119, 136, 153),
    "lightsteelblue": (176, 196, 222),
    "lightyellow": (255, 255, 224),
    "linen": (250, 240, 230),
    "mediumaquamarine": (102, 205, 170),
    "mediumblue": (0, 0, 205),
    "mediumorchid": (186, 85, 211),
    "mediumpurple": (147, 112, 219),
    "mediumseagreen": (60, 179, 113),
    "mediumslateblue": (123, 104, 238),
    "mediumspringgreen": (0, 250, 154),
    "mediumturquoise": (72, 209, 204),
    "mediumvioletred": (199, 21, 133),
    "midnightblue": (25, 25, 112),
    "mistyrose": (255, 228, 225),
    "moccasin": (255, 228, 181),
    "navajowhite": (255, 222, 173),
    "oldlace": (253, 245, 230),
    "olivedrab": (107, 142, 35),
    "palegoldenrod": (238, 232, 170),
    "palegreen": (152, 251, 152),
    "paleturquoise": (175, 238, 238),
    "palevioletred": (219, 112, 147),
    "papayawhip": (255, 239, 213),
    "peachpuff": (255, 218, 185),
    "powderblue": (176, 224, 230),
    "rebeccapurple": (102, 51, 153),
    "rosybrown": (188, 143, 143),
    "saddlebrown": (139, 69, 19),
    "sandybrown": (244, 164, 96),
    "seashell": (255, 245, 238),
    "thistle": (216, 191, 216),
    "whitesmoke": (245, 245, 245),
    "yellowgreen": (154, 205, 50),
    # smart-home (legacy RGB, kept for backward compatibility)
    "warmwhite": (255, 244, 229),
    "coolwhite": (229, 244, 255),
    "daylight": (255, 255, 251),
    "offwhite": (253, 245, 230),
}

COLOR_MAP = {}


def is_color_name(value):
    """Return whether the string is a known English color name.

    Args:
        value: Value to check (typically a string).

    Returns:
        bool: True if ``value`` is a registered color name.
    """
    if not isinstance(value, str):
        return False
    return value.strip().lower() in COLOR_NAME_MAP


def parse_color_name(name):
    """Resolve an English color name to RGB.

    Supports CSS/HTML and smart-home names (e.g. warmwhite, relax).
    Localized names are not accepted; use hex, rgb, or xy instead.

    Args:
        name (str): Color name (case-insensitive).

    Returns:
        tuple: ``(R, G, B)`` integers in 0–255.
    """
    if not isinstance(name, str):
        raise ValueError("Color name must be a string")
    normalized = name.strip().lower()
    if normalized not in COLOR_NAME_MAP:
        raise ValueError(f"Unknown color name: {name}")
    return COLOR_NAME_MAP[normalized]


def rgb_to_color_name(r, g, b):
    """Look up a registered color name for an exact RGB triplet.

    Args:
        r (int): Red channel (0–255).
        g (int): Green channel (0–255).
        b (int): Blue channel (0–255).

    Returns:
        str: Color name, or ``"unknown"`` if not in the map.
    """
    return COLOR_MAP.get((r, g, b), "unknown")


def is_light_color(r, g, b):
    """Return whether the color is perceptually light (luminance threshold).

    Args:
        r (int): Red channel (0–255).
        g (int): Green channel (0–255).
        b (int): Blue channel (0–255).

    Returns:
        bool: True if weighted brightness exceeds 128.
    """
    brightness = (r * 299 + g * 587 + b * 114) / 1000
    return brightness > 128


def rgb_to_kelvin(r, g, b):
    """Estimate correlated color temperature in Kelvin from RGB.

    Intended for near-white colors only.

    Args:
        r (int): Red channel (0–255).
        g (int): Green channel (0–255).
        b (int): Blue channel (0–255).

    Returns:
        int: Approximate color temperature in Kelvin (clamped 1000–40000).
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
    """Approximate RGB for a black-body color temperature.

    Args:
        kelvin (int or float): Color temperature (roughly 1000–40000 K).

    Returns:
        tuple: ``(R, G, B)`` integers in 0–255.
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


def _build_smart_home_color_names():
    """CCT whites and scene presets for smart-home automations."""
    names = {}
    for name, kelvin in {
        "candlelight": 2000,
        "candle": 2000,
        "bedtime": 1800,
        "nightlight": 2000,
        "relax": 2200,
        "softwhite": 2700,
        "incandescent": 2700,
        "neutralwhite": 4000,
        "naturalwhite": 4000,
        "reading": 4000,
        "brightwhite": 5000,
        "energize": 6500,
        "arcticwhite": 7500,
        "coldwhite": 7500,
    }.items():
        names[name] = kelvin_to_rgb(kelvin)
    names.update({
        "sunset": (255, 120, 60),
        "amber": (255, 191, 0),
        "fire": (255, 80, 20),
    })
    return names


COLOR_NAME_MAP.update(_build_smart_home_color_names())
for _name, _rgb in COLOR_NAME_MAP.items():
    COLOR_MAP.setdefault(_rgb, _name)


def hsb_to_rgb(h, s, b):
    """Convert HSB to RGB (HSB is treated as HSV in this module).

    Args:
        h (int): Hue (0–360).
        s (int): Saturation (0–100%).
        b (int): Brightness (0–100%).

    Returns:
        tuple: ``(R, G, B)`` integers in 0–255.
    """
    return hsv_to_rgb(h, s, b)


def rgb_to_hsb(r, g, b):
    """Convert RGB to HSB (HSB is treated as HSV in this module).

    Args:
        r (int): Red channel (0–255).
        g (int): Green channel (0–255).
        b (int): Blue channel (0–255).

    Returns:
        tuple: ``(H, S, B)`` — hue 0–360, saturation and brightness 0–100%.
    """
    return rgb_to_hsv(r, g, b)


def kelvin_to_mired(kelvin):
    """Convert color temperature in Kelvin to mired (micro reciprocal degree).

    Args:
        kelvin (float): Color temperature in Kelvin (must be > 0).

    Returns:
        int: Mired value (rounded).

    Raises:
        ValueError: If kelvin is not positive.
    """
    kelvin = float(kelvin)
    if kelvin <= 0:
        raise ValueError("kelvin must be > 0")
    return round(1000000.0 / kelvin)


def mired_to_kelvin(mired):
    """Convert mired to color temperature in Kelvin.

    Args:
        mired (float): Mired value (must be > 0).

    Returns:
        int: Color temperature in Kelvin (rounded).

    Raises:
        ValueError: If mired is not positive.
    """
    mired = float(mired)
    if mired <= 0:
        raise ValueError("mired must be > 0")
    return round(1000000.0 / mired)


def normalize_hue_sat(h, s, hue_scale=360, sat_scale=100):
    """Scale hue and saturation into 0–360 and 0–100.

    Args:
        h (float): Hue in source scale.
        s (float): Saturation in source scale.
        hue_scale (float): Full-scale hue of the source (default 360).
        sat_scale (float): Full-scale saturation of the source (default 100).

    Returns:
        tuple: ``(h_norm, s_norm)`` clamped to standard ranges.
    """
    hue_scale = float(hue_scale or 360)
    sat_scale = float(sat_scale or 100)
    h_norm = (float(h) * 360.0) / hue_scale
    s_norm = (float(s) * 100.0) / sat_scale
    h_norm = max(0.0, min(360.0, h_norm))
    s_norm = max(0.0, min(100.0, s_norm))
    return h_norm, s_norm


def denormalize_hue_sat(h, s, hue_scale=360, sat_scale=100):
    """Map normalized hue/saturation into custom scales.

    Args:
        h (float): Hue in 0–360.
        s (float): Saturation in 0–100.
        hue_scale (float): Target hue full scale (default 360).
        sat_scale (float): Target saturation full scale (default 100).

    Returns:
        tuple: ``(h_raw, s_raw)`` rounded to three decimal places.
    """
    hue_scale = float(hue_scale or 360)
    sat_scale = float(sat_scale or 100)
    h_raw = (float(h) * hue_scale) / 360.0
    s_raw = (float(s) * sat_scale) / 100.0
    return round(h_raw, 3), round(s_raw, 3)


def parse_rgb_string(value):
    """Parse a comma-separated ``R,G,B`` string.

    Args:
        value (str): Three decimal channel values separated by commas.

    Returns:
        tuple: ``(R, G, B)`` integers in 0–255.
    """
    if not isinstance(value, str):
        raise ValueError("rgb string must be a string")
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 3:
        raise ValueError(f"Invalid rgb string: {value}")
    r, g, b = (int(p) for p in parts)
    for channel in (r, g, b):
        if channel < 0 or channel > 255:
            raise ValueError(f"RGB channel out of range: {channel}")
    return r, g, b


def _safe_rgb_from_universal(univ):
    """Derive an RGB triplet from a universal color dict (rgb or xy)."""
    rgb = univ.get("rgb")
    if isinstance(rgb, (list, tuple)) and len(rgb) == 3:
        return int(rgb[0]), int(rgb[1]), int(rgb[2])
    xy = univ.get("xy")
    if isinstance(xy, (list, tuple)) and len(xy) == 2:
        return xy_to_rgb(float(xy[0]), float(xy[1]))
    raise ValueError("Universal color must contain rgb or xy")


def build_zigbee2mqtt_color(univ, fmt_hint=None):
    """Build a Zigbee2MQTT ``color`` command payload from a universal color dict.

    Args:
        univ (dict): Universal color with rgb, xy, hs, or hsv/hsb fields.
        fmt_hint (str, optional): Preferred encoding (``xy``, ``hs``, ``hsv``, ``hsb``).

    Returns:
        dict: Payload shaped as ``{"color": {...}}``.
    """
    if not isinstance(univ, dict):
        raise ValueError("Universal color must be a dict")

    hint = (fmt_hint or "").lower()
    if hint == "xy" and "xy" in univ:
        return {"color": {"x": float(univ["xy"][0]), "y": float(univ["xy"][1])}}
    if hint in ("hs", "hue_saturation"):
        hs = univ.get("hs")
        if hs and len(hs) == 2:
            return {"color": {"hue": round(float(hs[0]), 3), "saturation": round(float(hs[1]), 3)}}
    if hint in ("hsv", "hsb") and hint in univ:
        values = univ[hint]
        if isinstance(values, (list, tuple)) and len(values) == 3:
            return {"color": {hint: f"{values[0]},{values[1]},{values[2]}"}}

    if "xy" in univ:
        return {"color": {"x": float(univ["xy"][0]), "y": float(univ["xy"][1])}}
    if "hs" in univ and isinstance(univ["hs"], (list, tuple)) and len(univ["hs"]) == 2:
        return {
            "color": {
                "hue": round(float(univ["hs"][0]), 3),
                "saturation": round(float(univ["hs"][1]), 3),
            }
        }
    rgb = _safe_rgb_from_universal(univ)
    return {"color": {"r": rgb[0], "g": rgb[1], "b": rgb[2]}}


def color_json_dumps(value):
    """Serialize a color value to compact, stable JSON for storage.

    Args:
        value: JSON-serializable color structure.

    Returns:
        str: JSON string with sorted keys and minimal separators.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
