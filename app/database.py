# -*- coding: utf-8 -*-
"""Database module, including the SQLAlchemy database object and DB-related utilities."""
import time
import random
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker, scoped_session
from contextlib import contextmanager
from sqlalchemy import create_engine, exc
from settings import Config
from .extensions import db
from .logging_config import getLogger

try:
    # the declarative API is a part of the ORM layer since SQLAlchemy 1.4
    from sqlalchemy.orm import declarative_base
except ImportError:
    # however it used to be an extension before SQLAlchemy 1.4
    from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Alias common SQLAlchemy names
Column = db.Column
relationship = relationship
Model = db.Model

# From Mike Bayer's "Building the app" talk
# https://speakerdeck.com/zzzeek/building-the-app
class SurrogatePK(object):
    """A mixin that adds a surrogate integer 'primary key' column named ``id`` \
        to any declarative-mapped class.
    """

    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)

    @classmethod
    def get_by_id(cls, record_id):
        """Get record by ID."""
        if any(
                (isinstance(record_id, (str, bytes)) and record_id.isdigit(),
                 isinstance(record_id, (int, float))),
        ):
            return cls.query.get(int(record_id))


def reference_col(tablename, nullable=False, pk_name='id', **kwargs):
    """Column that adds primary key foreign key reference.

    Usage: ::

        category_id = reference_col('category')
        category = relationship('Category', backref='categories')
    """
    return db.Column(
        db.ForeignKey('{0}.{1}'.format(tablename, pk_name)),
        nullable=nullable, **kwargs)


# define the database
engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, pool_size=20, max_overflow=30)
Base.metadata.create_all(engine)
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

logger = getLogger('session')

def model_exists(model_class):
    # The recommended way to check for existence
    import sqlalchemy
    return sqlalchemy.inspect(engine).has_table(model_class.__tablename__)
    # return model_class.metadata.tables[model_class.__tablename__].exists(engine)

def getSession():
    session_obj = scoped_session(DBSession)
    session = session_obj()
    return session

@contextmanager
def session_scope():
    """When accessing the database, use the following syntax:
    >>> with session_scope() as session:
    >>>     session.query(...)
    :return: the session for accessing the database.
    """
    session_obj = scoped_session(DBSession)
    session = session_obj()
    try:
        yield session
        session.commit()
    except exc.OperationalError:
        session.rollback()
        time.sleep(0.5 + random.random())
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception('No commit has been made, due to the following error: {}'.format(e))
        raise e
    finally:
        session.close()


def row2dict(row):
    """Converts a database-object to a python dict.
    This function can be used to serialize an object into JSON, as this cannot be
    directly done (but a dict can).
    :param row: any object
    :return: dict
    """
    d = {}
    for column in row.__table__.columns:
        d[column.name] = getattr(row, column.name)

    return d
