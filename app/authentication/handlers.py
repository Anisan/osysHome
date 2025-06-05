from functools import wraps

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
