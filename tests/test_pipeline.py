import os
import sys
import numpy as np
from PIL import Image, ImageDraw

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.database.connection import init_db
from app.modules.hashing_engine import HashingEngine
from app.modules.metadata_engine import MetadataEngine
from app.modules.manipulation_ela import ManipulationELAModule
from app.modules.sift_engine import SIFTEngine
from app.modules.ai_detector import AIDetector
from app.core.security import validate_image_file

def create_sample_images():
    """Generates synthetic test images for local verification."""
    os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
    os.makedirs(settings.CORPUS_DIR, exist_ok=True)

    # 1. Base clean image
    clean_path = str(settings.UPLOADS_DIR / "sample_clean.jpg")
    img = Image.new("RGB", (400, 400), color=(73, 109, 137))
    d = ImageDraw.Draw(img)
    d.rectangle([(50, 50), (200, 200)], fill=(255, 255, 0), outline=(0, 0, 0))
    d.ellipse([(220, 220), (350, 350)], fill=(255, 0, 100), outline=(255, 255, 255))
    img.save(clean_path, "JPEG", quality=95)

    # 2. Tampered image with spliced block
    tampered_path = str(settings.UPLOADS_DIR / "sample_tampered.jpg")
    img_tampered = img.copy()
    d_t = ImageDraw.Draw(img_tampered)
    # Add spliced region with high contrast noise
    noise_block = Image.fromarray(np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8))
    img_tampered.paste(noise_block, (150, 150))
    img_tampered.save(tampered_path, "JPEG", quality=80)

    # 3. Reference corpus item
    ref_path = str(settings.CORPUS_DIR / "verified_ref_1.jpg")
    img.save(ref_path, "JPEG", quality=95)

    return clean_path, tampered_path

def test_pipeline():
    print(">>> 1. Initializing Database...")
    init_db()
    assert os.path.exists(settings.DB_PATH), "Database file was not created!"
    print("     [OK] Database initialized.")

    print(">>> 2. Creating Test Images...")
    clean_img, tampered_img = create_sample_images()
    is_valid, mime, err = validate_image_file(clean_img)
    assert is_valid, f"Validation failed: {err}"
    print(f"     [OK] Image validation passed: MIME={mime}")

    print(">>> 3. Testing Hashing Suite (7 algorithms)...")
    hasher = HashingEngine()
    res_h = hasher.analyze(clean_img, {"job_id": "test_job_1"})
    print("res_h:", res_h)
    fps = res_h.result.get("fingerprints", {})
    assert "sha256" in fps and len(fps["sha256"]) == 64
    assert "phash" in fps
    assert "dhash" in fps
    assert "ahash" in fps
    assert "whash" in fps
    assert "colorhash" in fps
    assert "crop_resistant_hash" in fps
    print(f"     [OK] SHA-256: {fps['sha256'][:16]}...")
    print(f"     [OK] pHash: {fps['phash']} | dHash: {fps['dhash']} | wHash: {fps['whash']}")

    print(">>> 4. Testing Metadata Extraction & C2PA Inspection...")
    meta = MetadataEngine()
    res_m = meta.analyze(clean_img, {"job_id": "test_job_1"})
    assert res_m.status == "COMPLETED"
    print(f"     [OK] Metadata tags extracted: {res_m.result.get('exif_tags_count', 0)}")

    print(">>> 5. Testing Error Level Analysis (ELA) & Noise Variance...")
    ela_mod = ManipulationELAModule()
    res_e = ela_mod.analyze(tampered_img, {"job_id": "test_job_tampered"})
    assert res_e.status == "COMPLETED"
    ela_data = res_e.result.get("ela", {})
    assert "mean_error" in ela_data
    print(f"     [OK] ELA Mean Error: {ela_data.get('mean_error')} (Anomaly: {ela_data.get('ela_anomaly_detected')})")

    print(">>> 6. Testing OpenCV SIFT/ORB Keypoint Matching against Corpus...")
    sift_mod = SIFTEngine()
    res_s = sift_mod.analyze(clean_img, {"job_id": "test_job_1"})
    assert res_s.status == "COMPLETED"
    print(f"     [OK] Keypoints: {res_s.result.get('query_keypoints_extracted')}, Matches found: {len(res_s.result.get('matches', []))}")

    print(">>> 7. Testing AI Detector...")
    ai_mod = AIDetector()
    res_ai = ai_mod.analyze(clean_img, {"job_id": "test_job_1"})
    assert res_ai.status == "COMPLETED"
    print(f"     [OK] AI Detection completed. Backend: {res_ai.result.get('model_backend')}")

    print("\n==================================================")
    print(" ALL FORENSIC ENGINE VERIFICATION CHECKS PASSED! ")
    print("==================================================")

if __name__ == "__main__":
    test_pipeline()
