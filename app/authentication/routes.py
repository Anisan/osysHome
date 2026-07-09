import datetime
from flask import render_template, redirect, request, url_for, session
from flask_login import (
    current_user,
    login_user,
    logout_user
)
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

from . import blueprint
from .forms import LoginForm
from app.extensions import login_manager, limiter, cache
from app.core.models.Users import User
from app.core.lib.object import getObject, getObjectsByClass, addObject, setProperty
from app import safe_translate as _

from app.logging_config import security_audit_log, log_app_exception
from app.authentication.handlers import public_endpoint


def _get_client_ip():
    if request.headers.getlist("X-Forwarded-For"):
        return request.headers.getlist("X-Forwarded-For")[0]
    return request.remote_addr or '?'

@blueprint.route('/')
def route_default():
    return redirect(url_for('auth.login'))

# Login & Registration

def _login_rate_limit():
    from app.configuration import Config
    return Config.RATELIMIT_LOGIN if Config.RATELIMIT_ENABLED else '10000 per minute'


def _apply_login_limit(f):
    if limiter:
        return limiter.limit(_login_rate_limit)(f)
    return f


def _process_login(username, password, login_form, register=False):
    ip = _get_client_ip()

    lock_key = f"login_lock:{username}:{ip}"
    lock_info = cache.get(lock_key)
    if lock_info:
        return render_template('accounts/login.html',
                               msg=_('Wrong user or password'),
                               register=register,
                               form=login_form)

    users = getObjectsByClass('Users')
    user = None
    obj = getObject(username)
    if obj:
        user = User(obj)
    elif users is None or len(users) == 0:
        obj = addObject(username, "Users", "Administrator")
        user = User(obj)
        user.set_password(password)
        user.role = 'admin'
        session.permanent = True
        login_user(user)
        setProperty(username + ".password", user.password)
        setProperty(username + ".role", 'admin')

        from app.utils import initPermissions
        initPermissions()

        security_audit_log(
            'LOGIN_SUCCESS',
            ip=ip,
            url=request.url,
            username=username,
            reason='first_admin_created'
        )
        return redirect("/")

    if user and user.password and user.check_password(password):
        setProperty(username + ".lastLogin", datetime.datetime.now(), source=ip)
        session.permanent = True
        login_user(user)
        security_audit_log(
            'LOGIN_SUCCESS',
            ip=ip,
            url=request.url,
            username=username,
            reason='user_authenticated'
        )
        return redirect("/")

    fail_key = f"login_fail:{username}:{ip}"
    lock_timeout = 15 * 60
    fail_count = cache.get(fail_key) or 0
    fail_count += 1
    cache.set(fail_key, fail_count, timeout=lock_timeout)

    max_failures = 5
    if fail_count >= max_failures:
        cache.set(lock_key, True, timeout=lock_timeout)
        security_audit_log(
            'LOGIN_LOCKED',
            ip=ip,
            url=request.url,
            username=username,
            reason=f'too_many_failed_attempts({fail_count})'
        )

    security_audit_log('LOGIN_FAILED', ip=ip, url=request.url, username=username)

    return render_template('accounts/login.html',
                           msg=_('Wrong user or password'),
                           register=register,
                           form=login_form)


@blueprint.route('/login', methods=['GET', 'POST'])
@_apply_login_limit
@public_endpoint
def login():
    login_form = LoginForm()
    users = getObjectsByClass('Users')
    register = not users

    if login_form.validate_on_submit():
        username = (login_form.username.data or '').strip()
        password = login_form.password.data or ''

        if not username:
            return render_template('accounts/login.html',
                                   msg=_('Username cannot be empty'),
                                   register=register,
                                   form=login_form)

        if not password:
            return render_template('accounts/login.html',
                                   msg=_('Password cannot be empty'),
                                   register=register,
                                   form=login_form)

        return _process_login(username, password, login_form, register=register)

    if not current_user.is_authenticated:
        msg = None
        if register:
            msg = _('For create a user with administrator rights, specify login and password!')
        return render_template('accounts/login.html',
                               form=login_form,
                               register=register,
                               msg=msg)

    home_page = current_user.home_page
    if not home_page:
        home_page = '/admin'
    return redirect(home_page)


@blueprint.route('/logout', methods=['GET', 'POST'])
@public_endpoint
def logout():
    if request.method == 'POST':
        try:
            validate_csrf(request.form.get('csrf_token'))
        except ValidationError:
            return render_template('errors/page-403.html'), 403

    ip = _get_client_ip()
    username = getattr(current_user, 'username', '') or 'anonymous'
    security_audit_log(
        'LOGOUT',
        ip=ip,
        url=request.url,
        username=username,
        reason='user_logout'
    )
    logout_user()
    return redirect(url_for('auth.login'))

# Errors

@login_manager.unauthorized_handler
def unauthorized_handler():
    try:
        security_audit_log(
            'UNAUTHORIZED', ip=_get_client_ip(), url=request.url, endpoint=request.endpoint or '?',
            reason='login_required', user_agent=request.headers.get('User-Agent', '')
        )
    except Exception:
        pass
    return render_template('errors/page-403.html'), 403


@blueprint.errorhandler(401)
def unauthorized(error):
    return render_template('errors/page-401.html'), 401


@blueprint.errorhandler(403)
def access_forbidden(error):
    return render_template('errors/page-403.html'), 403


@blueprint.errorhandler(404)
def not_found_error(error):
    return render_template('errors/page-404.html'), 404


@blueprint.errorhandler(429)
def too_many_requests(error):
    return render_template('errors/page-429.html'), 429


@blueprint.errorhandler(500)
def internal_error(error):
    log_app_exception(error)
    return render_template('errors/page-500.html'), 500
