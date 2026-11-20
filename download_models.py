#!/usr/bin/env python3
"""
Model management utility for IMAGE TRACE.
Pre-caches AI & Deep Learning models for offline forensic inference.
"""

import os
import sys
import argparse
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app.config import settings


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:3.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def get_model_status():
    """Check the status of all local model checkpoints."""
    models = [
        {
            "name": "SDXL Synthetic Detector (ViT)",
            "type": "Hugging Face Cache",
            "repo": "Organika/sdxl-detector",
            "path": Path.home() / ".cache" / "huggingface" / "hub",
            "required": True,
        },
        {
            "name": "OpenCLIP Embeddings (ViT-B-32)",
            "type": "Torch / Hugging Face Cache",
            "repo": "ViT-B-32 (laion2b_s34b_b79k)",
            "path": Path.home() / ".cache" / "clip",
            "required": True,
        },
        {
            "name": "YuNet Face Detector",
            "type": "ONNX Model",
            "path": settings.YUNET_FACE_MODEL,
            "url": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
            "required": False,
        },
        {
            "name": "GenD Deepfake Detector",
            "type": "SafeTensors Checkpoint",
            "path": settings.GEND_CHECKPOINT_PATH,
            "repo": "yermandy/GenD_CLIP_L_14",
            "required": False,
        },
        {
            "name": "DeMamba Video AI Detector",
            "type": "PyTorch Checkpoint",
            "path": settings.DEMAMBA_CHECKPOINT_PATH,
            "repo": "Ahsanz/DeMamba-GenVideo100K",
            "required": False,
        },
        {
            "name": "DF Arena Audio Deepfake Detector",
            "type": "PyTorch Checkpoint",
            "path": settings.AUDIO_CHECKPOINT_PATH,
            "repo": "Speech-Arena-2025/DF_Arena_1B_V_1",
            "required": False,
        },
    ]

    for m in models:
        path = m.get("path")
        if path and path.exists():
            if path.is_file():
                m["status"] = "INSTALLED"
                m["size"] = format_size(path.stat().st_size)
            else:
                m["status"] = "PRESENT"
                m["size"] = "Directory"
        else:
            m["status"] = "MISSING"
            m["size"] = "0 B"

    return models


def print_status():
    """Print status of all models."""
    print("=" * 80)
    print("            IMAGE TRACE — FORENSIC AI MODEL CHECKPOINT REGISTRY")
    print("=" * 80)
    print(f"{'Model Name':<35} | {'Type':<22} | {'Status':<10} | {'Size'}")
    print("-" * 80)
    models = get_model_status()
    for m in models:
        status_tag = f"[{m['status']}]"
        print(f"{m['name']:<35} | {m['type']:<22} | {status_tag:<10} | {m['size']}")
    print("=" * 80)


def download_base_models():
    """Pre-cache core image classification and embedding models."""
    print("\n[1/2] Pre-caching Hugging Face AI detection model (Organika/sdxl-detector)...")
    try:
        from transformers import pipeline
        pipeline("image-classification", model="Organika/sdxl-detector", device="cpu")
        print("      --> [SUCCESS] Organika/sdxl-detector ready.")
    except Exception as e:
        print(f"      --> [NOTICE] Skipping Organika/sdxl-detector: {e}")

    print("\n[2/2] Pre-caching OpenCLIP weights (ViT-B-32 laion2b_s34b_b79k)...")
    try:
        import open_clip
        open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k", device="cpu")
        print("      --> [SUCCESS] OpenCLIP ViT-B-32 ready.")
    except Exception as e:
        print(f"      --> [NOTICE] Skipping OpenCLIP ViT-B-32: {e}")


def download_video_models():
    """Download video & face deepfake detection weights using huggingface_hub."""
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("huggingface_hub is required to download video checkpoints. Run: pip install huggingface_hub")
        return

    # 1. GenD
    if not settings.GEND_CHECKPOINT_PATH.exists():
        print("\nDownloading GenD CLIP-L/14 checkpoint (~1.2 GB)...")
        settings.GEND_MODEL_DIR.mkdir(parents=True, exist_ok=True)
        try:
            hf_hub_download(
                repo_id="yermandy/GenD_CLIP_L_14",
                filename="model.safetensors",
                local_dir=str(settings.GEND_MODEL_DIR),
            )
            print("  --> [SUCCESS] GenD checkpoint saved.")
        except Exception as e:
            print(f"  --> [ERROR] Failed to download GenD: {e}")
    else:
        print("\nGenD checkpoint is already present.")

    # 2. DeMamba
    if not settings.DEMAMBA_CHECKPOINT_PATH.exists():
        print("\nDownloading DeMamba GenVideo-100K checkpoint (~500 MB)...")
        settings.DEMAMBA_MODEL_DIR.mkdir(parents=True, exist_ok=True)
        try:
            hf_hub_download(
                repo_id="Ahsanz/DeMamba-GenVideo100K",
                filename="best_acc.pth",
                local_dir=str(settings.DEMAMBA_MODEL_DIR),
            )
            print("  --> [SUCCESS] DeMamba checkpoint saved.")
        except Exception as e:
            print(f"  --> [ERROR] Failed to download DeMamba: {e}")
    else:
        print("\nDeMamba checkpoint is already present.")


def main():
    parser = argparse.ArgumentParser(description="IMAGE TRACE Model Downloader & Status Tool")
    parser.add_argument("--check", action="store_true", help="Check local model status without downloading")
    parser.add_argument("--video", action="store_true", help="Download video deepfake models (DeMamba + GenD)")
    parser.add_argument("--all", action="store_true", help="Download all base and optional models")
    args = parser.parse_args()

    print_status()

    if args.check:
        return

    download_base_models()

    if args.video or args.all:
        download_video_models()

    print("\nUpdated model status:")
    print_status()


if __name__ == "__main__":
    main()
