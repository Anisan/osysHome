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
