from sqlalchemy import Table, MetaData
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import text
from app.database import session_scope

def SqlExec(sql: str):
    with session_scope() as session:
        statement = text(sql)
        return session.execute(statement).scalar_one_or_none()

def SqlSelectOne(sql: str) -> dict:
    with session_scope() as session:
        statement = text(sql)
        row = session.execute(statement).one_or_none()
        if row is None:
            return None
        return row._mapping
      
def SqlSelect(sql) -> list:
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

        try:
            # Create an insert statement
            insert_stmt = table_obj.insert()

            # Execute the insert statement using the session
            result = session.execute(insert_stmt, data)

            # Commit the transaction
            session.commit()

            return result.rowcount == 1
        except IntegrityError:
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
        except IntegrityError:
            # Handle duplicate key errors
            session.rollback()
            return False
        finally:
            session.close()