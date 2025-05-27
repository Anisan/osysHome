from flask import g, abort, request
from flask_login import current_user, login_user
from app.utils import get_user_by_api_key
from functools import wraps

def api_key_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.is_authenticated:
            g.current_user = current_user  # Сохраняем пользователя в g для использования в маршруте
            return f(*args, **kwargs)
        # Проверяем API ключ в разных местах
        api_key = (
            request.args.get('apikey')  # Query parameter ?apikey=...
            or request.headers.get('X-API-Key')) # Заголовок X-API-Key

        if not api_key:
            abort(401, 'API key is missing')
        user = get_user_by_api_key(api_key)
        if not user:
            abort(401, 'Invalid API key')
        g.current_user = user  # Сохраняем пользователя в g для использования в маршруте
        # Вручную авторизуем пользователя через Flask-Login
        login_user(user)
        return f(*args, **kwargs)
    return decorated
