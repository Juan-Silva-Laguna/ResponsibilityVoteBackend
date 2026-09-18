import calendar
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor, execute_values

load_dotenv(Path(__file__).resolve().parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
DAY_CODES = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
USERS = ((1, "Alexa", "1508"), (2, "Michell", "1515"))
TASKS = (
    (1, "gomitas", "Hacer gomitas", 3), (2, "domicilios", "Domicilios", 3),
    (3, "colegios", "Ir a colegios", 4), (4, "video", "Video", 3),
    (5, "fruta", "Comprar fruta", 2), (6, "punto", "Preparar y llevar al punto", 3),
    (7, "comandas", "Ingresar comandas", 2), (8, "cuentas", "Contar dinero / hacer cuentas", 4),
    (9, "loza", "Lavar loza", 2), (10, "preparar_empleada", "Alistar pedido para empleada", 3),
)


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL no está configurada. Define la conexión de PostgreSQL en el entorno o en backend/.env.")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, connect_timeout=10)


def init_db() -> None:
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, pin TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                points DOUBLE PRECISION NOT NULL, active BOOLEAN NOT NULL DEFAULT TRUE
            );
            CREATE TABLE IF NOT EXISTS calendar_assignments (
                id BIGSERIAL PRIMARY KEY,
                month TEXT NOT NULL, week_no INTEGER NOT NULL, work_date DATE NOT NULL,
                day_of_week TEXT NOT NULL, task_id INTEGER NOT NULL REFERENCES tasks(id),
                user_id INTEGER NOT NULL REFERENCES users(id), assigned_points DOUBLE PRECISION NOT NULL,
                UNIQUE(work_date, task_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS compliance_records (
                id BIGSERIAL PRIMARY KEY,
                work_date DATE NOT NULL, task_id INTEGER NOT NULL REFERENCES tasks(id),
                assigned_user_id INTEGER NOT NULL REFERENCES users(id),
                evaluator_user_id INTEGER NOT NULL REFERENCES users(id),
                assigned_points DOUBLE PRECISION NOT NULL, completed BOOLEAN NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(work_date, task_id, assigned_user_id, evaluator_user_id)
            );
        """)
        cursor.executemany(
            "INSERT INTO users (id, name, pin) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING",
            USERS,
        )
        cursor.executemany(
            "INSERT INTO tasks (id, code, name, points, active) VALUES (%s, %s, %s, %s, TRUE) ON CONFLICT (id) DO NOTHING",
            TASKS,
        )


def parse_month(month: str) -> tuple[int, int]:
    try:
        parsed = datetime.strptime(month, "%Y-%m")
    except ValueError as error:
        raise ValueError("El mes debe tener formato AAAA-MM.") from error
    return parsed.year, parsed.month


def month_weeks(month: str) -> list[dict[str, Any]]:
    year, month_number = parse_month(month)
    first = date(year, month_number, 1)
    last = date(year, month_number, calendar.monthrange(year, month_number)[1])
    weeks = []
    start = first
    week_number = 1
    while start <= last:
        end = min(start + timedelta(days=6 - start.weekday()), last)
        weeks.append({"week_no": week_number, "start_date": start.isoformat(), "end_date": end.isoformat()})
        start = end + timedelta(days=1)
        week_number += 1
    return weeks


def cycle_number(work_date: date) -> int:
    anchor_monday = date(2026, 8, 31)
    monday = work_date - timedelta(days=work_date.weekday())
    return ((monday - anchor_monday).days // 7) % 4 + 1


def daily_template(work_date: date) -> list[tuple[int, int, float]]:
    weekday = work_date.weekday()
    cycle = cycle_number(work_date)
    high, low = (2.1, 0.9) if cycle in (2, 4) else (1.8, 1.2)
    if weekday == 0:
        return [(1, 1, 3), (1, 2, 3), (3, 1, 4), (3, 2, 4), (2, 1, high), (2, 2, low), (4, 2, 3)]
    if weekday == 1:
        fruit_owner = 2 if cycle == 2 else 1
        return [(1, 1, 3), (1, 2, 3), (3, 1, 4), (3, 2, 4), (2, 1, high), (2, 2, low), (5, fruit_owner, 2), (4, 2, 3)]
    if weekday == 2:
        return [(2, 1, 3), (6, 1, 3), (7, 1, 2), (8, 1, 4), (9, 1, 2)]
    if weekday == 3:
        return [(2, 2, 3), (6, 2, 3), (7, 2, 2), (8, 2, 4), (9, 2, 2)]
    if weekday == 4:
        operation = [(2, 1, 3), (7, 1, 2), (8, 1, 4), (9, 1, 2)]
        preparation = (10, 2, 3) if cycle in (2, 4) else (10, 1, 3)
        return [*operation, preparation]
    if weekday == 5:
        alexa_domicilios, michell_domicilios = (1.5, 1.5) if cycle in (2, 4) else (2, 1)
        return [(2, 1, alexa_domicilios), (2, 2, michell_domicilios)]
    if weekday == 6:
        operation = [(2, 2, 3), (7, 2, 2), (8, 2, 4), (9, 2, 2)]
        preparation = (10, 1, 3) if cycle in (2, 4) else (10, 2, 3)
        return [*operation, preparation]
    return []


def sync_schedule_from(start_date: date) -> dict[str, int]:
    """Actualiza calendarios existentes sin borrar asignaciones que ya fueron evaluadas."""
    init_db()
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT MAX(work_date) AS last_date FROM calendar_assignments")
        last_date = cursor.fetchone()["last_date"]
        if not last_date or start_date > last_date:
            return {"upserted": 0, "removed": 0}

        cursor.execute("""
            DELETE FROM calendar_assignments ca
            WHERE ca.work_date >= %s
              AND ca.day_of_week IN ('jueves', 'sabado')
              AND ca.task_id = 10
              AND NOT EXISTS (
                  SELECT 1 FROM compliance_records cr
                  WHERE cr.work_date = ca.work_date AND cr.task_id = ca.task_id
                    AND cr.assigned_user_id = ca.user_id
              )
        """, (start_date,))
        removed = cursor.rowcount

        cursor.execute("""
            DELETE FROM calendar_assignments ca
            USING tasks t
            WHERE ca.task_id = t.id AND t.code = 'graba'
              AND NOT EXISTS (
                  SELECT 1 FROM compliance_records cr
                  WHERE cr.work_date = ca.work_date AND cr.task_id = ca.task_id
                    AND cr.assigned_user_id = ca.user_id
              )
        """)
        removed += cursor.rowcount
        cursor.execute("""
            DELETE FROM tasks t
            WHERE t.code = 'graba'
              AND NOT EXISTS (SELECT 1 FROM calendar_assignments ca WHERE ca.task_id = t.id)
              AND NOT EXISTS (SELECT 1 FROM compliance_records cr WHERE cr.task_id = t.id)
        """)

        rows = []
        current = start_date
        while current <= last_date:
            if current.weekday() in (0, 3, 4, 5, 6):
                month = current.strftime("%Y-%m")
                week_no = next(
                    week["week_no"] for week in month_weeks(month)
                    if week["start_date"] <= current.isoformat() <= week["end_date"]
                )
                rows.extend(
                    (month, week_no, current, DAY_CODES[current.weekday()], task_id, user_id, points)
                    for task_id, user_id, points in daily_template(current)
                )
            current += timedelta(days=1)

        execute_values(cursor, """
            INSERT INTO calendar_assignments
                (month, week_no, work_date, day_of_week, task_id, user_id, assigned_points)
            VALUES %s
            ON CONFLICT (work_date, task_id, user_id) DO UPDATE SET
                month = EXCLUDED.month, week_no = EXCLUDED.week_no,
                day_of_week = EXCLUDED.day_of_week, assigned_points = EXCLUDED.assigned_points
        """, rows, page_size=1000)
        return {"upserted": len(rows), "removed": removed}


def ensure_month_schedule(month: str) -> list[dict[str, Any]]:
    weeks = month_weeks(month)
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM calendar_assignments WHERE month = %s", (month,))
        if cursor.fetchone()["total"]:
            return weeks
        for week in weeks:
            current = date.fromisoformat(week["start_date"])
            end = date.fromisoformat(week["end_date"])
            while current <= end:
                rows = [(month, week["week_no"], current, DAY_CODES[current.weekday()], task_id, user_id, points) for task_id, user_id, points in daily_template(current)]
                if rows:
                    cursor.executemany("""
                        INSERT INTO calendar_assignments (month, week_no, work_date, day_of_week, task_id, user_id, assigned_points)
                        VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (work_date, task_id, user_id) DO NOTHING
                    """, rows)
                current += timedelta(days=1)
    return weeks


def authenticate_user(name: str, pin: str) -> dict[str, Any] | None:
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id, name FROM users WHERE name = %s AND pin = %s", (name, pin))
        return cursor.fetchone()


def get_users() -> list[dict[str, Any]]:
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id, name FROM users ORDER BY id")
        return cursor.fetchall()


def get_tasks() -> list[dict[str, Any]]:
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id, code, name, points FROM tasks WHERE active = TRUE ORDER BY id")
        return cursor.fetchall()


def get_calendar(month: str) -> dict[str, Any]:
    return {"month": month, "weeks": ensure_month_schedule(month)}


def get_assignments_for_day(month: str, work_date: str) -> list[dict[str, Any]]:
    ensure_month_schedule(month)
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("""
            SELECT ca.id, ca.month, ca.week_no, ca.work_date::text, ca.day_of_week, ca.assigned_points,
                   u.id AS user_id, u.name AS user_name, t.id AS task_id, t.code AS task_code,
                   t.name AS task_name, t.points AS base_points
            FROM calendar_assignments ca JOIN users u ON u.id = ca.user_id JOIN tasks t ON t.id = ca.task_id
            WHERE ca.month = %s AND ca.work_date = %s::date ORDER BY u.id, t.id
        """, (month, work_date))
        return cursor.fetchall()


def report_for_week(month: str, week_no: int) -> dict[str, Any]:
    ensure_month_schedule(month)
    return report(month, "ca.week_no = %s", (week_no,), "week_no", week_no)


def report_for_month(month: str) -> dict[str, Any]:
    ensure_month_schedule(month)
    return report(month, "TRUE", (), "month", month)


def report_for_year(year: int) -> dict[str, Any]:
    if year < 2000 or year > 2100:
        raise ValueError("El año debe estar entre 2000 y 2100.")
    for month_number in range(1, 13):
        ensure_month_schedule(f"{year}-{month_number:02d}")
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("""
            SELECT u.id AS user_id, u.name AS user_name,
                   COALESCE(SUM(ca.assigned_points), 0) AS assigned_points,
                   COALESCE(SUM(CASE WHEN cr.completed THEN ca.assigned_points ELSE 0 END), 0) AS completed_points
            FROM users u LEFT JOIN calendar_assignments ca ON ca.user_id = u.id AND ca.month LIKE %s
            LEFT JOIN compliance_records cr ON cr.work_date = ca.work_date AND cr.task_id = ca.task_id AND cr.assigned_user_id = ca.user_id
            GROUP BY u.id, u.name ORDER BY u.id
        """, (f"{year}-%",))
        return {"year": year, "users": build_report_users(cursor.fetchall())}


def report(month: str, extra_filter: str, values: tuple[Any, ...], key: str, key_value: Any) -> dict[str, Any]:
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT u.id AS user_id, u.name AS user_name,
                   COALESCE(SUM(ca.assigned_points), 0) AS assigned_points,
                   COALESCE(SUM(CASE WHEN cr.completed THEN ca.assigned_points ELSE 0 END), 0) AS completed_points
            FROM users u LEFT JOIN calendar_assignments ca ON ca.user_id = u.id AND ca.month = %s AND {extra_filter}
            LEFT JOIN compliance_records cr ON cr.work_date = ca.work_date AND cr.task_id = ca.task_id AND cr.assigned_user_id = ca.user_id
            GROUP BY u.id, u.name ORDER BY u.id
        """, (month, *values))
        return {key: key_value, "users": build_report_users(cursor.fetchall())}


def build_report_users(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    users = []
    for row in rows:
        assigned = round(float(row["assigned_points"]), 2)
        completed = round(float(row["completed_points"]), 2)
        users.append({**row, "assigned_points": assigned, "completed_points": completed, "not_completed_points": round(assigned - completed, 2), "completion_pct": round(completed / assigned * 100, 2) if assigned else 0})
    return users


def get_user_dashboard(month: str, user_id: int, week_no: int) -> dict[str, Any]:
    weekly = report_for_week(month, week_no)["users"]
    current = next(item for item in weekly if item["user_id"] == user_id)
    peer = next(item for item in weekly if item["user_id"] != user_id)
    return {"month": month, "week_no": week_no, "current_user": current, "peer": peer}


def add_evaluation(work_date: str, task_id: int, assigned_user_id: int, evaluator_user_id: int, completed: bool) -> dict[str, Any]:
    if assigned_user_id == evaluator_user_id:
        raise ValueError("Una persona no puede evaluarse a sí misma.")
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT assigned_points FROM calendar_assignments WHERE work_date = %s::date AND task_id = %s AND user_id = %s", (work_date, task_id, assigned_user_id))
        assignment = cursor.fetchone()
        if not assignment:
            raise ValueError("La tarea no existe para ese responsable y fecha.")
        cursor.execute("""
            INSERT INTO compliance_records (work_date, task_id, assigned_user_id, evaluator_user_id, assigned_points, completed)
            VALUES (%s::date, %s, %s, %s, %s, %s)
            ON CONFLICT (work_date, task_id, assigned_user_id, evaluator_user_id)
            DO UPDATE SET completed = EXCLUDED.completed, assigned_points = EXCLUDED.assigned_points
            RETURNING id, work_date::text, task_id, assigned_user_id, evaluator_user_id, assigned_points, completed
        """, (work_date, task_id, assigned_user_id, evaluator_user_id, assignment["assigned_points"], completed))
        return cursor.fetchone()


def get_daily_validations(work_date: str) -> list[dict[str, Any]]:
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id, work_date::text, task_id, assigned_user_id, evaluator_user_id, assigned_points, completed FROM compliance_records WHERE work_date = %s::date", (work_date,))
        return cursor.fetchall()
