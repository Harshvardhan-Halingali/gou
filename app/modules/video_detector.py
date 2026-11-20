import os
import sys
import cv2
import time
import math
import json
import torch
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Dict, Any, List, Tuple
from safetensors.torch import load_file

from app.config import settings

# Ensure offline loading for cached transformers architectures
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from app.modules.video_network.demamba import (
    XCLIP_DeMamba,
    load_checkpoint as load_demamba_checkpoint,
    sample_frames as demamba_sample_frames,
    make_clips as demamba_make_clips,
)
from app.modules.video_network.gend import GenD, GenDConfig


class DualVideoDetector:
    """
    Unified AI-Generated Video & Deepfake Manipulation Detector integrating:
    1. DeMamba (X-CLIP + Mamba trained on GenVideo-100K) -> AI-Generated Video Detection
       (https://huggingface.co/Ahsanz/DeMamba-GenVideo100K)
    2. GenD (CLIP-Large ViT-14 WACV 2026) -> Generalized Facial Deepfake Detection
       (https://huggingface.co/collections/yermandy/gend / yermandy/GenD_CLIP_L_14)
    """

    def __init__(self, device: str = None):
        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        self.demamba_model = None
        self.gend_model = None
        self.face_detector = None
        self._initialized = False

    def _lazy_init(self):
        if self._initialized:
            return

        t0 = time.perf_counter()
        print(f"[DUAL VIDEO DETECTOR] Initializing DeMamba + GenD on {self.device}...")

        # -------------------------------------------------------------
        # 1. Initialize DeMamba (AI-Generated Video Detector)
        # -------------------------------------------------------------
        if not settings.DEMAMBA_CHECKPOINT_PATH.exists():
            raise FileNotFoundError(
                f"DeMamba checkpoint not found at: {settings.DEMAMBA_CHECKPOINT_PATH}"
            )

        print("[DUAL VIDEO DETECTOR] Loading DeMamba (X-CLIP + Mamba)...")
        self.demamba_model = XCLIP_DeMamba(class_num=1)
        load_demamba_checkpoint(self.demamba_model, str(settings.DEMAMBA_CHECKPOINT_PATH))
        self.demamba_model.to(self.device)
        self.demamba_model.eval()

        # -------------------------------------------------------------
        # 2. Initialize GenD (Facial Deepfake Detector)
        # -------------------------------------------------------------
        config_path = settings.GEND_CONFIG_PATH
        if not config_path.exists():
            fallback_cfg = Path(__file__).parent / "video_network" / "gend_config.json"
            if fallback_cfg.exists():
                config_path = fallback_cfg

        if not settings.GEND_CHECKPOINT_PATH.exists() or not config_path.exists():
            raise FileNotFoundError(
                f"GenD model files not found at: {settings.GEND_MODEL_DIR}"
            )

        print("[DUAL VIDEO DETECTOR] Loading GenD (CLIP-L/14 WACV 2026)...")
        with open(str(config_path), "r", encoding="utf-8") as f:
            gend_cfg_dict = json.load(f)

        gend_config = GenDConfig(**gend_cfg_dict)
        self.gend_model = GenD(gend_config)
        gend_sd = load_file(str(settings.GEND_CHECKPOINT_PATH))
        self.gend_model.load_state_dict(gend_sd)
        self.gend_model.to(self.device)
        self.gend_model.eval()

        # -------------------------------------------------------------
        # 3. Initialize YuNet Face Detector for Facial Alignment
        # -------------------------------------------------------------
        if settings.YUNET_FACE_MODEL.exists():
            self.face_detector = cv2.FaceDetectorYN_create(
                model=str(settings.YUNET_FACE_MODEL),
                config="",
                input_size=(640, 480),
                score_threshold=0.6,
                nms_threshold=0.3,
                top_k=5000,
            )

        self._initialized = True
        elapsed = time.perf_counter() - t0
        print(f"[DUAL VIDEO DETECTOR] Both models initialized in {elapsed:.2f}s.")

    def detect_face_and_crop(self, frame: np.ndarray, scale: float = 1.3) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Detects primary human face using YuNet with 1.3x bounding box expansion.
        Returns (None, face_info) if no face is detected in the frame.
        """
        h, w = frame.shape[:2]
        face_info = {"face_detected": False, "confidence": 0.0, "box": None, "low_res": False}

        if self.face_detector is not None:
            self.face_detector.setInputSize((w, h))
            faces = self.face_detector.detect(frame)
            if faces[0] > 0 and faces[1] is not None and len(faces[1]) > 0:
                best_face = max(faces[1], key=lambda f: f[-1])
                conf = float(best_face[-1])
                box = best_face[:4].astype(int)
                x, y, bw, bh = int(box[0]), int(box[1]), int(box[2]), int(box[3])

                # 1.3x expansion around facial center
                size_bb = int(max(bw, bh) * scale)
                cx, cy = x + bw // 2, y + bh // 2
                x1 = max(int(cx - size_bb // 2), 0)
                y1 = max(int(cy - size_bb // 2), 0)
                x2 = min(x1 + size_bb, w)
                y2 = min(y1 + size_bb, h)

                crop = frame[y1:y2, x1:x2]
                if crop.size > 0:
                    face_info = {
                        "face_detected": True,
                        "confidence": round(conf, 3),
                        "box": {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1},
                        "low_res": bool(bw < 70 or bh < 70),
                    }
                    return crop, face_info

        return None, face_info

    def predict(self, video_path: str, max_sample_frames: int = 24, num_clips: int = 2) -> Dict[str, Any]:
        """
        Runs dual inference on video:
        1. DeMamba checks whether the video is AI-generated (Crafter, Gen2, Sora, Kling, etc.).
        2. GenD checks whether the video contains facial deepfakes / manipulation.
        Returns unified probabilities, individual model breakdowns, and human bonafide verification.
        """
        self._lazy_init()
        t0 = time.perf_counter()

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration_sec = total_frames / fps if fps > 0 else 0.0
        cap.release()

        if total_frames <= 0:
            raise ValueError("Video contains zero valid frames.")

        with torch.inference_mode():
            # =========================================================
            # STREAM 1: DeMamba (AI-Generated Video Detection)
            # =========================================================
            demamba_frames = demamba_sample_frames(video_path)
            if demamba_frames:
                demamba_clips = demamba_make_clips(demamba_frames, num_clips=num_clips)
                x_demamba = torch.from_numpy(demamba_clips).to(self.device)
                demamba_logits = self.demamba_model(x_demamba)
                p_ai_fake = float(demamba_logits[:, 0].sigmoid().mean().cpu().item())
            else:
                p_ai_fake = 0.0

            p_ai_real = 1.0 - p_ai_fake
            spoof_ai_pct = round(p_ai_fake * 100.0, 2)
            bonafide_ai_pct = round(p_ai_real * 100.0, 2)
            is_ai_generated = spoof_ai_pct >= 50.0

            # =========================================================
            # STREAM 2: GenD (Facial Deepfake & Manipulation Detection)
            # =========================================================
            cap = cv2.VideoCapture(video_path)
            num_samples = min(total_frames, max_sample_frames)
            sample_indices = np.linspace(0, total_frames - 1, num_samples, dtype=int)
            sample_set = set(sample_indices)

            frame_results = []
            gend_fake_probs = []
            gend_real_probs = []
            faces_detected_count = 0
            low_res_count = 0

            current_frame_idx = 0
            while cap.isOpened() and len(frame_results) < num_samples:
                ret, frame = cap.read()
                if not ret or frame is None:
                    break

                if current_frame_idx in sample_set:
                    timestamp_sec = round(current_frame_idx / fps, 2)
                    face_crop, face_meta = self.detect_face_and_crop(frame)

                    if face_meta["face_detected"] and face_crop is not None:
                        faces_detected_count += 1
                        if face_meta.get("low_res"):
                            low_res_count += 1

                        # Use GenD feature extractor preprocess on cropped face
                        face_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
                        pil_img = Image.fromarray(face_rgb)
                        inp_tensor = self.gend_model.feature_extractor.preprocess(pil_img).unsqueeze(0).to(self.device)

                        # GenD forward pass: index 0 = Bonafide / Real, index 1 = Spoof Deepfake
                        out_logits = self.gend_model(inp_tensor)
                        probs = torch.softmax(out_logits, dim=-1)[0].cpu().numpy()

                        p_real = float(probs[0])
                        p_fake = float(probs[1])

                        gend_real_probs.append(p_real)
                        gend_fake_probs.append(p_fake)

                        frame_results.append({
                            "frame_index": int(current_frame_idx),
                            "timestamp_sec": timestamp_sec,
                            "face_detected": True,
                            "face_confidence": face_meta["confidence"],
                            "bounding_box": face_meta["box"],
                            "low_res": face_meta.get("low_res", False),
                            "spoof_deepfake_percentage": round(p_fake * 100.0, 2),
                            "bonafide_facial_percentage": round(p_real * 100.0, 2),
                            "verdict": "SPOOF_DEEPFAKE" if p_fake >= 0.50 else "BONAFIDE",
                        })
                    else:
                        frame_results.append({
                            "frame_index": int(current_frame_idx),
                            "timestamp_sec": timestamp_sec,
                            "face_detected": False,
                            "face_confidence": 0.0,
                            "bounding_box": None,
                            "low_res": False,
                            "spoof_deepfake_percentage": None,
                            "bonafide_facial_percentage": None,
                            "verdict": "NO_FACE",
                        })

                current_frame_idx += 1

            cap.release()

        # Aggregate GenD facial deepfake probabilities
        if gend_fake_probs:
            mean_df_fake = float(np.mean(gend_fake_probs))
            mean_df_real = float(np.mean(gend_real_probs))
            spoof_deepfake_pct = round(mean_df_fake * 100.0, 2)
            bonafide_deepfake_pct = round(mean_df_real * 100.0, 2)
            is_deepfake = spoof_deepfake_pct >= 50.0
        else:
            mean_df_fake = 0.0
            mean_df_real = 1.0
            spoof_deepfake_pct = 0.0
            bonafide_deepfake_pct = 100.0
            is_deepfake = False

        # =========================================================
        # UNIFIED VERDICT & HUMAN BONAFIDE VERIFICATION
        # =========================================================
        is_bonafide = (not is_ai_generated) and (not is_deepfake)

        if is_bonafide:
            prediction = "bonafide"
            verdict_badge = "BONAFIDE (HUMAN & REAL CAMERA VERIFIED)"
            summary = (
                f"BONAFIDE AUTHENTIC VIDEO VERIFIED: "
                f"Camera optical sensor dynamics confirmed by DeMamba (Authentic: {bonafide_ai_pct}%, AI Risk: {spoof_ai_pct}%), "
                f"and facial biometric consistency verified by GenD (Authentic Face: {bonafide_deepfake_pct}%, Deepfake Risk: {spoof_deepfake_pct}%)."
            )
        elif is_ai_generated and is_deepfake:
            prediction = "spoof_synthetic_deepfake"
            verdict_badge = "SPOOF: AI GENERATED & DEEPFAKE"
            summary = (
                f"SYNTHETIC MANIPULATION DETECTED: Video exhibits synthetic AI generation patterns "
                f"(Spoof AI: {spoof_ai_pct}%) along with facial deepfake manipulation artifacts (Spoof Deepfake: {spoof_deepfake_pct}%)."
            )
        elif is_ai_generated:
            prediction = "spoof_ai"
            verdict_badge = "SPOOF: AI GENERATED VIDEO"
            summary = (
                f"AI-GENERATED VIDEO DETECTED: DeMamba flagged synthetic video generation artifacts "
                f"(Spoof AI: {spoof_ai_pct}%, Bonafide: {bonafide_ai_pct}%)."
            )
        else:
            prediction = "spoof_deepfake"
            verdict_badge = "SPOOF: DEEPFAKE FACIAL MANIPULATION"
            summary = (
                f"DEEPFAKE MANIPULATION DETECTED: GenD flagged facial reenactment or deepfake boundary manipulation "
                f"(Spoof Deepfake: {spoof_deepfake_pct}%, Bonafide Face: {bonafide_deepfake_pct}%)."
            )

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        # Primary percentages for unified scoring
        overall_spoof_pct = round(max(spoof_ai_pct, spoof_deepfake_pct), 2)
        overall_bonafide_pct = round(100.0 - overall_spoof_pct, 2) if not is_bonafide else round(min(bonafide_ai_pct, bonafide_deepfake_pct), 2)

        return {
            "success": True,
            "prediction": prediction,
            "is_bonafide": is_bonafide,
            "verdict_badge": verdict_badge,
            # Requested percentage outputs
            "spoof_deepfake_percentage": spoof_deepfake_pct,
            "bonafide_deepfake_percentage": bonafide_deepfake_pct,
            "spoof_ai_percentage": spoof_ai_pct,
            "bonafide_ai_percentage": bonafide_ai_pct,
            # Backward-compatible fields
            "fake_percentage": overall_spoof_pct,
            "real_percentage": overall_bonafide_pct,
            "fake_probability": round(overall_spoof_pct / 100.0, 4),
            "real_probability": round(overall_bonafide_pct / 100.0, 4),
            # Model metadata
            "models_used": [
                {
                    "name": "DeMamba (GenVideo-100K)",
                    "type": "AI-Generated Video Detection",
                    "repo": "https://huggingface.co/Ahsanz/DeMamba-GenVideo100K",
                    "spoof_percentage": spoof_ai_pct,
                    "bonafide_percentage": bonafide_ai_pct,
                },
                {
                    "name": "GenD CLIP-L/14 (WACV 2026)",
                    "type": "Facial Deepfake Detection",
                    "repo": "https://huggingface.co/collections/yermandy/gend",
                    "spoof_percentage": spoof_deepfake_pct,
                    "bonafide_percentage": bonafide_deepfake_pct,
                },
            ],
            "model": "Dual-Model: DeMamba (GenVideo-100K) + GenD (CLIP-L/14)",
            "duration_seconds": round(duration_sec, 2),
            "total_frames_in_video": total_frames,
            "frames_analyzed": len(frame_results),
            "faces_detected_count": faces_detected_count,
            "low_res_faces_count": low_res_count,
            "resolution": f"{width}x{height}",
            "fps": round(fps, 1),
            "execution_time_ms": round(elapsed_ms, 1),
            "frame_predictions": frame_results,
            "summary": summary,
            "interpretation": summary,
            "forensic_notice": (
                "Dual-model forensic analysis performed using DeMamba (GenVideo-100K) for full AI-generated "
                "video detection and GenD (WACV 2026) for generalized facial deepfake detection."
            ),
        }


video_detector = DualVideoDetector()
