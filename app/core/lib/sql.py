from sqlalchemy import Table, MetaData
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import text
from app.database import session_scope
from app.logging_config import getLogger

_logger = getLogger("sql")

def SqlExec(sql: str):
    """
    Exec SQL

    Args:
        sql (str): SQL
    """
    with session_scope() as session:
        statement = text(sql)
        session.execute(statement)

def SqlScalar(sql: str):
    """
    Exec SQL and return scalar value

    Args:
        sql (str): SQL

    Returns:
        any: scalar value
    """
    with session_scope() as session:
        statement = text(sql)
        return session.execute(statement).scalar_one_or_none()

def SqlSelectOne(sql: str) -> dict:
    """
    Exec SQL and return one row as dict

    Args:
        sql (str): SQL

    Returns:
        dict: Row
    """
    with session_scope() as session:
        statement = text(sql)
        row = session.execute(statement).one_or_none()
        if row is None:
            return None
        return row._mapping

def SqlSelect(sql) -> list:
    """
    Exec SQL and return rows as list of dict

    Args:
        sql (str): SQL

    Returns:
        list: Rows
    """
    with session_scope() as session:
        statement = text(sql)
        result = session.execute(statement).fetchall()
        res_dict = []
        for row in result:
            res_dict.append(row._mapping)

        return res_dict

def SqlInsert(table: str, data: dict):
    """
    Inserts a new row into the specified table.

    Args:
        table (str): The name of the table to insert into.
        data (dict): A dictionary of column names to values to insert.

    Returns:
        bool: True if the insert was successful, False otherwise.
    """
    with session_scope() as session:
        meta = MetaData()

        # Reflect the table from the database
        table_obj = Table(table, meta, autoload_with=session.bind)

        # Fetch the columns for the table
        table_columns = table_obj.columns

        # Exclude auto-increment columns and fill missing values
        for column in table_columns:
            # If the column is auto-increment, skip it
            if column.autoincrement:
                if column.name in data:
                    del data[column.name]
            elif column.name not in data:
                # If the column is missing from data, try to fill it with default or None if nullable
                if column.default is not None:
                    data[column.name] = column.default.arg
                elif column.nullable:
                    data[column.name] = None

        try:
            # Create an insert statement
            insert_stmt = table_obj.insert()

            # Execute the insert statement using the session
            result = session.execute(insert_stmt, data)

            # Commit the transaction
            session.commit()

            return result.rowcount == 1
        except IntegrityError as ex:
            _logger.error(ex)
            # Handle duplicate key errors
            session.rollback()
            return False
        finally:
            session.close()

def SqlUpdate(table: str, data: dict, id_column: str):
    """
    Updates a row in the specified table.

    Args:
        table (str): The name of the table to update.
        data (dict): A dictionary of column names to values to update.
        id_column (str): The name of the column to use for identifying the row to update.

    Returns:
        bool: True if the update was successful, False otherwise.
    """
    with session_scope() as session:

        meta = MetaData()

        # Reflect the table from the database
        table_obj = Table(table, meta, autoload_with=session.bind)

        try:
            # Create an update statement
            update_stmt = table_obj.update().where(getattr(table_obj.c, id_column) == data[id_column])

            # Execute the update statement using the session
            result = session.execute(update_stmt, data)

            # Commit the transaction
            session.commit()

            return result.rowcount == 1
        except IntegrityError as ex:
            _logger.error(ex)
            # Handle duplicate key errors
            session.rollback()
            return False
        finally:
            session.close()
