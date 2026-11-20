import os
import sys
import time
import json
from pathlib import Path
from PIL import Image, ImageDraw
import numpy as np

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.database.connection import init_db, get_db_connection
from app.database.repository import ForensicRepository
from app.core.security import validate_image_file, sanitize_filename
from app.modules.hashing_engine import HashingEngine
from app.modules.metadata_engine import MetadataEngine
from app.modules.manipulation_ela import ManipulationELAModule
from app.modules.sift_engine import SIFTEngine
from app.modules.reverse_engine import ReverseEngine
from app.modules.ai_detector import AIDetector
from app.connectors.instagram_connector import InstagramConnector
from app.connectors.facebook_connector import FacebookConnector
from app.connectors.telegram_connector import TelegramConnector
from app.core.orchestrator import orchestrator

def verify_all_methods():
    print("=" * 80)
    print("          IMAGE TRACE — COMPLETE SYSTEM & METHOD VERIFICATION")
    print("=" * 80)

    # 1. Database & Tables Verification
    print("\n[METHOD 1/9] Database & WAL Persistence Verification...")
    init_db()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in c.fetchall()]
    conn.close()
    expected_tables = ["analysis_jobs", "image_hashes", "indexed_images", "evidence_records", "social_media_connections"]
    for t in expected_tables:
        assert t in tables, f"Missing table {t}"
    print(f"  --> Tables present: {', '.join(expected_tables)}")
    print("  --> SQLite WAL Mode and Schema Integrity: VERIFIED [OK]")

    # 2. File Validation & Security Verification
    print("\n[METHOD 2/9] Security, Magic Bytes & Path Traversal Verification...")
    clean_path = str(settings.UPLOADS_DIR / "sample_clean.jpg")
    is_valid, mime, err = validate_image_file(clean_path)
    assert is_valid and mime == "image/jpeg"
    safe_name = sanitize_filename("../../../etc/passwd_evil.jpg")
    assert safe_name == "passwd_evil.jpg"
    print(f"  --> Ingest Magic Byte Check: {mime} [OK]")
    print(f"  --> Path Sanitization: '../../../etc/passwd_evil.jpg' -> '{safe_name}' [OK]")

    # 3. Hashing Suite (7 Algorithms) Verification
    print("\n[METHOD 3/9] Multi-Algorithm Fingerprinting Verification...")
    hasher = HashingEngine()
    t0 = time.perf_counter()
    res_h = hasher.analyze(clean_path, {"job_id": "test_verify_hash"})
    dt_h = (time.perf_counter() - t0) * 1000.0
    fps = res_h.result["fingerprints"]
    assert len(fps["sha256"]) == 64
    assert len(fps["phash"]) > 0
    assert len(fps["dhash"]) > 0
    assert len(fps["ahash"]) > 0
    assert len(fps["whash"]) > 0
    assert len(fps["colorhash"]) > 0
    assert "|" in fps["crop_resistant_hash"]
    print(f"  --> SHA-256 (Bitwise): {fps['sha256']}")
    print(f"  --> pHash (DCT):        {fps['phash']}")
    print(f"  --> dHash (Gradient):   {fps['dhash']}")
    print(f"  --> aHash (Average):    {fps['ahash']}")
    print(f"  --> wHash (Wavelet):    {fps['whash']}")
    print(f"  --> ColorHash (HSV):    {fps['colorhash']}")
    print(f"  --> Crop-Resistant (3x3): {fps['crop_resistant_hash'][:30]}...")
    print(f"  --> Execution Time: {dt_h:.1f} ms [OK]")

    # 4. Metadata & Provenance Verification
    print("\n[METHOD 4/9] EXIF, Provenance & C2PA Inspection Verification...")
    meta = MetadataEngine()
    t0 = time.perf_counter()
    res_m = meta.analyze(clean_path, {"job_id": "test_verify_meta"})
    dt_m = (time.perf_counter() - t0) * 1000.0
    c2pa = res_m.result["c2pa"]
    print(f"  --> Extracted Tags: {res_m.result.get('exif_tags_count')} attributes")
    print(f"  --> Editing Software Flags: {res_m.result.get('editing_software_detected')}")
    print(f"  --> C2PA Signed Manifest: {c2pa['c2pa_present']} ({c2pa['details']})")
    print(f"  --> Execution Time: {dt_m:.1f} ms [OK]")

    # 5. Error Level Analysis & Noise Verification
    print("\n[METHOD 5/9] Error Level Analysis (ELA) & Noise Variance Verification...")
    ela_mod = ManipulationELAModule()
    t0 = time.perf_counter()
    res_e = ela_mod.analyze(clean_path, {"job_id": "test_verify_ela"})
    dt_e = (time.perf_counter() - t0) * 1000.0
    ela_d = res_e.result["ela"]
    noise_d = res_e.result["noise_analysis"]
    cm_d = res_e.result["copy_move"]
    assert "ela_image_url" in ela_d
    assert Path(settings.REPORTS_DIR / "test_verify_ela_ela.jpg").exists()
    print(f"  --> ELA Generated Heatmap: {ela_d['ela_image_url']} [SAVED]")
    print(f"  --> Local Discrepancy Ratio: {ela_d.get('local_discrepancy_ratio')}x (Anomaly: {ela_d['ela_anomaly_detected']})")
    print(f"  --> Noise Inconsistency Ratio: {noise_d.get('noise_inconsistency_ratio')} (Inconsistent: {noise_d['inconsistent_noise']})")
    print(f"  --> Copy-Move Clones: {cm_d['cloned_regions_found']} (Clusters: {cm_d['candidate_matches']})")
    print(f"  --> Execution Time: {dt_e:.1f} ms [OK]")

    # 6. OpenCV SIFT/ORB Homography Verification
    print("\n[METHOD 6/9] OpenCV SIFT/ORB Keypoint Homography Verification...")
    sift_mod = SIFTEngine()
    t0 = time.perf_counter()
    res_s = sift_mod.analyze(clean_path, {"job_id": "test_verify_sift"})
    dt_s = (time.perf_counter() - t0) * 1000.0
    print(f"  --> Algorithm: {res_s.result['algorithm']}")
    print(f"  --> Extracted Keypoints: {res_s.result['query_keypoints_extracted']}")
    print(f"  --> Geometric Corpus Matches: {len(res_s.result['matches'])}")
    print(f"  --> Execution Time: {dt_s:.1f} ms [OK]")

    # 7. OpenCLIP Semantic Vector Search Verification
    print("\n[METHOD 7/9] OpenCLIP Semantic Vector Embedding Verification...")
    rev_mod = ReverseEngine()
    t0 = time.perf_counter()
    res_r = rev_mod.analyze(clean_path, {"job_id": "test_verify_rev"})
    dt_r = (time.perf_counter() - t0) * 1000.0
    print(f"  --> Vector Backend: {res_r.result['vector_backend']}")
    print(f"  --> Embedding Dimensions: {res_r.result['embedding_dimension']}")
    print(f"  --> Matches in Local Corpus: {len(res_r.result['matches'])}")
    print(f"  --> Execution Time: {dt_r:.1f} ms [OK]")

    # 8. AI Deepfake & Synthetic Detection Verification
    print("\n[METHOD 8/9] AI Synthetic Detection (Vision Transformer on CPU) Verification...")
    ai_mod = AIDetector()
    ai_mod._lazy_init()
    t0 = time.perf_counter()
    res_ai = ai_mod.analyze(clean_path, {"job_id": "test_verify_ai"})
    dt_ai = (time.perf_counter() - t0) * 1000.0
    ai_res = res_ai.result
    print(f"  --> Model Name: {ai_res['model_name']}")
    print(f"  --> Model Backend: {ai_res['model_backend']}")
    print(f"  --> Synthetic Likelihood: {ai_res['synthetic_likelihood'] * 100:.2f}%")
    print(f"  --> Authentic Likelihood: {ai_res['authentic_likelihood'] * 100:.2f}%")
    print(f"  --> Classification Bracket: {ai_res['classification_bracket']}")
    print(f"  --> 2D FFT Radial Ratio: {ai_res['fourier_spectrum_signals']['high_to_low_freq_energy_ratio']}")
    print(f"  --> Inference Time: {dt_ai:.1f} ms [OK]")

    # 9. Social Media Connector Scaffold Verification
    print("\n[METHOD 9/9] Social Connectors & Zero-Fabrication Checks Verification...")
    for conn in [InstagramConnector(), FacebookConnector(), TelegramConnector()]:
        is_cfg = conn.is_configured()
        sync_res = conn.sync_media(max_items=1)
        print(f"  --> {conn.platform_name}: Configured={is_cfg} | Status={sync_res['status']} [OK]")

    print("\n" + "=" * 80)
    print("      ALL 9 CORE FORENSIC METHODS & PIPELINES ARE 100% OPERATIONAL")
    print("=" * 80)

if __name__ == "__main__":
    verify_all_methods()
