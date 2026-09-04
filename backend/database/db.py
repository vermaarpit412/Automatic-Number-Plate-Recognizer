import sqlite3
import os
from utils.helpers import is_similar

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "database.db")


def create_table():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vehicle_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plate_number TEXT,
        entry_time TEXT,
        exit_time TEXT,
        duration TEXT,
        entry_image TEXT,
        exit_image TEXT
    )
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_vehicle_logs_plate
    ON vehicle_logs(plate_number)
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_vehicle_logs_entry_time
    ON vehicle_logs(entry_time)
    """)

    conn.commit()
    conn.close()


def insert_entry(plate, entry_time, entry_image):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO vehicle_logs (plate_number, entry_time, entry_image)
    VALUES (?, ?, ?)
    """, (plate, entry_time, os.path.basename(entry_image)))

    conn.commit()
    conn.close()


def get_open_records():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM vehicle_logs
    WHERE exit_time IS NULL
    """)

    records = cursor.fetchall()
    conn.close()

    return records


def find_matching_record(detected_plate):
    records = get_open_records()

    for record in records:
        db_plate = record[1]

        if is_similar(detected_plate, db_plate):
            return record

    return None


def update_exit(record_id, exit_time, duration, exit_image):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE vehicle_logs
    SET exit_time = ?, duration = ?, exit_image = ?
    WHERE id = ?
    """, (exit_time, duration, os.path.basename(exit_image), record_id))

    conn.commit()
    conn.close()


def get_all_records():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM vehicle_logs
    ORDER BY entry_time DESC
    """)

    records = cursor.fetchall()
    conn.close()

    return records


def search_records(plate):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM vehicle_logs
    WHERE plate_number LIKE ?
    ORDER BY entry_time DESC
    """, ('%' + plate + '%',))

    records = cursor.fetchall()
    conn.close()

    return records


def get_dashboard_stats():
    records = get_all_records()
    total_entries = len(records)
    total_exits = len([record for record in records if record[3]])
    currently_inside = total_entries - total_exits
    unique_vehicles = len({record[1] for record in records})

    return {
        "total_entries": total_entries,
        "total_exits": total_exits,
        "currently_inside": currently_inside,
        "unique_vehicles": unique_vehicles,
    }
