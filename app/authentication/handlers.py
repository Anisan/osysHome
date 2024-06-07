from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user

def handle_login_required(required_roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Check if user is logged in
            if not current_user.is_authenticated:
                flash('You need to log in first.', 'error')
                return redirect(url_for('authentication_blueprint.login'))

            # Check if user has required roles
            if not any(role == current_user.role for role in required_roles):
                flash('You do not have permission to access this page.', 'error')
                return redirect(url_for('access_forbidden'))
            
            # If user has required roles, execute the original function
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator

handle_admin_required = handle_login_required(['admin'])

handle_user_required = handle_login_required(['user','admin'])