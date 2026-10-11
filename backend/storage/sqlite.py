"""Local order storage for a demo that requires no database service."""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.getenv('POSTFLOW_SQLITE_PATH') or 'backend/data/postflow.db')
if not DB_PATH.is_absolute():
    DB_PATH = PROJECT_ROOT / DB_PATH

SCHEMA = '''CREATE TABLE IF NOT EXISTS orders (
    tracking_code TEXT PRIMARY KEY,
    sender_name TEXT NOT NULL, sender_phone TEXT NOT NULL,
    sender_province TEXT NOT NULL, sender_ward TEXT NOT NULL, sender_address TEXT NOT NULL,
    receiver_name TEXT NOT NULL, receiver_phone TEXT NOT NULL,
    receiver_province TEXT NOT NULL, receiver_ward TEXT NOT NULL, receiver_address TEXT NOT NULL,
    service TEXT NOT NULL, item_description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'WAITING_FOR_MEASUREMENT',
    actual_weight_kg REAL, length_cm REAL, width_cm REAL, height_cm REAL,
    route TEXT, chargeable_weight_kg REAL, used_volumetric_weight INTEGER, amount_vnd REAL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
)'''


@contextmanager
def _connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def initialize() -> None:
    with _connection() as conn:
        conn.execute(SCHEMA)


def _validate_columns(conn, fields):
    allowed = {row['name'] for row in conn.execute('PRAGMA table_info(orders)')}
    if set(fields) - allowed:
        raise ValueError('Unknown order field.')


def create_order(order: dict[str, Any]) -> None:
    with _connection() as conn:
        _validate_columns(conn, order)
        columns = ', '.join(order)
        placeholders = ', '.join('?' for _ in order)
        conn.execute(f'INSERT INTO orders ({columns}) VALUES ({placeholders})', tuple(order.values()))


def get_order(tracking_code: str) -> dict[str, Any] | None:
    with _connection() as conn:
        row = conn.execute('SELECT * FROM orders WHERE tracking_code = ?', (tracking_code,)).fetchone()
        return dict(row) if row else None


def update_order(tracking_code: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    if fields:
        with _connection() as conn:
            _validate_columns(conn, fields)
            assignments = ', '.join(f'{field} = ?' for field in fields)
            conn.execute(f'UPDATE orders SET {assignments} WHERE tracking_code = ?', tuple(fields.values()) + (tracking_code,))
    return get_order(tracking_code)
