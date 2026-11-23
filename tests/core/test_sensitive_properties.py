"""Tests for sensitive Users property access control."""
import unittest
from unittest.mock import Mock, patch

from app.core.main.ObjectManager import ObjectManager, TypeOperation


class TestSensitiveUserProperties(unittest.TestCase):
    def _make_users_manager(self, obj_name='alice', role='user', username='bob'):
        mock_object = Mock()
        mock_object.id = 1
        mock_object.name = obj_name
        mock_object.description = 'User'

        om = ObjectManager(mock_object)
        om.parents = ['Users']
        om.set_permission({'properties': {}})

        user = Mock()
        user.username = username
        user.role = role
        return om, user

    @patch('app.core.main.ObjectManager.current_user')
    def test_password_get_denied_for_authenticated_user(self, mock_current_user):
        om, user = self._make_users_manager()
        mock_current_user.username = user.username
        mock_current_user.role = user.role

        with self.assertRaises(PermissionError):
            om._check_permissions(TypeOperation.Get, 'password', None)

    @patch('app.core.main.ObjectManager.current_user')
    def test_password_get_denied_for_admin(self, mock_current_user):
        om, user = self._make_users_manager(role='admin', username='admin')
        mock_current_user.username = user.username
        mock_current_user.role = user.role

        with self.assertRaises(PermissionError):
            om._check_permissions(TypeOperation.Get, 'password', None)

    @patch('app.core.main.ObjectManager.current_user')
    def test_password_set_allowed_for_admin(self, mock_current_user):
        om, user = self._make_users_manager(role='admin', username='admin')
        mock_current_user.username = user.username
        mock_current_user.role = user.role

        self.assertTrue(om._check_permissions(TypeOperation.Set, 'password', None))

    @patch('app.core.main.ObjectManager.current_user')
    def test_password_set_denied_for_non_admin(self, mock_current_user):
        om, user = self._make_users_manager(role='user', username='alice')
        mock_current_user.username = user.username
        mock_current_user.role = user.role

        with self.assertRaises(PermissionError):
            om._check_permissions(TypeOperation.Set, 'password', None)

    @patch('app.core.main.ObjectManager.current_user')
    def test_apikey_get_allowed_for_own_user(self, mock_current_user):
        om, user = self._make_users_manager(obj_name='alice', role='user', username='alice')
        mock_current_user.username = user.username
        mock_current_user.role = user.role

        self.assertTrue(om._check_permissions(TypeOperation.Get, 'apikey', None))

    @patch('app.core.main.ObjectManager.current_user')
    def test_apikey_get_denied_for_other_user(self, mock_current_user):
        om, user = self._make_users_manager(obj_name='alice', role='user', username='bob')
        mock_current_user.username = user.username
        mock_current_user.role = user.role

        with self.assertRaises(PermissionError):
            om._check_permissions(TypeOperation.Get, 'apikey', None)

    @patch('app.core.main.ObjectManager.current_user')
    def test_apikey_get_allowed_for_admin_on_other_user(self, mock_current_user):
        om, user = self._make_users_manager(obj_name='alice', role='admin', username='admin')
        mock_current_user.username = user.username
        mock_current_user.role = user.role

        self.assertTrue(om._check_permissions(TypeOperation.Get, 'apikey', None))

    @patch('app.core.main.ObjectManager.current_user')
    def test_admin_role_set_bypasses_restrictive_acl(self, mock_current_user):
        om, user = self._make_users_manager(obj_name='alice', role='admin', username='admin')
        om.set_permission({
            'properties': {
                'role': {
                    'set': {
                        'access_users': ['eraser'],
                        'denied_roles': ['editor', 'user'],
                    }
                }
            }
        })
        mock_current_user.username = user.username
        mock_current_user.role = user.role

        self.assertTrue(om._check_permissions(TypeOperation.Set, 'role', None))

    @patch('app.core.main.ObjectManager.current_user')
    def test_first_admin_password_set_allowed(self, mock_current_user):
        """Bootstrap flow: login_user runs before setProperty with role=admin."""
        om, user = self._make_users_manager(obj_name='admin', role='admin', username='admin')
        mock_current_user.username = user.username
        mock_current_user.role = user.role

        self.assertTrue(om._check_permissions(TypeOperation.Set, 'password', None))
        self.assertTrue(om._check_permissions(TypeOperation.Set, 'role', None))

    @patch('app.core.main.ObjectManager.current_user')
    def test_system_calls_without_user_still_allowed(self, mock_current_user):
        om, _ = self._make_users_manager()
        mock_current_user.username = None

        self.assertTrue(om._check_permissions(TypeOperation.Set, 'password', None))


if __name__ == '__main__':
    unittest.main()
