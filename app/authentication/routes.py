# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from flask import render_template, redirect, request, url_for
from flask_login import (
    current_user,
    login_user,
    logout_user
)

from app.extensions import db, login_manager
from . import blueprint
from .forms import LoginForm
from app.core.models.Users import User
from app.core.lib.object import getObject, getObjectsByClass, addClass, addObject, setProperty, getProperty

@blueprint.route('/')
def route_default():
    return redirect(url_for('authentication_blueprint.login'))

# Login & Registration

@blueprint.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm(request.form)
    if 'login' in request.form:

        # read form data
        username = request.form['username']
        password = request.form['password']

        user = None
        obj = getObject(username)
        if obj:
            user = User(obj)
        else:
            users = getObjectsByClass('Users')
            if len(users) == 0:
                addClass('Users')
                #todo add properties - password, role, home_page
                obj = addObject(username,"Users")
                user = User(obj)
                user.set_password(password)
                user.role = 'admin'
                setProperty(username+".password", user.password)
                setProperty(username+".role", 'admin')

        # Check the password
        if user and user.check_password(password):
            login_user(user)
            return redirect("/")

        # Something (user or pass) is not ok
        return render_template('accounts/login.html',
                               msg='Wrong user or password',
                               form=login_form)

    if not current_user.is_authenticated:
        return render_template('accounts/login.html',
                               form=login_form)
    home_page = current_user.home_page
    if not home_page:
        home_page = '/admin'
    return redirect(home_page) #TODO get from settings user


@blueprint.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('authentication_blueprint.login')) 

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