import os
import sys
import json
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.main import app

def run_tests():
    client = TestClient(app)

    print("======================================================================")
    print("      VIDEO DEEPFAKE DETECTION TEST SUITE (DEBUG THRICE VERIFICATION)")
    print("======================================================================")

    # ------------------------------------------------------------------
    # TEST 1: Deepfake Video from HongguLiu/Deepfake-Detection Repository
    # ------------------------------------------------------------------
    print("\n[TEST 1] Testing HongguLiu Sample Deepfake Video (003_000.mp4)...")
    video_path = "tests/fixtures/video/sample_deepfake_003_000.mp4"
    if not os.path.exists(video_path):
        video_path = "data/uploads/video/sample_deepfake_003_000.mp4"
    assert os.path.exists(video_path), f"Video missing: {video_path}"

    with open(video_path, "rb") as f:
        resp1 = client.post("/api/v1/detect/video", files={"file": ("deepfake_sample.mp4", f, "video/mp4")})

    print("HTTP Status Code:", resp1.status_code)
    assert resp1.status_code == 200, f"Error: {resp1.text}"
    data1 = resp1.json()

    print("Prediction:", data1["prediction"])
    print("Deepfake %:", f"{data1['fake_percentage']}%")
    print("Authentic %:", f"{data1['real_percentage']}%")
    print("Model:", data1["model"])
    print("Frames Analyzed:", data1["frames_analyzed"])
    print("Faces Detected:", data1["faces_detected_count"])
    print("Summary:", data1["summary"])

    assert data1["success"] is True
    assert data1["prediction"] == "fake"
    assert data1["fake_percentage"] >= 90.0, f"Expected fake_percentage >= 90%, got {data1['fake_percentage']}"
    assert round(data1["fake_percentage"] + data1["real_percentage"], 1) == 100.0
    assert len(data1["frame_predictions"]) > 0
    print(">>> TEST 1 PASSED: Successfully detected FaceForensics++ deepfake with >90% confidence.")

    # ------------------------------------------------------------------
    # TEST 2: Short Route & Format Verification (/api/detect/video)
    # ------------------------------------------------------------------
    print("\n[TEST 2] Testing Short Path /api/detect/video & Percentage Output Format...")
    sim_video_path = "tests/fixtures/video/test_real_sim_video.mp4"
    if not os.path.exists(sim_video_path):
        sim_video_path = "data/uploads/video/test_real_sim_video.mp4"
    assert os.path.exists(sim_video_path), f"Video missing: {sim_video_path}"
    with open(sim_video_path, "rb") as f:
        resp2 = client.post("/api/detect/video", files={"file": ("sim_video.mp4", f, "video/mp4")})

    print("HTTP Status Code:", resp2.status_code)
    assert resp2.status_code == 200, f"Error: {resp2.text}"
    data2 = resp2.json()

    print("Prediction:", data2["prediction"])
    print("Deepfake %:", f"{data2['fake_percentage']}%")
    print("Authentic %:", f"{data2['real_percentage']}%")
    assert "fake_percentage" in data2 and "real_percentage" in data2
    assert "frame_predictions" in data2
    print(">>> TEST 2 PASSED: Percentage format returned and short endpoint functional.")

    # ------------------------------------------------------------------
    # TEST 3: Validation, Bad Inputs & Corrupted Stream Handling
    # ------------------------------------------------------------------
    print("\n[TEST 3] Testing Bad Input Rejection & Stream Validation...")
    # Empty 0-byte file
    r_empty = client.post("/api/v1/detect/video", files={"file": ("empty.mp4", b"", "video/mp4")})
    print("Empty file response code:", r_empty.status_code)
    assert r_empty.status_code == 400
    assert r_empty.json()["success"] is False
    print("Empty file error message:", r_empty.json()["error"])

    # Corrupt fake video
    r_corrupt = client.post("/api/v1/detect/video", files={"file": ("fake.mp4", b"not-a-video-container", "video/mp4")})
    print("Corrupt file response code:", r_corrupt.status_code)
    assert r_corrupt.status_code == 400
    assert r_corrupt.json()["success"] is False
    print("Corrupt file error message:", r_corrupt.json()["error"])
    print(">>> TEST 3 PASSED: Robust error rejection on empty/corrupted videos.")

    # ------------------------------------------------------------------
    # UI Web Interface Verification
    # ------------------------------------------------------------------
    print("\n[UI VERIFICATION] Checking Web Dashboard HTML & JavaScript...")
    r_ui = client.get("/")
    assert r_ui.status_code == 200
    html = r_ui.text
    assert "modeVideoBtn" in html
    assert "videoWorkspace" in html
    assert "videoDropzone" in html
    assert "videoScanOverlay" in html
    assert "videoFakeBarFill" in html
    assert "videoRealBarFill" in html

    r_js = client.get("/static/js/app.js")
    assert r_js.status_code == 200
    js = r_js.text
    assert "startVideoDetection" in js
    assert "renderVideoResults" in js
    assert "videoScanOverlay" in js
    print(">>> UI VERIFICATION PASSED: Video mode buttons, scan overlay animation, and handlers verified.")

    print("\n" + "=" * 70)
    print("   ALL 3 VIDEO DETECTION TESTS PASSED WITH ZERO REGRESSIONS!")
    print("======================================================================")

if __name__ == "__main__":
    run_tests()
