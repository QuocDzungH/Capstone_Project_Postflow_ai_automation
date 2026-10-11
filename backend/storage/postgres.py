"""PostgreSQL persistence layer for PostFlow MVP."""
from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]


def _get_connection():
    """Create and return a PostgreSQL connection."""
    return psycopg2.connect(DATABASE_URL)


def initialize() -> None:
    """Create orders table if it doesn't exist."""
    with _get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS orders (
                    tracking_code TEXT PRIMARY KEY,
                    sender_name TEXT NOT NULL,
                    sender_phone TEXT NOT NULL,
                    sender_province TEXT NOT NULL,
                    sender_ward TEXT NOT NULL,
                    sender_address TEXT NOT NULL,
                    receiver_name TEXT NOT NULL,
                    receiver_phone TEXT NOT NULL,
                    receiver_province TEXT NOT NULL,
                    receiver_ward TEXT NOT NULL,
                    receiver_address TEXT NOT NULL,
                    service TEXT NOT NULL,
                    item_description TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'WAITING_FOR_MEASUREMENT',
                    actual_weight_kg REAL,
                    length_cm REAL,
                    width_cm REAL,
                    height_cm REAL,
                    route TEXT,
                    chargeable_weight_kg REAL,
                    used_volumetric_weight INTEGER,
                    amount_vnd REAL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            conn.commit()


def create_order(order: dict[str, Any]) -> None:
    """Insert a new order into the database."""
    # Convert boolean to integer for PostgreSQL
    order_copy = order.copy()
    if "used_volumetric_weight" in order_copy:
        order_copy["used_volumetric_weight"] = 1 if order_copy["used_volumetric_weight"] else 0

    with _get_connection() as conn:
        with conn.cursor() as cursor:
            columns = ", ".join(order_copy.keys())
            placeholders = ", ".join(["%s"] * len(order_copy))
            values = tuple(order_copy.values())

            query = f"INSERT INTO orders ({columns}) VALUES ({placeholders})"
            cursor.execute(query, values)
            conn.commit()


def get_order(tracking_code: str) -> dict[str, Any] | None:
    """Retrieve an order by tracking code."""
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM orders WHERE tracking_code = %s", (tracking_code,))
            row = cursor.fetchone()
            return dict(row) if row else None


def update_order(tracking_code: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    """Update specific fields of an order."""
    if not fields:
        return get_order(tracking_code)

    # Convert boolean to integer for PostgreSQL
    fields_copy = fields.copy()
    if "used_volumetric_weight" in fields_copy:
        fields_copy["used_volumetric_weight"] = 1 if fields_copy["used_volumetric_weight"] else 0

    with _get_connection() as conn:
        with conn.cursor() as cursor:
            set_clauses = ", ".join([f"{key} = %s" for key in fields_copy.keys()])
            values = tuple(fields_copy.values()) + (tracking_code,)

            query = f"UPDATE orders SET {set_clauses} WHERE tracking_code = %s"
            cursor.execute(query, values)
            conn.commit()

    return get_order(tracking_code)
