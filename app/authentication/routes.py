import datetime
from flask import render_template, redirect, request, url_for
from flask_login import (
    current_user,
    login_user,
    logout_user
)

from . import blueprint
from .forms import LoginForm
from app.extensions import login_manager
from app.core.models.Users import User
from app.core.lib.object import getObject, getObjectsByClass, addObject, setProperty
from app import safe_translate as _

from app.logging_config import getLogger  
_logger = getLogger("security")  

@blueprint.route('/')
def route_default():
    return redirect(url_for('auth.login'))

# Login & Registration

@blueprint.route('/login', methods=['GET', 'POST'])
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
                login_user(user)
                setProperty(username + ".password", user.password)
                setProperty(username + ".role", 'admin')

                from app.utils import initPermissions
                initPermissions()

        # Check the password
        if user and user.password and user.check_password(password):
            ip = ""
            if request.headers.getlist("X-Forwarded-For"):
                ip = request.headers.getlist("X-Forwarded-For")[0]
            else:
                ip = request.remote_addr
            setProperty(username + ".lastLogin",datetime.datetime.now(),source=ip)
            login_user(user)
            return redirect("/")

        # Something (user or pass) is not ok
        ip = request.headers.getlist("X-Forwarded-For")[0] if request.headers.getlist("X-Forwarded-For") else request.remote_addr
        _logger.warning(f"Failed login attempt for user '{username}' from {ip}")

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
