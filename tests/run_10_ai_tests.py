import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.modules.ai_detector import AIDetector
from app.core.orchestrator import orchestrator

TEST_FILES = [
    ("WhatsApp_Image_2026-11-19_at_3.22.33_PM.jpeg", "Natural Photograph A (Portrait / Indoor)"),
    ("WhatsApp_Image_2026-11-19_at_7.51.44_PM.jpeg", "Natural Photograph B (Everyday Capture)"),
    ("WhatsApp_Image_2026-11-19_at_9.20.30_AM.jpeg", "Natural Photograph C (Scene Capture)"),
    ("WhatsApp_Image_2026-11-19_at_7.53.10_PM.jpeg", "Synthetic Candidate A (AI Generation)"),
    ("WhatsApp_Image_2026-11-19_at_9.34.58_AM.jpeg", "Synthetic Candidate B (Diffusion Image)"),
    ("WhatsApp_Image_2026-11-19_at_9.37.21_AM.jpeg", "Synthetic Candidate C (Deepfake / Render)"),
    ("iron-man-the-most-powerful-hero-nx.jpg", "Digital Artwork / CGI Wallpaper 1"),
    ("always-be-the-most-iconic-iron-man-v8.jpg", "Digital Artwork / CGI Wallpaper 2"),
    ("sample_clean.jpg", "Synthetic Clean Geometric Graphic"),
    ("sample_tampered.jpg", "Composite Spliced Noise Test Target"),
]

def find_file(name: str) -> str:
    # First search directly in data/uploads/
    upload_dir = Path("data/uploads")
    for f in upload_dir.iterdir():
        if f.name.endswith(name) or name in f.name:
            return str(f)
    return ""

def run_tests():
    detector = AIDetector()
    detector._lazy_init()
    
    print("\n" + "=" * 95)
    print("                 IMAGE TRACE — 10 FORENSIC AI DETECTION BENCHMARKS")
    print("=" * 95)
    print(f"{'#':<3} | {'Image Subject':<34} | {'AI %':<8} | {'Authentic %':<12} | {'Bracket':<24}")
    print("-" * 95)

    results = []

    for idx, (filename, description) in enumerate(TEST_FILES, start=1):
        filepath = find_file(filename)
        if not filepath or not os.path.exists(filepath):
            print(f"{idx:<3} | {description[:34]:<34} | [FILE NOT FOUND]")
            continue

        res = detector.analyze(filepath, {"job_id": f"bench_{idx}"})
        r_data = res.result
        synth_pct = r_data.get("synthetic_likelihood", 0.0) * 100.0
        auth_pct = r_data.get("authentic_likelihood", 0.0) * 100.0
        bracket = r_data.get("classification_bracket", "UNKNOWN")
        fft_ratio = r_data.get("fourier_spectrum_signals", {}).get("high_to_low_freq_energy_ratio", 0.0)

        results.append({
            "index": idx,
            "filename": filename,
            "description": description,
            "synthetic_likelihood_pct": round(synth_pct, 2),
            "authentic_likelihood_pct": round(auth_pct, 2),
            "classification_bracket": bracket,
            "fft_ratio": fft_ratio
        })

        bracket_short = bracket.replace("_", " ")[:24]
        print(f"{idx:<3} | {description[:34]:<34} | {synth_pct:>6.2f}% | {auth_pct:>10.2f}% | {bracket_short:<24}")

    print("=" * 95)
    print("\nSummary of Benchmark Verification:")
    high_ai = sum(1 for r in results if r["synthetic_likelihood_pct"] >= 65.0)
    human_real = sum(1 for r in results if r["synthetic_likelihood_pct"] <= 35.0)
    ambiguous = len(results) - high_ai - human_real
    print(f"Total Evaluated: {len(results)} | High AI Probability: {high_ai} | Likely Real/Human: {human_real} | Inconclusive: {ambiguous}")

if __name__ == "__main__":
    run_tests()
