import os
import sys
import json
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app

def test_modi_context():
    client = TestClient(app)
    
    # Locate candidate image
    modi_img_path = None
    upload_dir = os.path.join(os.path.dirname(__file__), "..", "data", "uploads")
    if os.path.exists(upload_dir):
        for fname in os.listdir(upload_dir):
            if "modi" in fname.lower() and fname.endswith((".jpg", ".jpeg", ".png")):
                modi_img_path = os.path.join(upload_dir, fname)
                break
    
    if not modi_img_path or not os.path.exists(modi_img_path):
        sample_path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_clean.jpg")
        if os.path.exists(sample_path):
            modi_img_path = sample_path
        else:
            print("[SKIP] No suitable test image found for test_modi_context.")
            return
    
    print("Uploading Modi Guitar image to /api/v1/investigate...")
    with open(modi_img_path, "rb") as f:
        resp = client.post("/api/v1/investigate", files={"file": ("modi_rockstar.jpg", f, "image/jpeg")})
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]
    print(f"Job launched: {job_id}")

    # Wait for execution
    time.sleep(3.0)

    # Fetch dossier
    r_resp = client.get(f"/api/v1/report/{job_id}")
    assert r_resp.status_code == 200
    dossier = r_resp.json()

    print("\n" + "=" * 70)
    print("           MODI GUITAR IMAGE — FORENSIC VERDICT & OSINT")
    print("=" * 70)
    print("Verdict Type:", dossier["verdict"]["verdict_type"])
    print("Authenticity Score:", dossier["verdict"]["authenticity_score"], "%")
    print("Tamper / Synthetic Risk:", dossier["verdict"]["tamper_score"], "%")
    print("Summary:", dossier["verdict"]["summary"])
    print("\nKey Indicators:")
    for k in dossier["verdict"]["key_indicators"]:
        print("  -", k)
    print("\nOSINT Module Findings:")
    print(json.dumps(dossier.get("context_osint"), indent=2))
    print("=" * 70)

if __name__ == "__main__":
    test_modi_context()
