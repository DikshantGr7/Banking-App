import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Tuple, Any
import os


class Database:
    def __init__(self, db_path: str = "database/banking.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @contextmanager
    def transaction(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def initialize(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    phone TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    account_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    account_type TEXT NOT NULL,
                    account_number TEXT UNIQUE NOT NULL,
                    balance REAL DEFAULT 0.0,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    transaction_type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT,
                    status TEXT DEFAULT 'COMPLETED',
                    related_account_id INTEGER,
                    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
                    FOREIGN KEY (related_account_id) REFERENCES accounts(account_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS otp (
                    otp_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    otp_code TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                )
            """)

            conn.commit()

    def execute_query(self, query: str, params: Tuple = ()) -> List[Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

    def execute_insert(self, query: str, params: Tuple = ()) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid

    def execute_update(self, query: str, params: Tuple = ()) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount

    def execute_transaction(self, queries: List[Tuple[str, Tuple]]) -> bool:
        with self.transaction() as conn:
            cursor = conn.cursor()
            for query, params in queries:
                cursor.execute(query, params)
        return True
