# -*- coding: utf-8 -*-
"""Database module, including the SQLAlchemy database object and DB-related utilities."""
import time
import random
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from tzlocal import get_localzone
from flask_login import current_user
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker, scoped_session
from contextlib import contextmanager
from sqlalchemy import create_engine, exc, event, inspect, text, ForeignKey
from sqlalchemy.exc import ProgrammingError
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

def normalize_column_type(column_type, dialect):
    column_type_str = str(column_type).upper()

    type_mappings = {
        "mysql": {
            "TINYINT(1)": "BOOLEAN",
            "TINYINT": "BOOLEAN",
            "MEDIUMINT": "INTEGER",
            "BIGINT": "BIGINTEGER",
            "VARCHAR": "STRING",
            "TEXT": "MEDIUMTEXT"
        },
        "sqlite": {
            "BOOLEAN": "INTEGER",
            "BIGINTEGER": "INTEGER"
        },
        "postgresql": {
            "BOOLEAN": "BOOLEAN",
            "INTEGER": "INTEGER",
            "BIGINT": "BIGINTEGER",
            "TEXT": "TEXT",
            "VARCHAR": "STRING",
            "DATETIME": "TIMESTAMP",
            "TIMESTAMP": "TIMESTAMP"
        }
    }

    return type_mappings.get(dialect, {}).get(column_type_str, column_type_str)

def sync_db(app):
    with app.app_context():
        engine = db.engine
        inspector = inspect(engine)
        dialect = engine.dialect.name  # Define DBMS (mysql, postgresql, sqlite)

        for class_name, model in db.Model.registry._class_registry.items():
            if hasattr(model, '__tablename__') and hasattr(model, '__table__'):
                table_name = model.__tablename__
                safe_table_name = f'"{table_name}"' if dialect == 'postgresql' else f'`{table_name}`'  

                if not inspector.has_table(table_name):
                    logger.info(f'✅ Create table: {table_name}')
                    model.__table__.create(engine)
                else:
                    existing_columns = {col['name']: col for col in inspector.get_columns(table_name)}
                    existing_foreign_keys = {fk['constrained_columns'][0] for fk in inspector.get_foreign_keys(table_name)}

                    # Step 1: Add new columns
                    for column in model.__table__.columns:
                        if column.name not in existing_columns:
                            safe_column_name = f'"{column.name}"' if dialect == 'postgresql' else f'`{column.name}`'
                            # Normalize the column type before using it in SQL
                            column_type = normalize_column_type(column.type, dialect)

                            if dialect == 'sqlite':
                                logger.info(f'⚠ SQLite: add column {column.name}')
                                alter_stmt = text(f'ALTER TABLE {table_name} ADD COLUMN {column.name}')
                            else:
                                alter_stmt = text(f'ALTER TABLE {safe_table_name} ADD COLUMN {safe_column_name} {column_type}')

                            with engine.connect() as conn:
                                conn.execute(alter_stmt)
                                conn.commit()
                            logger.info(f'✅ Column {column.name} added in {table_name}')

                    # Step 2: Check and change column types if necessary
                    for column in model.__table__.columns:
                        if column.name in existing_columns:
                            db_column_type = existing_columns[column.name]['type']
                            # Normalize the column type before using it in SQL
                            column_type = normalize_column_type(column.type, dialect)
                            if normalize_column_type(db_column_type, dialect) != column_type:
                                if dialect == 'sqlite':
                                    logger.warning(f'⚠ SQLite: no change type in {table_name}.{column.name}')
                                    continue  # It is not possible to change the column type in SQLite
                                else:
                                    # For MySQL and PostgreSQL you can use MODIFY COLUMN
                                    safe_column_name = f'"{column.name}"' if dialect == 'postgresql' else f'`{column.name}`'
                                    if dialect == 'postgresql':
                                        alter_stmt = text(f'ALTER TABLE {safe_table_name} ALTER COLUMN {safe_column_name} TYPE {column_type}')
                                    elif dialect == 'mysql':
                                        alter_stmt = text(f'ALTER TABLE {safe_table_name} MODIFY COLUMN {safe_column_name} {column_type}')
                                    with engine.connect() as conn:
                                        conn.execute(alter_stmt)
                                        conn.commit()
                                    logger.info(f'✅ Changed type column {column.name} in {table_name} of {column_type}')

                    # Step 3: Remove columns that are no longer present in the model
                    for db_column in existing_columns.values():
                        if db_column['name'] not in model.__table__.columns:
                            try:
                                alter_stmt = text(f'ALTER TABLE {safe_table_name} DROP COLUMN {db_column["name"]}')
                                with engine.connect() as conn:
                                    conn.execute(alter_stmt)
                                    conn.commit()
                                logger.info(f'✅ Deleted column {db_column["name"]} in {table_name}')
                            except ProgrammingError as e:
                                logger.error(f'❌ Error delete column {db_column["name"]} in {table_name}: {e}')

                    # Step 4: Check and create/update foreign keys
                    for column in model.__table__.columns:
                        if isinstance(column.type, ForeignKey):
                            fk_name = f'fk_{table_name}_{column.name}'
                            referenced_table = column.type.target_fullname.split('.')[0]
                            referenced_column = column.type.target_fullname.split('.')[1]

                            if fk_name not in existing_foreign_keys:
                                logger.info(f'🔗 Add foreignkey: {table_name}.{column.name} → {referenced_table}.{referenced_column}')
                                alter_stmt = text(
                                    f'ALTER TABLE {safe_table_name} ADD CONSTRAINT {fk_name} '
                                    f'FOREIGN KEY ({column.name}) REFERENCES {referenced_table} ({referenced_column})'
                                )
                                with engine.connect() as conn:
                                    conn.execute(alter_stmt)
                                    conn.commit()
                                logger.info(f'✅ Foreignkey {table_name}.{column.name} → {referenced_table}.{referenced_column} added')

                    # Step 5: Remove unnecessary foreign keys
                    if dialect != 'sqlite':
                        for fk in inspector.get_foreign_keys(table_name):
                            fk_name = fk['name']
                            if fk_name not in [f'fk_{table_name}_{column.name}' for column in model.__table__.columns if isinstance(column.type, ForeignKey)]:
                                try:
                                    alter_stmt = text(f'ALTER TABLE {safe_table_name} DROP CONSTRAINT {fk_name}')
                                    with engine.connect() as conn:
                                        conn.execute(alter_stmt)
                                        conn.commit()
                                    logger.info(f'✅ Deleted foreignkey {fk_name} in {table_name}')
                                except ProgrammingError as e:
                                    logger.error(f'❌ Error delete foreignkey {fk_name} in {table_name}: {e}')

# Функция для логирования SQL-запросов
def log_sql_statement(conn, cursor, statement, parameters, context, executemany):
    if Config.SQLALCHEMY_ECHO:
        logger.debug(f"Executing SQL: {statement} with params: {parameters}")

# Подключаем обработчик к движку SQLAlchemy
@event.listens_for(engine, 'before_cursor_execute')
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    log_sql_statement(conn, cursor, statement, parameters, context, executemany)

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
    timezone = getattr(current_user, 'timezone', None)
    d = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        # Если значение - это datetime и указан часовой пояс пользователя
        if isinstance(value, datetime) and timezone:
            # Преобразуем время из UTC в локальное время пользователя
            utc_time = value.replace(tzinfo=ZoneInfo("UTC"))  # Добавляем временную зону UTC
            local_time = utc_time.astimezone(ZoneInfo(timezone))  # Конвертируем в локальное время
            d[column.name] = local_time.replace(tzinfo=None)
        else:
            d[column.name] = value
    return d

def convert_utc_to_local(utc_time, timezone:str=None):
    """
    Convert UTC to local time user
    """
    if utc_time is None:
        return None
    if timezone is None:
        timezone = getattr(current_user, 'timezone', None)
    if utc_time.tzinfo is None:
        utc_time = utc_time.replace(tzinfo=ZoneInfo("UTC"))
    if timezone is None:
        timezone = get_localzone().zone
    local_timezone = ZoneInfo(timezone)
    local_time = utc_time.astimezone(local_timezone)
    return local_time.replace(tzinfo=None)

def convert_local_to_utc(local_time, timezone:str=None):
    """
    Convert local time user to UTC
    """
    if local_time is None:
        return None
    if timezone is None:
        timezone = getattr(current_user, 'timezone', None)
    if timezone is None:
        timezone = get_localzone().zone
    local_timezone = ZoneInfo(timezone)
    aware_local_time = local_time.replace(tzinfo=local_timezone)
    utc_time = aware_local_time.astimezone(ZoneInfo("UTC"))
    return utc_time.replace(tzinfo=None)

def get_now_to_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)
