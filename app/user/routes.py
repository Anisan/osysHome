# -*- coding: utf-8 -*-
"""User views."""
from flask import Blueprint, request, render_template, redirect, url_for
from flask_apispec import use_kwargs, marshal_with
from flask_jwt_extended import jwt_required, create_access_token, current_user
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.exceptions import InvalidUsage
from app.core.models.Users import User
from .serializers import user_schema


blueprint = Blueprint('users', __name__)

@blueprint.route('/api/users', methods=('POST',))
@use_kwargs(user_schema)
@marshal_with(user_schema)
def register_user(username, password, **kwargs):
    try:
        user = User(username, password=password, **kwargs).save()
        user.token = create_access_token(identity=user)
    except IntegrityError:
        db.session.rollback()
        raise InvalidUsage.user_already_registered()
    return user


@blueprint.route('/api/users/login', methods=('POST',))
@jwt_required(optional = False)
@use_kwargs(user_schema)
@marshal_with(user_schema)
def login_user(username, password, **kwargs):
    user = User.query.filter_by(username=username).first()
    if user is not None and user.check_password(password):
        user.token = create_access_token(identity=user, fresh=True)
        return user
    else:
        raise InvalidUsage.user_not_found()


@blueprint.route('/api/user', methods=('GET',))
@jwt_required()
@marshal_with(user_schema)
def get_user():
    user = current_user
    # Not sure about this
    user.token = request.headers.environ['HTTP_AUTHORIZATION'].split('Token ')[1]
    return current_user


@blueprint.route('/api/user', methods=('PUT',))
@jwt_required()
@use_kwargs(user_schema)
@marshal_with(user_schema)
def update_user(**kwargs):
    user = current_user
    # take in consideration the password
    password = kwargs.pop('password', None)
    if password:
        user.set_password(password)
    user.update(**kwargs)
    return user
