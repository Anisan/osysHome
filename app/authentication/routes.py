import datetime
from flask import render_template, redirect, request, url_for, session
from flask_login import (
    current_user,
    login_user,
    logout_user
)

from . import blueprint
from .forms import LoginForm
from app.extensions import login_manager, limiter, cache
from app.core.models.Users import User
from app.core.lib.object import getObject, getObjectsByClass, addObject, setProperty
from app import safe_translate as _

from app.logging_config import security_audit_log


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


@blueprint.route('/login', methods=['GET', 'POST'])
@_apply_login_limit
def login():
    login_form = LoginForm(request.form)
    users = getObjectsByClass('Users')

    if 'login' in request.form and request.method == "POST":

        # read form data
        username = request.form['username']
        if not username:
            return render_template('accounts/login.html',
                                   msg=_('Username cannot be empty'),
                                   register=False,
                                   form=login_form)

        password = request.form['password']
        if not password:
            return render_template('accounts/login.html',
                                   msg=_('Password cannot be empty'),
                                   register=False,
                                   form=login_form)

        ip = _get_client_ip()

        # Проверка на блокировку по username+ip (эскалация после N неудач)
        lock_key = f"login_lock:{username}:{ip}"
        lock_info = cache.get(lock_key)
        if lock_info:
            # Уже заблокирован — не даём даже проверять пароль
            # Логирование события блокировки выполняется в момент её установки,
            # поэтому здесь повторно в audit-лог не пишем, чтобы избежать дублей.
            return render_template('accounts/login.html',
                                   msg=_('Wrong user or password'),
                                   register=False,
                                   form=login_form)

        user = None
        obj = getObject(username)
        if obj:
            user = User(obj)
        else:
            if users is None or len(users) == 0:
                # Create first admin user
                obj = addObject(username,"Users","Administrator")
                user = User(obj)
                user.set_password(password)
                user.role = 'admin'
                session.permanent = True
                login_user(user)
                setProperty(username + ".password", user.password)
                setProperty(username + ".role", 'admin')

                from app.utils import initPermissions
                initPermissions()

        # Check the password
        if user and user.password and user.check_password(password):
            setProperty(username + ".lastLogin",datetime.datetime.now(),source=ip)
            session.permanent = True
            login_user(user)
            return redirect("/")

        # Something (user or pass) is not ok

        # Регистрируем неудачную попытку для username+ip
        fail_key = f"login_fail:{username}:{ip}"
        # окно блокировки, сек
        lock_timeout = 15 * 60
        fail_count = cache.get(fail_key) or 0
        fail_count += 1
        # храним счётчик в том же временном окне, что и блокировку
        cache.set(fail_key, fail_count, timeout=lock_timeout)

        # после N неудач — блокируем на lock_timeout
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
                               register=False,
                               form=login_form)

    if not current_user.is_authenticated:
        msg = None
        register = False
        if not users:
            msg = _('For create a user with administrator rights, specify login and password!')
            register = True
        return render_template('accounts/login.html',
                               form=login_form,
                               register=register,
                               msg=msg)
    # get home page from settings user
    home_page = current_user.home_page
    if not home_page:
        home_page = '/admin'
    return redirect(home_page)


@blueprint.route('/logout')
def logout():
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


@blueprint.errorhandler(403)
def access_forbidden(error):
    return render_template('errors/page-403.html'), 403


@blueprint.errorhandler(404)
def not_found_error(error):
    return render_template('errors/page-404.html'), 404


@blueprint.errorhandler(500)
def internal_error(error):
    return render_template('errors/page-500.html'), 500
