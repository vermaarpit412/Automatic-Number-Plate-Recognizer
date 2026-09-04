"""
Clear database and reset for real camera captures only.
"""
import os
import sqlite3
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from database.db import create_table

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "database", "database.db")

print("Clearing database of all data...")

if os.path.exists(DB_NAME):
    os.remove(DB_NAME)
    print("Old database deleted")

create_table()

try:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vehicle_logs")
    conn.commit()
    conn.close()
    print("All records cleared")
except sqlite3.OperationalError:
    print("No existing records to clear")

print("\nNow only real camera captures will be stored.")
print("Run: python camera/single_cam.py")
print("Open: http://localhost:5000")
