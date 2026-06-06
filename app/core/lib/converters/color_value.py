import json
import ast
import re
from app.core.lib.converters.color import (
    hex_to_rgb,
    rgb_to_hex,
    rgb_to_xy,
    rgb_to_xyY,
    xy_to_rgb,
    rgb_to_hsv,
    hsv_to_rgb,
    rgb_to_hsl,
    hsl_to_rgb,
    rgb_to_hsb,
    hsb_to_rgb,
    kelvin_to_rgb,
    kelvin_to_mired,
    mired_to_kelvin,
    normalize_hue_sat,
    denormalize_hue_sat,
    parse_rgb_string,
    parse_color_name,
    is_color_name,
    build_zigbee2mqtt_color,
    color_json_dumps,
)


SUPPORTED_FORMATS = {
    "canonical",
    "xy",
    "rgb",
    "hex",
    "hs",
    "hsv",
    "hsl",
    "hsb",
    "color_temp",
    "zigbee2mqtt",
    "name",
    "auto",
}


def _coerce_universal(univ, scales=None):
    """
    Приводит вход к универсальному dict.
    Поддерживает dict, JSON-строки, python-literal строки и legacy raw color строки.
    """
    scales = scales or {}

    if isinstance(univ, dict):
        if "rgb" in univ or "xy" in univ:
            return to_universal(univ)
        return to_universal(parse(univ, write_format="auto", scales=scales))

    if isinstance(univ, str):
        raw = univ.strip()
        if not raw:
            raise ValueError("Universal color string is empty")

        # 1) JSON / python literal dict
        try:
            return to_universal(_load_dict_from_string(raw))
        except Exception:
            pass

        # 2) Raw color string (e.g. #RRGGBB, "46,102,150", etc.)
        parsed = parse(raw, write_format="auto", scales=scales)
        return to_universal(parsed)

    raise ValueError(f"Unsupported universal color type: {type(univ)}")


def _clamp(value, min_val, max_val):
    return max(min_val, min(max_val, value))


def _round_xy(x, y):
    return [round(float(x), 6), round(float(y), 6)]


def _round_luminance(y_value):
    return round(float(y_value), 6)


def _extract_luminance(source, rgb=None):
    """Извлекает Y (яркость xyY) из dict или вычисляет из rgb."""
    if isinstance(source, dict):
        if "Y" in source:
            return float(source["Y"])
        if "luminance" in source:
            return float(source["luminance"])
    if rgb is not None:
        _, _, y_lum = rgb_to_xyY(rgb[0], rgb[1], rgb[2])
        return y_lum
    return None


def _rgb_from_xy(x, y, luminance=None):
    """XY -> RGB с учётом яркости Y (xyY). Без Y результат будет слишком тёмным."""
    if luminance is None:
        raise ValueError("XY to RGB conversion requires luminance (Y)")
    r, g, b = xy_to_rgb(x, y, luminance)
    return [int(r), int(g), int(b)]


def is_xy_only_payload(parsed):
    if not isinstance(parsed, dict):
        return False
    has_xy = "xy" in parsed or ("x" in parsed and "y" in parsed)
    has_rgb = "rgb" in parsed or {"r", "g", "b"} <= set(parsed.keys())
    return has_xy and not has_rgb


def merge_xy_luminance(parsed, existing_univ):
    """При обновлении только xy сохраняет Y из текущего universal-значения."""
    if not is_xy_only_payload(parsed) or not isinstance(existing_univ, dict):
        return parsed
    merged = dict(parsed)
    if "Y" in existing_univ:
        merged["Y"] = existing_univ["Y"]
        return merged
    if "rgb" in existing_univ:
        rgb = existing_univ["rgb"]
        if isinstance(rgb, (list, tuple)) and len(rgb) == 3:
            merged["Y"] = _extract_luminance(None, rgb=rgb)
    return merged


def normalize_hex_input(raw):
    """
    Нормализует hex-ввод: #RRGGBB или RRGGBB -> (r, g, b).
    """
    if isinstance(raw, dict):
        raw = raw.get("hex")
    if raw is None:
        raise ValueError("Hex color is empty")
    text = str(raw).strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", text):
        raise ValueError(f"Invalid hex color: {raw}")
    return hex_to_rgb(text)


def _to_rgb_triplet(values):
    if not isinstance(values, (list, tuple)) or len(values) != 3:
        raise ValueError("RGB value must contain 3 channels")
    r = int(values[0])
    g = int(values[1])
    b = int(values[2])
    for channel in (r, g, b):
        if channel < 0 or channel > 255:
            raise ValueError(f"RGB channel out of range: {channel}")
    return [r, g, b]


def _load_dict_from_string(raw):
    """
    Пытается разобрать строку как dict (JSON / python literal).
    """
    if not isinstance(raw, str):
        raise ValueError("Color dict must be a string")
    text = raw.strip()
    if not text:
        raise ValueError("Color dict string is empty")

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    try:
        data = ast.literal_eval(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    raise ValueError(f"Cannot parse color dict from string: {raw}")


def detect_format(raw):
    if isinstance(raw, dict):
        if "mode" in raw:
            return str(raw["mode"]).lower()
        if "xy" in raw or ("x" in raw and "y" in raw):
            return "xy"
        if "rgb" in raw or {"r", "g", "b"} <= set(raw.keys()):
            return "rgb"
        if "hex" in raw:
            return "hex"
        if "hue" in raw or "saturation" in raw:
            return "hs"
        if "hsv" in raw or ("h" in raw and "s" in raw and "v" in raw):
            return "hsv"
        if "hsb" in raw or ("h" in raw and "s" in raw and "b" in raw):
            return "hsb"
        if "hsl" in raw or ("h" in raw and "s" in raw and "l" in raw):
            return "hsl"
        if "color_temp" in raw or "mired" in raw:
            return "color_temp"
        if "color" in raw and isinstance(raw["color"], dict):
            return "zigbee2mqtt"
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith(("{", "[")):
            return "canonical"
        if s.startswith("#") and len(s) in (4, 7):
            return "hex"
        if re.fullmatch(r"[0-9a-fA-F]{6}", s) or re.fullmatch(r"[0-9a-fA-F]{3}", s):
            return "hex"
        if "," in s:
            parts = [p.strip() for p in s.split(",")]
            if len(parts) == 3:
                return "rgb"
            if len(parts) == 2:
                return "hs"
        if is_color_name(s):
            return "name"
    return "canonical"


def parse(raw, write_format="auto", scales=None):
    scales = scales or {}
    fmt = write_format if write_format and write_format != "auto" else detect_format(raw)
    fmt = fmt.lower()
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported color format: {fmt}")

    if fmt == "zigbee2mqtt":
        if not isinstance(raw, dict) or "color" not in raw or not isinstance(raw["color"], dict):
            raise ValueError("zigbee2mqtt payload must be {'color': {...}}")
        return parse(raw["color"], write_format="auto", scales=scales)

    if fmt == "canonical":
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            return _load_dict_from_string(raw)
        raise ValueError("Canonical color must be dict or JSON string")

    if fmt == "hex":
        r, g, b = normalize_hex_input(raw)
        return {"rgb": [r, g, b]}

    if fmt == "rgb":
        if isinstance(raw, dict):
            if "rgb" in raw:
                raw = raw["rgb"]
            elif {"r", "g", "b"} <= set(raw.keys()):
                raw = [raw["r"], raw["g"], raw["b"]]
        if isinstance(raw, str):
            if is_color_name(raw):
                raw = parse_color_name(raw)
            else:
                raw = parse_rgb_string(raw)
        return {"rgb": _to_rgb_triplet(raw)}

    if fmt == "name":
        if isinstance(raw, dict):
            raw = raw.get("name") or raw.get("color")
        if not isinstance(raw, str):
            raise ValueError("Color name must be a string")
        r, g, b = parse_color_name(raw)
        return {"rgb": [r, g, b]}

    if fmt == "xy":
        luminance = None
        if isinstance(raw, dict):
            luminance = _extract_luminance(raw)
            if "xy" in raw:
                raw = raw["xy"]
            elif "x" in raw and "y" in raw:
                raw = [raw["x"], raw["y"]]
        if not isinstance(raw, (list, tuple)) or len(raw) != 2:
            raise ValueError("XY must have 2 values")
        x = _clamp(float(raw[0]), 0.0, 1.0)
        y = _clamp(float(raw[1]), 0.0, 1.0)
        result = {"xy": [x, y]}
        if luminance is not None:
            result["Y"] = _round_luminance(luminance)
        return result

    hue_scale = scales.get("hue_scale", 360)
    sat_scale = scales.get("sat_scale", 100)

    if fmt == "hs":
        if isinstance(raw, dict):
            if "hs" in raw:
                raw = raw["hs"]
            elif "hue" in raw and "saturation" in raw:
                raw = [raw["hue"], raw["saturation"]]
            elif "h" in raw and "s" in raw:
                raw = [raw["h"], raw["s"]]
        if not isinstance(raw, (list, tuple)) or len(raw) != 2:
            raise ValueError("HS must have 2 values")
        h, s = normalize_hue_sat(raw[0], raw[1], hue_scale=hue_scale, sat_scale=sat_scale)
        r, g, b = hsv_to_rgb(h, s, 100)
        return {"rgb": [r, g, b], "hs": [round(h, 3), round(s, 3)]}

    if fmt in ("hsv", "hsb", "hsl"):
        key = fmt
        if isinstance(raw, dict):
            if key in raw:
                raw = raw[key]
            elif {"h", "s", key[-1]} <= set(raw.keys()):
                raw = [raw["h"], raw["s"], raw[key[-1]]]
        if isinstance(raw, str):
            raw = [v.strip() for v in raw.split(",")]
        if not isinstance(raw, (list, tuple)) or len(raw) != 3:
            raise ValueError(f"{fmt} must have 3 values")
        h, s = normalize_hue_sat(raw[0], raw[1], hue_scale=hue_scale, sat_scale=sat_scale)
        third = _clamp(float(raw[2]), 0.0, 100.0)
        if fmt == "hsv":
            r, g, b = hsv_to_rgb(h, s, third)
        elif fmt == "hsb":
            r, g, b = hsb_to_rgb(h, s, third)
        else:
            r, g, b = hsl_to_rgb(h, s, third)
        return {"rgb": [r, g, b], fmt: [round(h, 3), round(s, 3), round(third, 3)], "hs": [round(h, 3), round(s, 3)]}

    if fmt == "color_temp":
        if isinstance(raw, dict):
            if "color_temp" in raw:
                ct = int(raw["color_temp"])
                r, g, b = kelvin_to_rgb(ct)
                return {"color_temp": ct, "rgb": [r, g, b]}
            if "mired" in raw:
                mired = int(raw["mired"])
                kelvin = mired_to_kelvin(mired)
                r, g, b = kelvin_to_rgb(kelvin)
                return {"mired": mired, "color_temp": kelvin, "rgb": [r, g, b]}
        raise ValueError("color_temp format expects dict with color_temp or mired")

    raise ValueError(f"Unsupported color format: {fmt}")


def to_universal(parsed):
    if isinstance(parsed, str):
        parsed = json.loads(parsed)
    if not isinstance(parsed, dict):
        raise ValueError("Parsed color must be dict")

    result = {}
    if "rgb" in parsed:
        rgb = _to_rgb_triplet(parsed["rgb"])
        result["rgb"] = rgb
        x, y, y_lum = rgb_to_xyY(rgb[0], rgb[1], rgb[2])
        result["xy"] = _round_xy(x, y)
        result["Y"] = _round_luminance(y_lum)
    elif "xy" in parsed:
        xy = parsed["xy"]
        if not isinstance(xy, (list, tuple)) or len(xy) != 2:
            raise ValueError("xy must contain two values")
        x = _clamp(float(xy[0]), 0.0, 1.0)
        y = _clamp(float(xy[1]), 0.0, 1.0)
        result["xy"] = _round_xy(x, y)
        y_lum = _extract_luminance(parsed)
        if y_lum is not None:
            result["Y"] = _round_luminance(y_lum)
            result["rgb"] = _rgb_from_xy(x, y, y_lum)
    elif "x" in parsed and "y" in parsed:
        x = _clamp(float(parsed["x"]), 0.0, 1.0)
        y = _clamp(float(parsed["y"]), 0.0, 1.0)
        result["xy"] = _round_xy(x, y)
        y_lum = _extract_luminance(parsed)
        if y_lum is not None:
            result["Y"] = _round_luminance(y_lum)
            result["rgb"] = _rgb_from_xy(x, y, y_lum)
    else:
        enriched = parse(parsed, write_format="auto")
        if "rgb" in enriched:
            rgb = _to_rgb_triplet(enriched["rgb"])
            result["rgb"] = rgb
            x, y, y_lum = rgb_to_xyY(rgb[0], rgb[1], rgb[2])
            result["xy"] = _round_xy(x, y)
            result["Y"] = _round_luminance(y_lum)
        elif "xy" in enriched:
            xy = enriched["xy"]
            if not isinstance(xy, (list, tuple)) or len(xy) != 2:
                raise ValueError("xy must contain two values")
            x = _clamp(float(xy[0]), 0.0, 1.0)
            y = _clamp(float(xy[1]), 0.0, 1.0)
            result["xy"] = _round_xy(x, y)
            y_lum = _extract_luminance(enriched)
            if y_lum is not None:
                result["Y"] = _round_luminance(y_lum)
                result["rgb"] = _rgb_from_xy(x, y, y_lum)
        else:
            raise ValueError("parsed color must contain rgb or xy")
        parsed = enriched

    for key in ("hs", "hsv", "hsl", "hsb", "color_temp", "mired"):
        if key in parsed:
            result[key] = parsed[key]

    return result


def from_universal(univ, read_format="canonical", scales=None):
    scales = scales or {}
    fmt = (read_format or "canonical").lower()
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported read format: {fmt}")
    univ = _coerce_universal(univ, scales=scales)

    if fmt == "canonical":
        return univ

    rgb = univ.get("rgb")
    xy = univ.get("xy")
    if rgb is None and xy is not None:
        y_lum = _extract_luminance(univ)
        if y_lum is None:
            raise ValueError("Universal color with xy requires luminance (Y)")
        rgb = _rgb_from_xy(xy[0], xy[1], y_lum)
    if rgb is None:
        raise ValueError("Universal color must contain rgb or xy")
    rgb = _to_rgb_triplet(rgb)

    if fmt == "rgb":
        return {"r": rgb[0], "g": rgb[1], "b": rgb[2]}
    if fmt == "hex":
        return f"#{rgb_to_hex(rgb[0], rgb[1], rgb[2])}"
    if fmt == "xy":
        if xy is None:
            x, y = rgb_to_xy(rgb[0], rgb[1], rgb[2])
            xy = [x, y]
        return {"x": round(float(xy[0]), 6), "y": round(float(xy[1]), 6)}
    if fmt == "hs":
        hs = univ.get("hs")
        if hs and isinstance(hs, (list, tuple)) and len(hs) == 2:
            h, s = hs
        else:
            h, s, _ = rgb_to_hsv(rgb[0], rgb[1], rgb[2])
        h_raw, s_raw = denormalize_hue_sat(h, s, scales.get("hue_scale", 360), scales.get("sat_scale", 100))
        return {"hue": h_raw, "saturation": s_raw}
    if fmt == "hsv":
        hsv = univ.get("hsv")
        if not hsv:
            hsv = list(rgb_to_hsv(rgb[0], rgb[1], rgb[2]))
        return {"hsv": ",".join(str(v) for v in hsv)}
    if fmt == "hsl":
        hsl = univ.get("hsl")
        if not hsl:
            hsl = list(rgb_to_hsl(rgb[0], rgb[1], rgb[2]))
        return {"hsl": ",".join(str(v) for v in hsl)}
    if fmt == "hsb":
        hsb = univ.get("hsb")
        if not hsb:
            hsb = list(rgb_to_hsb(rgb[0], rgb[1], rgb[2]))
        return {"hsb": ",".join(str(v) for v in hsb)}
    if fmt == "color_temp":
        unit = (scales.get("color_temp_unit") or "kelvin").lower()
        if unit == "mired":
            if "mired" in univ:
                return int(univ["mired"])
            if "color_temp" in univ:
                return kelvin_to_mired(univ["color_temp"])
        if "color_temp" in univ:
            return int(univ["color_temp"])
        if "mired" in univ:
            return mired_to_kelvin(univ["mired"])
        return None
    if fmt == "zigbee2mqtt":
        return build_zigbee2mqtt_color(univ)
    raise ValueError(f"Unsupported read format: {fmt}")


def encode(univ):
    if not isinstance(univ, dict):
        raise ValueError("Universal color must be dict")
    normalized = to_universal(univ)
    if "xy" in normalized:
        normalized["xy"] = _round_xy(normalized["xy"][0], normalized["xy"][1])
    return color_json_dumps(normalized)


def decode(value):
    if value is None:
        return None
    return _coerce_universal(value)
