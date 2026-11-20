import sqlite3
import os
from pathlib import Path
from app.config import settings

def get_db_connection() -> sqlite3.Connection:
    """Returns an active SQLite connection configured with WAL and foreign keys."""
    conn = sqlite3.connect(str(settings.DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Initializes database tables and indexes."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS analysis_jobs (
        id TEXT PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL,
        source_filename TEXT NOT NULL,
        file_path TEXT NOT NULL,
        mime_type TEXT NOT NULL,
        file_size_bytes INTEGER NOT NULL,
        total_execution_time_ms REAL DEFAULT 0.0
    );

    CREATE TABLE IF NOT EXISTS image_hashes (
        job_id TEXT PRIMARY KEY,
        sha256 TEXT NOT NULL,
        phash TEXT NOT NULL,
        dhash TEXT NOT NULL,
        ahash TEXT NOT NULL,
        whash TEXT NOT NULL,
        colorhash TEXT NOT NULL,
        crop_resistant_hash TEXT,
        FOREIGN KEY (job_id) REFERENCES analysis_jobs(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_hashes_sha256 ON image_hashes(sha256);
    CREATE INDEX IF NOT EXISTS idx_hashes_phash ON image_hashes(phash);

    CREATE TABLE IF NOT EXISTS indexed_images (
        id TEXT PRIMARY KEY,
        source_platform TEXT NOT NULL,
        external_media_id TEXT,
        source_url TEXT,
        account_identifier TEXT,
        publication_timestamp TIMESTAMP,
        file_path TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        phash TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_indexed_sha256 ON indexed_images(sha256);
    CREATE INDEX IF NOT EXISTS idx_indexed_phash ON indexed_images(phash);

    CREATE TABLE IF NOT EXISTS evidence_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL,
        module_name TEXT NOT NULL,
        status TEXT NOT NULL,
        evidence_found BOOLEAN NOT NULL DEFAULT 0,
        confidence_score REAL,
        raw_payload_json TEXT NOT NULL,
        execution_time_ms REAL NOT NULL,
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES analysis_jobs(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_evidence_job ON evidence_records(job_id);

    CREATE TABLE IF NOT EXISTS social_media_connections (
        platform TEXT PRIMARY KEY,
        is_configured BOOLEAN NOT NULL DEFAULT 0,
        account_info_json TEXT,
        last_sync_timestamp TIMESTAMP,
        sync_status TEXT
    );
    """)
    conn.commit()
    conn.close()
