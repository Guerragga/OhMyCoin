from contextlib import contextmanager

import mysql.connector
from mysql.connector import Error, IntegrityError

from config import Config


def get_connection(database: bool = True):
    config = dict(Config.DB_CONFIG)
    if not database:
        config.pop("database", None)
    return mysql.connector.connect(**config)


@contextmanager
def db_cursor(dictionary: bool = True, commit: bool = False):
    """Yield a MySQL cursor with automatic rollback and resource cleanup."""
    connection = get_connection()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=dictionary)
        yield cursor
        if commit:
            connection.commit()
    except IntegrityError as error:
        connection.rollback()
        if error.errno == 1062:
            raise ValueError("Já existe um registro com esses dados.") from None
        if error.errno in {1451, 1452}:
            raise ValueError("Registro vinculado ou referência inválida.") from None
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def database_ready() -> bool:
    """Return whether the configured database accepts a simple query."""
    try:
        with db_cursor() as cursor:
            cursor.execute("SELECT EXISTS(SELECT 1 FROM usuarios LIMIT 1) IN (0, 1) AS ok")
            row = cursor.fetchone()
            return bool(row and row.get("ok") == 1)
    except Error:
        return False
