"""Tests for configuration defaults when sections are missing."""

import os
import tempfile
import unittest

import yaml

from app.configuration import ConfigLoader


class TestConfigurationDefaults(unittest.TestCase):
    def _write_yaml(self, directory, filename, data):
        path = os.path.join(directory, filename)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        return path

    def test_missing_sections_use_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample_secret = "your-secret-key-here"
            self._write_yaml(
                tmp,
                "sample_config.yaml",
                {"application": {"secret_key": sample_secret}},
            )
            config_path = self._write_yaml(
                tmp,
                "config.yaml",
                {
                    "application": {
                        "secret_key": "custom-secret-not-sample",
                        "debug": False,
                    }
                },
            )

            loader = ConfigLoader()
            loader.APP_DIR = tmp
            loader.load_from_file(config_path)

            self.assertEqual(loader.DEFAULT_LANGUAGE, "en")
            self.assertEqual(loader.DEFAULT_TIMEZONE, "Europe/Moscow")
            self.assertEqual(loader.APP_PORT, 5000)
            self.assertEqual(loader.CACHE_TYPE, "simple")
            self.assertEqual(loader.CACHE_DEFAULT_TIMEOUT, 300)
            self.assertFalse(loader.DEBUG_TOOLS_ENABLED)
            self.assertTrue(loader.RATELIMIT_ENABLED)


if __name__ == "__main__":
    unittest.main()
