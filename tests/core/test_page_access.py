"""Tests for check_page_access (deny-by-default model)."""
import unittest
from unittest.mock import Mock, patch, MagicMock

from flask import Flask
from flask_login import UserMixin

from app import check_page_access, _PUBLIC_ENDPOINTS, _resolve_required_roles, _resolve_public_access
from app.authentication.handlers import handle_admin_required, handle_user_required, public_endpoint


class DummyUser(UserMixin):
    def __init__(self, username, role):
        self.username = username
        self.role = role
        self.id = username


class TestCheckPageAccess(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'test'

    def _run_check(self, endpoint, method='GET', user=None, permissions=None, view_func=None):
        with self.app.test_request_context('/', method=method):
            request_mock = Mock()
            request_mock.endpoint = endpoint
            request_mock.method = method
            request_mock.args = {}
            request_mock.headers = {}
            request_mock.url = 'http://localhost/'
            request_mock.full_path = '/'
            request_mock.path = '/'
            if view_func is not None:
                self.app.view_functions[endpoint] = view_func
            with patch('app.current_app', self.app):
                with patch('app.getProperty', return_value=permissions):
                    with patch('app.security_audit_log'):
                        with patch('app.current_user', user or Mock(is_authenticated=False)):
                            return check_page_access(request_mock)

    def test_public_whitelist_contains_expected(self):
        self.assertIn('static', _PUBLIC_ENDPOINTS)

    def test_public_endpoint_decorator_without_auth(self):
        @public_endpoint
        def public_view():
            return 'ok'

        result = self._run_check('test.public_view', user=None, view_func=public_view)
        self.assertTrue(result)

    def test_public_endpoint_without_auth(self):
        @public_endpoint
        def public_file():
            return 'ok'

        result = self._run_check('files.public_file', user=None, view_func=public_file)
        self.assertTrue(result)

    def test_undecorated_route_denied_without_auth(self):
        result = self._run_check('admin.set_lang', user=None, view_func=lambda: 'ok')
        self.assertIsNone(result)

    def test_undecorated_route_allowed_when_authenticated(self):
        user = DummyUser('alice', 'user')
        result = self._run_check('admin.set_lang', user=user, view_func=lambda: 'ok')
        self.assertTrue(result)

    def test_admin_route_denied_for_user(self):
        @handle_admin_required
        def admin_view():
            return 'ok'

        user = DummyUser('bob', 'user')
        result = self._run_check('admin.control_panel', user=user, view_func=admin_view)
        self.assertFalse(result)

    def test_admin_route_allowed_for_admin(self):
        @handle_admin_required
        def admin_view():
            return 'ok'

        user = DummyUser('admin', 'admin')
        result = self._run_check('admin.control_panel', user=user, view_func=admin_view)
        self.assertTrue(result)

    def test_permissions_override_grants_user_on_admin_route(self):
        @handle_admin_required
        def sql_view():
            return 'ok'

        user = DummyUser('bob', 'user')
        permissions = {"get": {"access_roles": ["user"]}}
        result = self._run_check(
            'api.select_query',
            user=user,
            permissions=permissions,
            view_func=sql_view,
        )
        self.assertTrue(result)

    def test_resolve_public_access_restx_resource(self):
        class ResourceView:
            @public_endpoint
            def get(self):
                return 'ok'

        view_func = MagicMock()
        view_func.public_access = False
        view_func.view_class = ResourceView
        self.assertTrue(_resolve_public_access(view_func, 'GET'))
        self.assertFalse(_resolve_public_access(view_func, 'POST'))

    def test_resolve_required_roles_plain_view(self):
        @handle_user_required
        def view():
            return 'ok'

        self.assertEqual(_resolve_required_roles(view, 'GET'), ['user', 'editor', 'admin'])

    def test_resolve_required_roles_restx_resource(self):
        class ResourceView:
            @handle_admin_required
            def get(self):
                return 'ok'

        view_func = MagicMock()
        view_func.view_class = ResourceView
        self.assertEqual(_resolve_required_roles(view_func, 'GET'), ['admin'])

    def test_public_endpoint_overrides_required_roles(self):
        @public_endpoint
        @handle_admin_required
        def mixed_view():
            return 'ok'

        self.assertTrue(_resolve_public_access(mixed_view, 'GET'))
        self.assertEqual(_resolve_required_roles(mixed_view, 'GET'), ['admin'])
        result = self._run_check('admin.mixed_view', user=None, view_func=mixed_view)
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
