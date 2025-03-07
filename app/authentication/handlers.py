from functools import wraps
from flask import redirect, url_for, flash, request
from flask_login import current_user
from app.logging_config import getLogger
_logger = getLogger('unauthorized_access')

def handle_roles_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            return f(*args, **kwargs)
        setattr(decorated_function, 'required_roles', roles)
        return decorated_function
    return decorator


handle_admin_required = handle_roles_required(['admin'])

handle_editor_required = handle_roles_required(['editor', 'admin'])

handle_user_required = handle_roles_required(['user', 'editor', 'admin'])
