# -*- coding: utf-8 -*-
"""User models."""
from flask_login import UserMixin
from app.extensions import bcrypt

class User(UserMixin):

    username: str
    password: str
    image: str
    role: str
    home_page: str

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
        else:
            self.home_page = None

    def set_password(self, password):
        """Set password."""
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, value):
        """Check password."""
        return bcrypt.check_password_hash(self.password.encode('utf-8'), value)
    
    def get_id(self):
       return (self.username)

    def __repr__(self):
        """Represent instance as a unique string."""
        return '<User({username!r})>'.format(username=self.username)
