"""Migra el esquema vigente de SQLite a PostgreSQL/Supabase sin borrar el origen."""

import sqlite3
from pathlib import Path

from psycopg2.extras import execute_values

from database import get_connection, init_db

SQLITE_PATH = Path(__file__).resolve().parent / "data" / "calendar.db"


def read_rows(connection: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    return connection.execute(f"SELECT * FROM {table}").fetchall() if exists else []


def migrate() -> dict[str, int]:
    if not SQLITE_PATH.exists():
        raise FileNotFoundError(f"No se encontró la base SQLite en {SQLITE_PATH}.")

    sqlite_connection = sqlite3.connect(SQLITE_PATH)
    sqlite_connection.row_factory = sqlite3.Row
    users = read_rows(sqlite_connection, "users")
    tasks = read_rows(sqlite_connection, "tasks")
    assignments = read_rows(sqlite_connection, "calendar_assignments")
    evaluations = read_rows(sqlite_connection, "compliance_records")
    sqlite_connection.close()

    init_db()
    with get_connection() as postgres_connection, postgres_connection.cursor() as cursor:
        execute_values(
            cursor,
            """
            INSERT INTO users (id, name, pin) VALUES %s
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, pin = EXCLUDED.pin
            """,
            [(row["id"], row["name"], row["pin"]) for row in users],
        )
        execute_values(
            cursor,
            """
            INSERT INTO tasks (id, code, name, points, active) VALUES %s
            ON CONFLICT (id) DO UPDATE SET code = EXCLUDED.code, name = EXCLUDED.name,
            points = EXCLUDED.points, active = EXCLUDED.active
            """,
            [(row["id"], row["code"], row["name"], row["points"], bool(row["active"])) for row in tasks],
        )
        execute_values(
            cursor,
            """
            INSERT INTO calendar_assignments (month, week_no, work_date, day_of_week, task_id, user_id, assigned_points)
            VALUES %s
            ON CONFLICT (work_date, task_id, user_id) DO UPDATE SET month = EXCLUDED.month,
            week_no = EXCLUDED.week_no, day_of_week = EXCLUDED.day_of_week,
            assigned_points = EXCLUDED.assigned_points
            """,
            [(row["month"], row["week_no"], row["work_date"], row["day_of_week"], row["task_id"], row["user_id"], row["assigned_points"]) for row in assignments],
            page_size=1000,
        )
        execute_values(
            cursor,
            """
            INSERT INTO compliance_records (work_date, task_id, assigned_user_id, evaluator_user_id, assigned_points, completed, created_at)
            VALUES %s
            ON CONFLICT (work_date, task_id, assigned_user_id, evaluator_user_id)
            DO UPDATE SET assigned_points = EXCLUDED.assigned_points, completed = EXCLUDED.completed
            """,
            [(row["work_date"], row["task_id"], row["assigned_user_id"], row["evaluator_user_id"], row["assigned_points"], bool(row["completed"]), row["created_at"]) for row in evaluations],
        )

    return {
        "users": len(users),
        "tasks": len(tasks),
        "calendar_assignments": len(assignments),
        "compliance_records": len(evaluations),
    }


if __name__ == "__main__":
    migrated = migrate()
    print("MIGRATION_OK", migrated)
