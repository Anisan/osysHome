import datetime
from sqlalchemy.orm import (Mapped, mapped_column,)
from app.database import Column, Model, SurrogatePK, db
from app.core.lib.constants import CategoryNotify

class Plugin(SurrogatePK, db.Model):
    __tablename__ = 'plugins'
    name = Column(db.String(255), unique=True, nullable=False)
    title = Column(db.String(255))
    category = Column(db.String(255))
    hidden = Column(db.Boolean, default=False)
    active = Column(db.Boolean, default=True)
    config = Column(db.Text)
    url = Column(db.String(512))
    updated = Column(db.DateTime, default = datetime.datetime.now())

class Notify(SurrogatePK, db.Model):
    __tablename__ = 'notify'
    name = Column(db.String(255), nullable=False)
    description = Column(db.String(255))
    category: Mapped[CategoryNotify] = mapped_column(default=CategoryNotify.Info)
    source = Column(db.String(255), default=False)
    created = Column(db.DateTime, default = datetime.datetime.now())
    read = Column(db.Boolean, default=False)
    count = Column(db.Integer(), default=1)