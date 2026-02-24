# -*- coding: utf-8 -*-
"""Extensions module. Each extension is initialized in the app factory located in app.py."""

from flask import request
from flask_bcrypt import Bcrypt
from flask_caching import Cache
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except ImportError:
    Limiter = None
try:
    from flask_debugtoolbar import DebugToolbarExtension
except ImportError:  # pragma: no cover - optional dependency
    DebugToolbarExtension = None


def _rate_limit_key():
    """IP для rate limit с учётом X-Forwarded-For (reverse proxy)."""
    if request.headers.getlist("X-Forwarded-For"):
        return request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
    return get_remote_address()

class CRUDMixin(object):
    """Mixin that adds convenience methods for CRUD (create, read, update, delete) operations."""

    @classmethod
    def create(cls, **kwargs):
        """Create a new record and save it the database."""
        instance = cls(**kwargs)
        return instance.save()

    def update(self, commit=True, **kwargs):
        """Update specific fields of a record."""
        for attr, value in kwargs.items():
            setattr(self, attr, value)
        return commit and self.save() or self

    def save(self, commit=True):
        """Save the record."""
        db.session.add(self)
        if commit:
            db.session.commit()
        return self

    def delete(self, commit=True):
        """Remove the record from the database."""
        db.session.delete(self)
        return commit and db.session.commit()


bcrypt = Bcrypt()
db = SQLAlchemy(model_class=CRUDMixin)
cache = Cache()
cors = CORS()
toolbar = DebugToolbarExtension() if DebugToolbarExtension else None
limiter = Limiter(key_func=_rate_limit_key) if Limiter else None

from .utils import load_user  # noqa

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.user_loader(load_user)
