from app.database import Column, SurrogatePK, db, get_now_to_utc


class CustomFunction(SurrogatePK, db.Model):
    """User-defined Python functions shared across object methods."""

    __tablename__ = 'custom_functions'

    name = Column(db.String(255), unique=True, nullable=False)
    description = Column(db.String(512))
    code = Column(db.Text)
    test_code = Column(db.Text)
    active = Column(db.Boolean, default=True, nullable=False)
    order = Column(db.Integer, default=0, nullable=False)
    updated = Column(db.DateTime, default=get_now_to_utc, onupdate=get_now_to_utc)
