from functools import wraps

def handle_roles_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            return f(*args, **kwargs)
        setattr(decorated_function, 'required_roles', roles)
        return decorated_function
    return decorator


def public_endpoint(f):
    """Mark route as accessible without session/API-key auth (own auth may apply in handler)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    setattr(decorated_function, 'public_access', True)
    return decorated_function


handle_admin_required = handle_roles_required(['admin'])

handle_editor_required = handle_roles_required(['editor', 'admin'])

handle_user_required = handle_roles_required(['user', 'editor', 'admin'])
