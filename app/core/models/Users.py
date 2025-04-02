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
    pages_access: list = []
    pages_denied: list = []

    def __init__(self, objectUser):
        self.username = object.__getattribute__(objectUser, 'name')
        if 'password' in objectUser.__dict__['properties']:
            self.password = objectUser.__dict__['properties']["password"]._PropertyManager__value
        if 'image' in objectUser.__dict__['properties']:
            self.image = objectUser.__dict__['properties']["image"]._PropertyManager__value
        if 'role' in objectUser.__dict__['properties']:
            self.role = objectUser.__dict__['properties']["role"]._PropertyManager__value
        if 'home_page' in objectUser.__dict__['properties']:
            self.home_page = objectUser.__dict__['properties']["home_page"]._PropertyManager__value
        if 'apikey' in objectUser.__dict__['properties']:
            self.apikey = objectUser.__dict__['properties']["apikey"]._PropertyManager__value

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
