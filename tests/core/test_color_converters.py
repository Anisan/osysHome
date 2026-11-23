import unittest

from app.core.lib.converters.color import (
    rgb_to_xy,
    xy_to_rgb,
    parse_rgb_string,
    normalize_hue_sat,
    denormalize_hue_sat,
    kelvin_to_mired,
    mired_to_kelvin,
    build_zigbee2mqtt_color,
)


class TestColorConverters(unittest.TestCase):
    def test_rgb_xy_roundtrip(self):
        r, g, b = 84, 102, 150
        x, y = rgb_to_xy(r, g, b)
        rr, gg, bb = xy_to_rgb(x, y)
        self.assertTrue(0 <= rr <= 255)
        self.assertTrue(0 <= gg <= 255)
        self.assertTrue(0 <= bb <= 255)
        self.assertTrue(0 <= x <= 1)
        self.assertTrue(0 <= y <= 1)

    def test_parse_rgb_string(self):
        self.assertEqual(parse_rgb_string("46,102,150"), (46, 102, 150))
        with self.assertRaises(ValueError):
            parse_rgb_string("1,2")

    def test_hue_sat_scales(self):
        h, s = normalize_hue_sat(127, 127, hue_scale=254, sat_scale=254)
        raw_h, raw_s = denormalize_hue_sat(h, s, hue_scale=254, sat_scale=254)
        self.assertTrue(abs(raw_h - 127) <= 1)
        self.assertTrue(abs(raw_s - 127) <= 1)

    def test_color_temp_units(self):
        self.assertEqual(mired_to_kelvin(153), 6536)
        self.assertEqual(kelvin_to_mired(6500), 154)

    def test_build_zigbee2mqtt_payload(self):
        payload = build_zigbee2mqtt_color({"rgb": [46, 102, 150], "xy": [0.123456, 0.234567]})
        self.assertIn("color", payload)
        self.assertIn("x", payload["color"])


if __name__ == "__main__":
    unittest.main()
