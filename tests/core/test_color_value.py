import datetime
import json
import unittest
from unittest.mock import Mock, patch

from app.core.lib.converters.color import normalize_hue_sat, denormalize_hue_sat
from app.core.lib.converters.color_value import (
    detect_format,
    parse,
    to_universal,
    from_universal,
    encode,
    decode,
    merge_xy_luminance,
    normalize_hex_input,
)

DEFAULT_COLOR_SCALES = {
    "hue_scale": 360,
    "sat_scale": 100,
    "color_temp_unit": "kelvin",
}


class TestColorValue(unittest.TestCase):
    def test_detect_format(self):
        self.assertEqual(detect_format("#547CFF"), "hex")
        self.assertEqual(detect_format({"x": 0.1, "y": 0.2}), "xy")
        self.assertEqual(detect_format({"color": {"x": 0.1, "y": 0.2}}), "zigbee2mqtt")

    def test_parse_zigbee_xy(self):
        parsed = parse({"color": {"x": 0.123, "y": 0.456}}, write_format="auto")
        self.assertIn("xy", parsed)
        self.assertEqual(len(parsed["xy"]), 2)

    def test_parse_rgb_and_universal(self):
        parsed = parse({"r": 46, "g": 102, "b": 150}, write_format="auto")
        univ = to_universal(parsed)
        self.assertIn("rgb", univ)
        self.assertIn("xy", univ)

    def test_encode_decode(self):
        univ = {"rgb": [84, 102, 150], "xy": [0.458312, 0.410201]}
        encoded = encode(univ)
        decoded = decode(encoded)
        self.assertEqual(decoded["rgb"], [84, 102, 150])
        self.assertIn("xy", decoded)

    def test_from_universal_formats(self):
        univ = {"rgb": [84, 102, 150], "xy": [0.458312, 0.410201], "hs": [210, 44]}
        as_hex = from_universal(univ, "hex")
        as_xy = from_universal(univ, "xy")
        as_hs = from_universal(univ, "hs")
        self.assertTrue(as_hex.startswith("#"))
        self.assertIn("x", as_xy)
        self.assertIn("hue", as_hs)

    def test_strict_format(self):
        with self.assertRaises(ValueError):
            parse({"x": 0.1, "y": 0.2}, write_format="hex")

    def test_from_universal_legacy_hex_string(self):
        as_hex = from_universal("#547CFF", "hex")
        self.assertEqual(as_hex.upper(), "#547CFF")

    def test_from_universal_hex_without_hash(self):
        as_hex = from_universal("547CFF", "hex")
        self.assertEqual(as_hex.upper(), "#547CFF")

    def test_parse_hex_with_and_without_hash(self):
        with_hash = parse("#547CFF", write_format="hex")
        without_hash = parse("547CFF", write_format="hex")
        self.assertEqual(with_hash["rgb"], [84, 124, 255])
        self.assertEqual(without_hash["rgb"], [84, 124, 255])
        self.assertEqual(normalize_hex_input("#547CFF"), (84, 124, 255))
        self.assertEqual(normalize_hex_input("547CFF"), (84, 124, 255))

    def test_parse_canonical_python_literal(self):
        parsed = parse("{'rgb': [1, 2, 3]}", write_format="canonical")
        self.assertEqual(parsed["rgb"], [1, 2, 3])

    def test_from_universal_legacy_rgb_csv(self):
        as_rgb = from_universal("46,102,150", "rgb")
        self.assertEqual(as_rgb, {"r": 46, "g": 102, "b": 150})

    def test_to_universal_hsv_only_dict(self):
        univ = to_universal({"hsv": "0,90,78"})
        self.assertIn("rgb", univ)
        self.assertIn("xy", univ)
        self.assertIn("hsv", univ)

    def test_from_universal_hsv_read_format(self):
        univ = to_universal({"hsv": "0,90,78"})
        as_hsv = from_universal(univ, "hsv")
        self.assertIn("hsv", as_hsv)
        preview_hex = from_universal(univ, "hex")
        self.assertTrue(str(preview_hex).startswith("#"))

    def test_to_universal_xy_object_keys(self):
        univ = to_universal({"x": 0.21802, "y": 0.17052})
        self.assertIn("xy", univ)
        self.assertNotIn("rgb", univ)

    def test_decode_xy_json_string(self):
        decoded = decode('{"x":0.21802,"y":0.17052}')
        self.assertIn("xy", decoded)
        self.assertNotIn("rgb", decoded)

    def test_decode_python_literal_dict_string(self):
        value = decode("{'rgb': [84, 102, 150], 'xy': [0.458312, 0.410201]}")
        self.assertIn("rgb", value)
        self.assertIn("xy", value)

    def test_hex_xy_roundtrip_preserves_brightness(self):
        hex_in = "#FF5733"
        univ = to_universal(parse(hex_in, write_format="hex"))
        self.assertIn("Y", univ)
        xy_only = to_universal({"xy": univ["xy"], "Y": univ["Y"]})
        hex_out = from_universal(xy_only, "hex")
        self.assertEqual(hex_out.upper(), hex_in.upper())

    def test_merge_xy_luminance_on_xy_only_update(self):
        original = to_universal(parse("#FF0000", write_format="hex"))
        merged = merge_xy_luminance({"x": original["xy"][0], "y": original["xy"][1]}, original)
        updated = to_universal(merged)
        self.assertEqual(updated["rgb"], [255, 0, 0])

    def test_detect_format_color_name(self):
        self.assertEqual(detect_format("red"), "name")
        self.assertEqual(detect_format("Green"), "name")
        self.assertEqual(detect_format(" BLUE "), "name")

    def test_parse_color_name(self):
        parsed = parse("red", write_format="auto")
        self.assertEqual(parsed["rgb"], [255, 0, 0])
        parsed = parse("green", write_format="name")
        self.assertEqual(parsed["rgb"], [0, 128, 0])
        parsed = parse("white", write_format="auto")
        self.assertEqual(parsed["rgb"], [255, 255, 255])
        parsed = parse("orange", write_format="auto")
        self.assertEqual(parsed["rgb"], [255, 165, 0])
        parsed = parse("warmwhite", write_format="auto")
        self.assertEqual(parsed["rgb"], [255, 244, 229])
        parsed = parse("softwhite", write_format="auto")
        self.assertEqual(parsed["rgb"], [255, 167, 87])
        parsed = parse("relax", write_format="auto")
        self.assertEqual(parsed["rgb"], [255, 146, 39])
        parsed = parse("sunset", write_format="auto")
        self.assertEqual(parsed["rgb"], [255, 120, 60])

    def test_from_universal_color_name_string(self):
        univ = to_universal(parse("blue", write_format="auto"))
        self.assertEqual(univ["rgb"], [0, 0, 255])
        as_hex = from_universal("red", "hex")
        self.assertEqual(as_hex.upper(), "#FF0000")

    def test_unknown_color_name_raises(self):
        with self.assertRaises(ValueError):
            parse("notacolor", write_format="auto")

    def test_default_hue_sat_scales_identity(self):
        """hue_scale=360, sat_scale=100 — значения не меняются при нормализации."""
        h, s = normalize_hue_sat(226, 67, **{k: v for k, v in DEFAULT_COLOR_SCALES.items() if k != "color_temp_unit"})
        self.assertAlmostEqual(h, 226, places=3)
        self.assertAlmostEqual(s, 67, places=3)
        raw_h, raw_s = denormalize_hue_sat(h, s, hue_scale=360, sat_scale=100)
        self.assertEqual(raw_h, 226)
        self.assertEqual(raw_s, 67)

    def test_hs_roundtrip_default_scales(self):
        """Запись и чтение HS при стандартных шкалах 360/100."""
        parsed = parse(
            {"hue": 120, "saturation": 80},
            write_format="hs",
            scales=DEFAULT_COLOR_SCALES,
        )
        univ = to_universal(parsed)
        as_hs = from_universal(univ, "hs", scales=DEFAULT_COLOR_SCALES)
        self.assertEqual(as_hs["hue"], 120)
        self.assertEqual(as_hs["saturation"], 80)

    def test_hsv_roundtrip_default_scales(self):
        """HSV при hue_scale=360, sat_scale=100."""
        parsed = parse(
            {"hsv": "146,90,78"},
            write_format="hsv",
            scales=DEFAULT_COLOR_SCALES,
        )
        univ = to_universal(parsed)
        as_hsv = from_universal(univ, "hsv", scales=DEFAULT_COLOR_SCALES)
        self.assertEqual(as_hsv["hsv"], "146.0,90.0,78.0")

    def test_color_temp_kelvin_unit(self):
        """color_temp_unit=kelvin — read_format color_temp отдаёт Кельвины."""
        parsed = parse({"color_temp": 4000}, write_format="color_temp")
        univ = to_universal(parsed)
        as_kelvin = from_universal(univ, "color_temp", scales=DEFAULT_COLOR_SCALES)
        self.assertEqual(as_kelvin, 4000)

    def test_color_temp_mired_unit(self):
        """color_temp_unit=mired — read_format color_temp отдаёт mired."""
        parsed = parse({"color_temp": 4000}, write_format="color_temp")
        univ = to_universal(parsed)
        scales = {**DEFAULT_COLOR_SCALES, "color_temp_unit": "mired"}
        as_mired = from_universal(univ, "color_temp", scales=scales)
        self.assertEqual(as_mired, 250)


class TestColorPropertyManagerDefaultScales(unittest.TestCase):
    """PropertyManager с color_temp_unit=kelvin, hue_scale=360, sat_scale=100."""

    def setUp(self):
        self.mock_property = Mock()
        self.mock_property.id = 1
        self.mock_property.name = "color_prop"
        self.mock_property.description = ""
        self.mock_property.history = 0
        self.mock_property.type = "color"
        self.mock_property.params = json.dumps({
            "read_format": "hs",
            "write_format": "auto",
            "color_temp_unit": "kelvin",
            "hue_scale": 360,
            "sat_scale": 100,
        })

    @patch("app.core.main.ObjectManager.get_now_to_utc")
    def test_hs_read_write_default_scales(self, mock_now):
        from app.core.main.ObjectManager import PropertyManager

        mock_now.return_value = datetime.datetime.now()
        prop_manager = PropertyManager(1, self.mock_property, None)
        prop_manager.setValue({"hue": 226, "saturation": 67})
        value = prop_manager.getValue()
        self.assertEqual(value["hue"], 226)
        self.assertEqual(value["saturation"], 67)

    @patch("app.core.main.ObjectManager.get_now_to_utc")
    def test_color_temp_kelvin_read_write(self, mock_now):
        from app.core.main.ObjectManager import PropertyManager

        mock_now.return_value = datetime.datetime.now()
        self.mock_property.params = json.dumps({
            "read_format": "color_temp",
            "write_format": "auto",
            "color_temp_unit": "kelvin",
            "hue_scale": 360,
            "sat_scale": 100,
        })
        prop_manager = PropertyManager(1, self.mock_property, None)
        prop_manager.setValue({"color_temp": 2700})
        value = prop_manager.getValue()
        self.assertEqual(value, 2700)


if __name__ == "__main__":
    unittest.main()
