import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect("C://Users//Admin//Desktop//venv//BFCAgent//schedule.db")

    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedule_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT,
            subject TEXT,
            meeting_time_ist TEXT,
            meeting_time_utc TEXT,
            call_type TEXT,             -- ✅ ADD THIS
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def client_exists_in_log(client_name: str, call_type: str) -> bool:
    conn = sqlite3.connect("C://Users//Admin//Desktop//venv//BFCAgent//schedule.db")
    cursor = conn.cursor()
    query = """
        SELECT 1 FROM schedule_log
        WHERE client_name = ? AND call_type = ?
        LIMIT 1
    """
    cursor.execute(query, (client_name, call_type))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def log_meeting(client_name: str, subject: str, meeting_time_ist: str, meeting_time_utc: str, call_type: str):
    
    conn = sqlite3.connect("C://Users//Admin//Desktop//venv//BFCAgent//schedule.db")  # <-- your actual path

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO schedule_log (client_name, subject, meeting_time_ist, meeting_time_utc, call_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        client_name,
        subject,
        meeting_time_ist,
        meeting_time_utc,
        call_type,
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()


def query_meetings(filter_text: str = ""):
    conn = sqlite3.connect("C://Users//Admin//Desktop//venv//BFCAgent//schedule.db")  # <-- your actual path

    cursor = conn.cursor()

    base_query = "SELECT client_name, subject, meeting_time_ist, call_type FROM schedule_log"
    params = []

    if filter_text:
        base_query += " WHERE client_name LIKE ? OR subject LIKE ? OR call_type LIKE ?"
        params = [f"%{filter_text}%"] * 3

    base_query += " ORDER BY meeting_time_ist ASC"

    cursor.execute(base_query, params)
    results = cursor.fetchall()
    conn.close()
    return results

def query_meetings_advanced(client=None, call_type="any", date=None):
    conn = sqlite3.connect("C://Users//Admin//Desktop//venv//BFCAgent//schedule.db")  # <-- your actual path

    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT * FROM schedule_log WHERE 1=1"
    params = []

    if client:
        query += " AND client_name LIKE ?"
        params.append(f"%{client}%")

    if call_type and call_type.lower() != "any":
        query += " AND call_type = ?"
        params.append(call_type.lower())

    if date:
        query += " AND meeting_time_ist LIKE ?"
        params.append(f"{date}%")

    query += " ORDER BY meeting_time_ist"

    print("🛠️ QUERY:", query)
    print("🧾 PARAMS:", params)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def delete_meeting(client_name: str, call_type: str = "any", date: str = None):
    conn = sqlite3.connect("C://Users//Admin//Desktop//venv//BFCAgent//schedule.db")
    cursor = conn.cursor()

    query = "DELETE FROM schedule_log WHERE client_name LIKE ?"
    params = [f"%{client_name}%"]

    if call_type.lower() != "any":
        query += " AND call_type = ?"
        params.append(call_type)

    if date:
        query += " AND meeting_time_ist LIKE ?"
        params.append(f"{date}%")

    cursor.execute(query, params)
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted
