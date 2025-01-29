from flask import g, abort, request
from flask_login import current_user
from app.utils import get_user_by_api_key
from functools import wraps

def api_key_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.is_authenticated:
            g.current_user = current_user  # Сохраняем пользователя в g для использования в маршруте
            return f(*args, **kwargs)
        api_key = request.args.get('apikey')
        if not api_key:
            abort(401, 'API key is missing')
        user = get_user_by_api_key(api_key)
        if not user:
            abort(401, 'Invalid API key')
        g.current_user = user  # Сохраняем пользователя в g для использования в маршруте
        return f(*args, **kwargs)
    return decorated

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if current_user.is_authenticated:
                user = current_user
            else:
                user = g.get('current_user')
            if not user:
                abort(401, 'Authorization required')
            if user.role != role and user.role != 'admin':
                abort(403, 'Forbidden: Insufficient permissions. Only for '+role)
            return f(*args, **kwargs)
        return decorated
    return decorator