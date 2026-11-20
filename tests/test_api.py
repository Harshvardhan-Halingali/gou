import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app

def test_api_routes():
    client = TestClient(app)

    print("1. Testing GET / (Dashboard UI)...")
    resp = client.get("/")
    assert resp.status_code == 200
    assert "IMAGE" in resp.text and "TRACE" in resp.text
    print("   [OK] Dashboard served successfully.")

    print("2. Testing GET /api/v1/connectors/status ...")
    resp = client.get("/api/v1/connectors/status")
    assert resp.status_code == 200
    conn_data = resp.json()
    assert "connectors" in conn_data
    print(f"   [OK] Connectors status: {len(conn_data['connectors'])} platforms reported.")

    print("3. Testing POST /api/v1/investigate with sample image...")
    sample_file_path = "tests/fixtures/sample_clean.jpg"
    if not os.path.exists(sample_file_path):
        sample_file_path = "data/uploads/sample_clean.jpg"
    with open(sample_file_path, "rb") as f:
        resp = client.post(
            "/api/v1/investigate",
            files={"file": ("sample_clean.jpg", f, "image/jpeg")}
        )
    assert resp.status_code == 202
    job_info = resp.json()
    job_id = job_info["job_id"]
    print(f"   [OK] Investigation job created: {job_id}")

    print("4. Testing GET /api/v1/report/{job_id} ...")
    # Wait briefly for background tasks to finish
    import time
    time.sleep(2.0)
    resp = client.get(f"/api/v1/report/{job_id}")
    assert resp.status_code == 200
    dossier = resp.json()
    assert "verdict" in dossier
    assert "fingerprints" in dossier
    print(f"   [OK] Dossier retrieved! Verdict: {dossier['verdict']['verdict_type']}")
    print(f"   [OK] Fingerprint SHA-256: {dossier['fingerprints'].get('sha256')}")

    print("\n>>> ALL API INTEGRATION TESTS PASSED! <<<")

if __name__ == "__main__":
    test_api_routes()
