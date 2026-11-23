"""Tests for auto security defaults when secret_key is still the sample value."""
import os
import tempfile
import unittest

import yaml

from app.configuration import (
    ConfigLoader,
    _SAMPLE_SECRET_KEY_FALLBACK,
    patch_config_yaml_preserving_comments,
)


class TestConfigurationSecurity(unittest.TestCase):
    def _write_yaml(self, directory, filename, data):
        path = os.path.join(directory, filename)
        with open(path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        return path

    def test_sample_secret_triggers_security_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample_secret = 'your-secret-key-here'
            self._write_yaml(tmp, 'sample_config.yaml', {
                'application': {'secret_key': sample_secret, 'debug': True},
            })
            config_path = self._write_yaml(tmp, 'config.yaml', {
                'application': {
                    'secret_key': sample_secret,
                    'debug': True,
                    'env': 'dev',
                },
            })

            loader = ConfigLoader()
            loader.APP_DIR = tmp
            loader.load_from_file(config_path)

            self.assertTrue(loader.SECURITY_DEFAULTS_APPLIED)
            self.assertNotEqual(loader.SECRET_KEY, sample_secret)
            self.assertEqual(len(loader.SECRET_KEY), 64)
            self.assertFalse(loader.DEBUG)
            self.assertEqual(loader.ENV, 'production')
            self.assertTrue(loader.RATELIMIT_ENABLED)
            self.assertFalse(loader.DEBUG_TOOLS_ENABLED)

            with open(config_path, 'r', encoding='utf-8') as f:
                saved = yaml.safe_load(f)
            self.assertEqual(saved['application']['secret_key'], loader.SECRET_KEY)
            self.assertFalse(saved['application']['debug'])

    def test_sample_secret_preserves_yaml_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample_secret = 'your-secret-key-here'
            self._write_yaml(tmp, 'sample_config.yaml', {
                'application': {'secret_key': sample_secret},
            })
            config_path = os.path.join(tmp, 'config.yaml')
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(
                    "# My deployment notes\n"
                    "# Remember: enable HTTPS on reverse proxy\n"
                    "application:\n"
                    f"  secret_key: '{sample_secret}'\n"
                    "  debug: true\n"
                    "  env: dev\n"
                )

            loader = ConfigLoader()
            loader.APP_DIR = tmp
            loader.load_from_file(config_path)

            with open(config_path, 'r', encoding='utf-8') as f:
                saved_text = f.read()

            self.assertIn('# My deployment notes', saved_text)
            self.assertIn('# Remember: enable HTTPS on reverse proxy', saved_text)
            self.assertNotIn(sample_secret, saved_text)

    def test_custom_secret_leaves_config_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            custom_secret = 'my-unique-production-secret'
            self._write_yaml(tmp, 'sample_config.yaml', {
                'application': {'secret_key': _SAMPLE_SECRET_KEY_FALLBACK},
            })
            config_path = self._write_yaml(tmp, 'config.yaml', {
                'application': {
                    'secret_key': custom_secret,
                    'debug': True,
                    'env': 'development',
                },
            })
            mtime_before = os.path.getmtime(config_path)

            loader = ConfigLoader()
            loader.APP_DIR = tmp
            loader.load_from_file(config_path)

            self.assertFalse(loader.SECURITY_DEFAULTS_APPLIED)
            self.assertEqual(loader.SECRET_KEY, custom_secret)
            self.assertTrue(loader.DEBUG)
            self.assertEqual(loader.ENV, 'development')
            self.assertGreaterEqual(os.path.getmtime(config_path), mtime_before)

    def test_patch_preserves_comments_and_updates_keys(self):
        original = (
            "# Keep this note\n"
            "application:\n"
            "  secret_key: 'your-secret-key-here'  # CHANGE ME\n"
            "  debug: true\n"
            "  env: dev\n"
            "  rate_limit:\n"
            "    enabled: false\n"
            "debug_tools:\n"
            "  enabled: true\n"
        )
        patched = patch_config_yaml_preserving_comments(original, 'a' * 64)
        self.assertIn('# Keep this note', patched)
        self.assertIn('debug: false', patched)
        self.assertIn("env: 'production'", patched)
        self.assertIn('enabled: true', patched.split('rate_limit')[1])
        self.assertIn('enabled: false', patched.split('debug_tools')[1])
        self.assertIn('a' * 64, patched)
        self.assertNotIn('your-secret-key-here', patched)

    def test_read_sample_secret_fallback_without_sample_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            loader = ConfigLoader()
            self.assertEqual(
                loader._read_sample_secret_key(tmp),
                _SAMPLE_SECRET_KEY_FALLBACK,
            )


if __name__ == '__main__':
    unittest.main()
