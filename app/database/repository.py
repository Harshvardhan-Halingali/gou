import json
import sqlite3
from typing import Dict, Any, List, Optional
from app.database.connection import get_db_connection

class ForensicRepository:
    def __init__(self):
        self.conn = get_db_connection()

    def create_job(self, job_id: str, filename: str, file_path: str, mime_type: str, file_size: int):
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO analysis_jobs (id, status, source_filename, file_path, mime_type, file_size_bytes)
                VALUES (?, 'PROCESSING', ?, ?, ?, ?)
                """,
                (job_id, filename, file_path, mime_type, file_size)
            )

    def update_job_status(self, job_id: str, status: str, total_time_ms: float = 0.0):
        with self.conn:
            self.conn.execute(
                """
                UPDATE analysis_jobs 
                SET status = ?, total_execution_time_ms = ?
                WHERE id = ?
                """,
                (status, total_time_ms, job_id)
            )

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM analysis_jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def save_hashes(self, job_id: str, hashes: Dict[str, str]):
        if not job_id:
            return
        with self.conn:
            # Ensure job_id exists in analysis_jobs to satisfy foreign key constraint
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM analysis_jobs WHERE id = ?", (job_id,))
            if not cursor.fetchone():
                self.conn.execute(
                    """
                    INSERT INTO analysis_jobs (id, status, source_filename, file_path, mime_type, file_size_bytes)
                    VALUES (?, 'PROCESSING', 'autogen_test.jpg', 'temp', 'image/jpeg', 0)
                    """,
                    (job_id,)
                )

            self.conn.execute(
                """
                INSERT OR REPLACE INTO image_hashes 
                (job_id, sha256, phash, dhash, ahash, whash, colorhash, crop_resistant_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    hashes.get("sha256", ""),
                    hashes.get("phash", ""),
                    hashes.get("dhash", ""),
                    hashes.get("ahash", ""),
                    hashes.get("whash", ""),
                    hashes.get("colorhash", ""),
                    hashes.get("crop_resistant_hash", "")
                )
            )

    def find_matching_hashes(self, sha256_val: str, phash_val: str, max_hamming_dist: int = 10) -> List[Dict[str, Any]]:
        """Searches indexed reference images for exact SHA-256 or near-pHash matches."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM indexed_images")
        rows = cursor.fetchall()
        
        matches = []
        for r in rows:
            r_dict = dict(r)
            # Exact cryptographic match
            if r_dict["sha256"] == sha256_val:
                matches.append({
                    "id": r_dict["id"],
                    "source_platform": r_dict["source_platform"],
                    "source_url": r_dict.get("source_url"),
                    "external_media_id": r_dict.get("external_media_id"),
                    "file_path": r_dict["file_path"],
                    "match_type": "EXACT_SHA256",
                    "hamming_distance": 0,
                    "similarity": 1.0
                })
                continue
                
            # Perceptual hash hamming distance
            if r_dict["phash"] and phash_val:
                try:
                    # Calculate hexadecimal hamming distance
                    h1 = int(r_dict["phash"], 16)
                    h2 = int(phash_val, 16)
                    dist = bin(h1 ^ h2).count("1")
                    if dist <= max_hamming_dist:
                        similarity = max(0.0, 1.0 - (dist / 64.0))
                        matches.append({
                            "id": r_dict["id"],
                            "source_platform": r_dict["source_platform"],
                            "source_url": r_dict.get("source_url"),
                            "external_media_id": r_dict.get("external_media_id"),
                            "file_path": r_dict["file_path"],
                            "match_type": "NEAR_DUPLICATE_PHASH",
                            "hamming_distance": dist,
                            "similarity": round(similarity, 3)
                        })
                except Exception:
                    pass
        return matches

    def save_evidence(self, job_id: str, module_name: str, status: str, evidence_found: bool,
                      confidence: Optional[float], raw_payload: Dict[str, Any],
                      execution_time_ms: float, error_message: Optional[str] = None):
        if not job_id:
            return
        with self.conn:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM analysis_jobs WHERE id = ?", (job_id,))
            if not cursor.fetchone():
                self.conn.execute(
                    """
                    INSERT INTO analysis_jobs (id, status, source_filename, file_path, mime_type, file_size_bytes)
                    VALUES (?, 'PROCESSING', 'autogen_test.jpg', 'temp', 'image/jpeg', 0)
                    """,
                    (job_id,)
                )

            self.conn.execute(
                """
                INSERT INTO evidence_records 
                (job_id, module_name, status, evidence_found, confidence_score, raw_payload_json, execution_time_ms, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id, module_name, status, 1 if evidence_found else 0,
                    confidence, json.dumps(raw_payload), execution_time_ms, error_message
                )
            )

    def get_evidence_records(self, job_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM evidence_records WHERE job_id = ? ORDER BY id ASC", (job_id,))
        records = []
        for r in cursor.fetchall():
            d = dict(r)
            try:
                d["raw_payload"] = json.loads(d["raw_payload_json"])
            except Exception:
                d["raw_payload"] = {}
            records.append(d)
        return records

    def add_indexed_image(self, item_id: str, source_platform: str, file_path: str,
                          sha256: str, phash: str, source_url: Optional[str] = None,
                          external_media_id: Optional[str] = None,
                          account_identifier: Optional[str] = None):
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO indexed_images
                (id, source_platform, external_media_id, source_url, account_identifier, file_path, sha256, phash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (item_id, source_platform, external_media_id, source_url, account_identifier, file_path, sha256, phash)
            )

    def count_indexed_images(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM indexed_images")
        return cursor.fetchone()["count"]
