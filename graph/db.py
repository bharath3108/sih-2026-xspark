import os
import json
import sqlite3

DB_URL = os.getenv("DATABASE_URL", "sqlite:///sih_local.db")

def fetch_canonical_events_from_db(start_time: str, end_time: str) -> list[dict]:
    """
    Fetches canonical events from the shared database within the specified time window.
    """
    # Local SQLite fallback for demo/offline testing
    if "sqlite" in DB_URL:
        db_path = DB_URL.replace("sqlite:///", "")
        if not os.path.exists(db_path):
            return []
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Ensures table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS canonical_events (
                event_id TEXT PRIMARY KEY,
                author_id_hash TEXT,
                parent_author_id_hash TEXT,
                reply_to_id TEXT,
                parent_event_id TEXT,
                timestamp_utc TEXT,
                payload JSON
            )
        """)
        
        query = "SELECT payload FROM canonical_events WHERE timestamp_utc BETWEEN ? AND ?"
        cursor.execute(query, (start_time, end_time))
        rows = cursor.fetchall()
        conn.close()

        return [json.loads(row[0]) if isinstance(row[0], str) else row[0] for row in rows]
    
    # PostgreSQL production connection
    else:
        try:
            import psycopg2
            conn = psycopg2.connect(DB_URL)
            cursor = conn.cursor()
            query = """
                SELECT payload FROM canonical_events 
                WHERE timestamp_utc >= %s AND timestamp_utc <= %s
            """
            cursor.execute(query, (start_time, end_time))
            rows = cursor.fetchall()
            conn.close()
            return [row[0] for row in rows]
        except Exception as e:
            print(f"[Graph DB Warning] Could not connect to PostgreSQL: {e}")
            return []