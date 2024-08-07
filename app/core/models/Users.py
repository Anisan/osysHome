# -*- coding: utf-8 -*-
"""User models."""
from flask_login import UserMixin
from app.extensions import bcrypt

class User(UserMixin):

    username: str = None
    password: str = None
    image: str = None
    role: str = None
    home_page: str = None
    apikey: str = None

    def __init__(self, object):
        self.username = object.name
        if object.getProperty('password'):
            self.password = object.password
        if object.getProperty('image'):
            self.image = object.image
        if object.getProperty('role'):
            self.role = object.role
        if object.getProperty('home_page'):
            self.home_page = object.home_page
        self.apikey = object.getProperty('apikey')

    def set_password(self, password):
        """Set password."""
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, value):
        """Check password."""
        return bcrypt.check_password_hash(self.password.encode('utf-8'), value)

    def get_id(self):
        return self.username

    def __repr__(self):
        """Represent instance as a unique string."""
        return '<User({username!r})>'.format(username=self.username)

    def to_dict(self):
        return {
            'username': self.username,
            'role': self.role
        }
