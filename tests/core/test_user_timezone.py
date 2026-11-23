"""Tests for UI timezone resolution (user / browser / default)."""

import unittest
from datetime import datetime
from unittest.mock import Mock, patch

from flask import Flask

from app.core.models.Users import User
from app.database import (
    _is_valid_iana_timezone,
    convert_local_to_utc,
    convert_utc_to_local,
    get_user_timezone,
    resolve_timezone,
)


class _Prop:
    def __init__(self, value):
        self._PropertyManager__value = value


class _ObjectUser:
    def __init__(self, name, timezone=None, include_timezone=True):
        self.name = name
        props = {}
        if include_timezone:
            props["timezone"] = _Prop(timezone)
        self.__dict__["properties"] = props


class TestIsValidIanaTimezone(unittest.TestCase):
    def test_valid_and_invalid(self):
        self.assertTrue(_is_valid_iana_timezone("Europe/Moscow"))
        self.assertTrue(_is_valid_iana_timezone("UTC"))
        self.assertFalse(_is_valid_iana_timezone(""))
        self.assertFalse(_is_valid_iana_timezone(None))
        self.assertFalse(_is_valid_iana_timezone("Not/ARealZone"))
        self.assertFalse(_is_valid_iana_timezone("auto"))


class TestGetUserTimezone(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["SECRET_KEY"] = "test"

    def _patch_user(self, timezone):
        user = Mock()
        user.timezone = timezone
        return patch("app.database.current_user", user)

    @patch("app.database.get_default_timezone", return_value="Europe/Moscow")
    def test_explicit_user_wins_over_browser(self, _default):
        with self._patch_user("America/New_York"):
            with self.app.test_request_context(
                "/",
                headers={"X-Timezone": "Asia/Tokyo"},
            ):
                self.assertEqual(get_user_timezone(), "America/New_York")

    @patch("app.database.get_default_timezone", return_value="Europe/Moscow")
    def test_auto_uses_header(self, _default):
        with self._patch_user("auto"):
            with self.app.test_request_context(
                "/",
                headers={"X-Timezone": "Asia/Tokyo"},
            ):
                self.assertEqual(get_user_timezone(), "Asia/Tokyo")

    @patch("app.database.get_default_timezone", return_value="Europe/Moscow")
    def test_auto_uses_cookie(self, _default):
        with self._patch_user("auto"):
            with self.app.test_request_context(
                "/",
                headers={"Cookie": "osys_tz=Europe%2FBerlin"},
            ):
                self.assertEqual(get_user_timezone(), "Europe/Berlin")

    @patch("app.database.get_default_timezone", return_value="Europe/Moscow")
    def test_header_preferred_over_cookie(self, _default):
        with self._patch_user("auto"):
            with self.app.test_request_context(
                "/",
                headers={
                    "X-Timezone": "Asia/Tokyo",
                    "Cookie": "osys_tz=Europe/Berlin",
                },
            ):
                self.assertEqual(get_user_timezone(), "Asia/Tokyo")

    @patch("app.database.get_default_timezone", return_value="Europe/Moscow")
    def test_auto_without_browser_falls_to_default(self, _default):
        with self._patch_user("auto"):
            with self.app.test_request_context("/"):
                self.assertEqual(get_user_timezone(), "Europe/Moscow")

    @patch("app.database.get_default_timezone", return_value="Europe/Moscow")
    def test_invalid_browser_zone_ignored(self, _default):
        with self._patch_user("auto"):
            with self.app.test_request_context(
                "/",
                headers={"X-Timezone": "Not/ARealZone", "Cookie": "osys_tz=Also/Bad"},
            ):
                self.assertEqual(get_user_timezone(), "Europe/Moscow")

    @patch("app.database.get_default_timezone", return_value="Europe/Moscow")
    def test_no_request_context_uses_default_for_auto(self, _default):
        with self._patch_user("auto"):
            self.assertEqual(get_user_timezone(), "Europe/Moscow")

    @patch("app.database.get_default_timezone", return_value="Europe/Moscow")
    def test_auto_case_insensitive(self, _default):
        with self._patch_user("AUTO"):
            with self.app.test_request_context(
                "/",
                headers={"X-Timezone": "Pacific/Auckland"},
            ):
                self.assertEqual(get_user_timezone(), "Pacific/Auckland")

    @patch("app.database.get_default_timezone", return_value="Europe/Moscow")
    def test_empty_user_timezone_uses_browser(self, _default):
        with self._patch_user(""):
            with self.app.test_request_context(
                "/",
                headers={"Cookie": "osys_tz=UTC"},
            ):
                self.assertEqual(get_user_timezone(), "UTC")


class TestResolveTimezone(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    @patch("app.database.get_default_timezone", return_value="Europe/Moscow")
    @patch("app.database.current_user")
    def test_keeps_valid_iana(self, mock_user, _default):
        mock_user.timezone = "auto"
        self.assertEqual(resolve_timezone("America/New_York"), "America/New_York")

    @patch("app.database.get_default_timezone", return_value="Europe/Moscow")
    @patch("app.database.current_user")
    def test_auto_and_invalid_fall_through(self, mock_user, _default):
        mock_user.timezone = "auto"
        with self.app.test_request_context(
            "/",
            headers={"X-Timezone": "Asia/Tokyo"},
        ):
            self.assertEqual(resolve_timezone("auto"), "Asia/Tokyo")
            self.assertEqual(resolve_timezone("AUTO"), "Asia/Tokyo")
            self.assertEqual(resolve_timezone("Not/ARealZone"), "Asia/Tokyo")
            self.assertEqual(resolve_timezone(None), "Asia/Tokyo")

    @patch("app.database.get_default_timezone", return_value="Europe/Moscow")
    @patch("app.database.current_user")
    def test_auto_without_browser_uses_default(self, mock_user, _default):
        mock_user.timezone = "auto"
        self.assertEqual(resolve_timezone("auto"), "Europe/Moscow")


class TestConvertWithUserTimezone(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    @patch("app.database.get_default_timezone", return_value="UTC")
    @patch("app.database.current_user")
    def test_convert_uses_resolved_timezone(self, mock_user, _default):
        mock_user.timezone = "auto"
        utc_noon = datetime(2024, 1, 15, 12, 0, 0)
        with self.app.test_request_context(
            "/",
            headers={"X-Timezone": "Europe/Moscow"},
        ):
            local = convert_utc_to_local(utc_noon)
            self.assertEqual(local, datetime(2024, 1, 15, 15, 0, 0))
            back = convert_local_to_utc(local)
            self.assertEqual(back, utc_noon)

    @patch("app.database.get_user_timezone")
    def test_explicit_timezone_arg_bypasses_resolver(self, mock_get_tz):
        utc_noon = datetime(2024, 1, 15, 12, 0, 0)
        local = convert_utc_to_local(utc_noon, timezone="Europe/Moscow")
        self.assertEqual(local, datetime(2024, 1, 15, 15, 0, 0))
        mock_get_tz.assert_not_called()

    @patch("app.database.get_default_timezone", return_value="Europe/Moscow")
    @patch("app.database.current_user")
    def test_convert_with_auto_arg_does_not_raise(self, mock_user, _default):
        mock_user.timezone = "auto"
        utc_noon = datetime(2024, 1, 15, 12, 0, 0)
        local = convert_utc_to_local(utc_noon, timezone="auto")
        self.assertEqual(local, datetime(2024, 1, 15, 15, 0, 0))
        back = convert_local_to_utc(local, timezone="auto")
        self.assertEqual(back, utc_noon)


class TestUserModelTimezone(unittest.TestCase):
    def test_default_auto_when_property_missing(self):
        user = User(_ObjectUser("admin", include_timezone=False))
        self.assertEqual(user.timezone, "auto")

    def test_auto_and_empty(self):
        self.assertEqual(User(_ObjectUser("a", "auto")).timezone, "auto")
        self.assertEqual(User(_ObjectUser("a", "AUTO")).timezone, "auto")
        self.assertEqual(User(_ObjectUser("a", "")).timezone, "auto")
        self.assertEqual(User(_ObjectUser("a", None)).timezone, "auto")

    def test_valid_iana(self):
        self.assertEqual(
            User(_ObjectUser("a", "Europe/Moscow")).timezone,
            "Europe/Moscow",
        )

    def test_invalid_iana_becomes_auto(self):
        self.assertEqual(User(_ObjectUser("a", "Not/ARealZone")).timezone, "auto")


if __name__ == "__main__":
    unittest.main()
