"""SQLite database for NHTSA Vehicle Safety data."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "nhtsa_safety.db"


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a database connection."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> None:
    """Create all tables."""
    _conn = conn or get_connection()
    _conn.executescript("""
        CREATE TABLE IF NOT EXISTS complaints (
            odi_number INTEGER PRIMARY KEY,
            manufacturer TEXT NOT NULL,
            make TEXT NOT NULL,
            model TEXT NOT NULL,
            model_year INTEGER NOT NULL,
            crash INTEGER DEFAULT 0,
            fire INTEGER DEFAULT 0,
            num_injuries INTEGER DEFAULT 0,
            num_deaths INTEGER DEFAULT 0,
            date_of_incident TEXT,
            date_complaint_filed TEXT,
            components TEXT,
            summary TEXT,
            vin_prefix TEXT,
            quality_score REAL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS recalls (
            campaign_number TEXT PRIMARY KEY,
            manufacturer TEXT NOT NULL,
            make TEXT NOT NULL,
            model TEXT NOT NULL,
            model_year INTEGER NOT NULL,
            report_received_date TEXT,
            component TEXT,
            summary TEXT,
            consequence TEXT,
            remedy TEXT,
            notes TEXT,
            num_potentially_affected INTEGER DEFAULT 0,
            park_it INTEGER DEFAULT 0,
            park_outside INTEGER DEFAULT 0,
            quality_score REAL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS investigations (
            investigation_number TEXT PRIMARY KEY,
            nhtsa_id TEXT,
            make TEXT,
            model TEXT,
            model_year_start INTEGER,
            model_year_end INTEGER,
            investigation_type TEXT,
            status TEXT,
            open_date TEXT,
            close_date TEXT,
            subject TEXT,
            description TEXT,
            num_complaints INTEGER DEFAULT 0,
            num_vehicles INTEGER DEFAULT 0,
            components TEXT,
            quality_score REAL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS cross_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            link_method TEXT,
            confidence REAL DEFAULT 1.0,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(source_type, source_id, target_type, target_id)
        );

        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            make TEXT NOT NULL,
            model TEXT NOT NULL,
            make_normalized TEXT NOT NULL,
            model_normalized TEXT NOT NULL,
            UNIQUE(make_normalized, model_normalized)
        );

        CREATE INDEX IF NOT EXISTS idx_complaints_make_model
            ON complaints(make, model, model_year);
        CREATE INDEX IF NOT EXISTS idx_complaints_components
            ON complaints(components);
        CREATE INDEX IF NOT EXISTS idx_complaints_date
            ON complaints(date_complaint_filed);
        CREATE INDEX IF NOT EXISTS idx_recalls_make_model
            ON recalls(make, model, model_year);
        CREATE INDEX IF NOT EXISTS idx_recalls_component
            ON recalls(component);
        CREATE INDEX IF NOT EXISTS idx_investigations_make_model
            ON investigations(make, model_year_start);
        CREATE INDEX IF NOT EXISTS idx_cross_links_source
            ON cross_links(source_type, source_id);
        CREATE INDEX IF NOT EXISTS idx_cross_links_target
            ON cross_links(target_type, target_id);
    """)
    _conn.commit()
    if conn is None:
        _conn.close()


def upsert_complaint(conn: sqlite3.Connection, rec: dict) -> int:
    """Insert or update a complaint record."""
    conn.execute("""
        INSERT INTO complaints (
            odi_number, manufacturer, make, model, model_year,
            crash, fire, num_injuries, num_deaths,
            date_of_incident, date_complaint_filed,
            components, summary, vin_prefix, quality_score
        ) VALUES (
            :odi_number, :manufacturer, :make, :model, :model_year,
            :crash, :fire, :num_injuries, :num_deaths,
            :date_of_incident, :date_complaint_filed,
            :components, :summary, :vin_prefix, :quality_score
        ) ON CONFLICT(odi_number) DO UPDATE SET
            manufacturer = CASE WHEN excluded.manufacturer != '' THEN excluded.manufacturer ELSE complaints.manufacturer END,
            components = CASE WHEN excluded.components != '' THEN excluded.components ELSE complaints.components END,
            summary = CASE WHEN excluded.summary != '' THEN excluded.summary ELSE complaints.summary END,
            quality_score = excluded.quality_score
    """, rec)
    return rec["odi_number"]


def upsert_recall(conn: sqlite3.Connection, rec: dict) -> str:
    """Insert or update a recall record."""
    conn.execute("""
        INSERT INTO recalls (
            campaign_number, manufacturer, make, model, model_year,
            report_received_date, component, summary, consequence,
            remedy, notes, num_potentially_affected,
            park_it, park_outside, quality_score
        ) VALUES (
            :campaign_number, :manufacturer, :make, :model, :model_year,
            :report_received_date, :component, :summary, :consequence,
            :remedy, :notes, :num_potentially_affected,
            :park_it, :park_outside, :quality_score
        ) ON CONFLICT(campaign_number) DO UPDATE SET
            summary = CASE WHEN excluded.summary != '' THEN excluded.summary ELSE recalls.summary END,
            consequence = CASE WHEN excluded.consequence != '' THEN excluded.consequence ELSE recalls.consequence END,
            remedy = CASE WHEN excluded.remedy != '' THEN excluded.remedy ELSE recalls.remedy END,
            num_potentially_affected = CASE WHEN excluded.num_potentially_affected > 0 THEN excluded.num_potentially_affected ELSE recalls.num_potentially_affected END,
            quality_score = excluded.quality_score
    """, rec)
    return rec["campaign_number"]


def upsert_investigation(conn: sqlite3.Connection, rec: dict) -> str:
    """Insert or update an investigation record."""
    conn.execute("""
        INSERT INTO investigations (
            investigation_number, nhtsa_id, make, model,
            model_year_start, model_year_end,
            investigation_type, status, open_date, close_date,
            subject, description, num_complaints, num_vehicles,
            components, quality_score
        ) VALUES (
            :investigation_number, :nhtsa_id, :make, :model,
            :model_year_start, :model_year_end,
            :investigation_type, :status, :open_date, :close_date,
            :subject, :description, :num_complaints, :num_vehicles,
            :components, :quality_score
        ) ON CONFLICT(investigation_number) DO UPDATE SET
            status = CASE WHEN excluded.status != '' THEN excluded.status ELSE investigations.status END,
            close_date = CASE WHEN excluded.close_date != '' THEN excluded.close_date ELSE investigations.close_date END,
            description = CASE WHEN excluded.description != '' THEN excluded.description ELSE investigations.description END,
            quality_score = excluded.quality_score
    """, rec)
    return rec["investigation_number"]


def insert_cross_link(conn: sqlite3.Connection, rec: dict) -> int | None:
    """Insert a cross-link between records."""
    try:
        cur = conn.execute("""
            INSERT INTO cross_links (source_type, source_id, target_type, target_id, link_method, confidence)
            VALUES (:source_type, :source_id, :target_type, :target_id, :link_method, :confidence)
        """, rec)
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def upsert_vehicle(conn: sqlite3.Connection, make: str, model: str,
                   make_norm: str, model_norm: str) -> int:
    """Insert or get a vehicle make/model pair."""
    row = conn.execute(
        "SELECT id FROM vehicles WHERE make_normalized = ? AND model_normalized = ?",
        (make_norm, model_norm),
    ).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO vehicles (make, model, make_normalized, model_normalized) VALUES (?, ?, ?, ?)",
        (make, model, make_norm, model_norm),
    )
    return cur.lastrowid


def get_stats(conn: sqlite3.Connection | None = None) -> dict:
    """Get database summary statistics."""
    _conn = conn or get_connection()

    complaint_count = _conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    recall_count = _conn.execute("SELECT COUNT(*) FROM recalls").fetchone()[0]
    investigation_count = _conn.execute("SELECT COUNT(*) FROM investigations").fetchone()[0]
    cross_link_count = _conn.execute("SELECT COUNT(*) FROM cross_links").fetchone()[0]
    vehicle_count = _conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]

    crash_count = _conn.execute("SELECT COUNT(*) FROM complaints WHERE crash = 1").fetchone()[0]
    fire_count = _conn.execute("SELECT COUNT(*) FROM complaints WHERE fire = 1").fetchone()[0]
    injury_total = _conn.execute("SELECT COALESCE(SUM(num_injuries), 0) FROM complaints").fetchone()[0]
    death_total = _conn.execute("SELECT COALESCE(SUM(num_deaths), 0) FROM complaints").fetchone()[0]

    avg_quality_c = _conn.execute("SELECT AVG(quality_score) FROM complaints WHERE quality_score > 0").fetchone()[0] or 0
    avg_quality_r = _conn.execute("SELECT AVG(quality_score) FROM recalls WHERE quality_score > 0").fetchone()[0] or 0
    avg_quality_i = _conn.execute("SELECT AVG(quality_score) FROM investigations WHERE quality_score > 0").fetchone()[0] or 0

    affected_total = _conn.execute("SELECT COALESCE(SUM(num_potentially_affected), 0) FROM recalls").fetchone()[0]

    # Date ranges
    complaint_dates = _conn.execute(
        "SELECT MIN(date_complaint_filed), MAX(date_complaint_filed) FROM complaints WHERE date_complaint_filed != ''"
    ).fetchone()
    recall_dates = _conn.execute(
        "SELECT MIN(report_received_date), MAX(report_received_date) FROM recalls WHERE report_received_date != ''"
    ).fetchone()

    # Top makes by complaints
    top_makes = _conn.execute("""
        SELECT make, COUNT(*) as cnt FROM complaints
        GROUP BY make ORDER BY cnt DESC LIMIT 10
    """).fetchall()

    # Top components
    top_components = _conn.execute("""
        SELECT components, COUNT(*) as cnt FROM complaints
        WHERE components != ''
        GROUP BY components ORDER BY cnt DESC LIMIT 10
    """).fetchall()

    result = {
        "complaint_count": complaint_count,
        "recall_count": recall_count,
        "investigation_count": investigation_count,
        "cross_link_count": cross_link_count,
        "vehicle_count": vehicle_count,
        "crash_count": crash_count,
        "fire_count": fire_count,
        "injury_total": injury_total,
        "death_total": death_total,
        "affected_total": affected_total,
        "avg_quality": {
            "complaints": round(avg_quality_c, 3),
            "recalls": round(avg_quality_r, 3),
            "investigations": round(avg_quality_i, 3),
        },
        "complaint_date_range": (complaint_dates[0], complaint_dates[1]) if complaint_dates else (None, None),
        "recall_date_range": (recall_dates[0], recall_dates[1]) if recall_dates else (None, None),
        "top_makes": [(r["make"], r["cnt"]) for r in top_makes],
        "top_components": [(r["components"], r["cnt"]) for r in top_components],
    }

    if conn is None:
        _conn.close()
    return result
