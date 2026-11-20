import os
import time
import math
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from collections import OrderedDict
import numpy as np
import torch
import soundfile as sf
import librosa
from transformers import AutoModel, AutoConfig

from app.config import settings

class AudioDeepfakeDetector:
    """
    Audio Deepfake Detection Engine powered by DF Arena 1B (Speech-Arena-2025/DF_Arena_1B_V_1)
    with fine-tuned fc5 classification head.
    
    Class Mapping:
      0: spoof (AI-generated / cloned / manipulated speech)
      1: bonafide (genuine human voice recording)
    """

    def __init__(self):
        self.model = None
        self.config = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._initialized = False
        self.sample_rate = settings.AUDIO_SAMPLE_RATE  # 16000 Hz
        self.window_size = 64600  # ~4.0375 seconds @ 16kHz
        self.hop_size = 32300     # 50% overlap for chunking

    def _lazy_init(self):
        if not self._initialized:
            self.load_model()

    def load_model(self):
        """Loads the pretrained DF Arena 1B model and restores the fine-tuned fc5 checkpoint."""
        print(f"[AUDIO MODEL] Initializing DF Arena 1B on device: {self.device}...")
        t0 = time.perf_counter()

        # 1. Load Pretrained Backbone & Conformer
        model_id = settings.AUDIO_MODEL_ID
        try:
            self.model = AutoModel.from_pretrained(
                model_id,
                trust_remote_code=True,
                local_files_only=True
            )
        except Exception:
            self.model = AutoModel.from_pretrained(
                model_id,
                trust_remote_code=True
            )
        self.model.to(self.device)
        self.model.eval()

        # 2. Restore Fine-Tuned FC5 Classification Checkpoint
        checkpoint_path = settings.AUDIO_CHECKPOINT_PATH
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Fine-tuned checkpoint not found at: {checkpoint_path}")

        print(f"[AUDIO MODEL] Restoring fine-tuned classification weights from: {checkpoint_path}")
        checkpoint = torch.load(str(checkpoint_path), map_location="cpu", weights_only=True)

        fc5_layer = self.model.backbone.conformer.fc5
        # Validate keys and tensor shapes
        if "weight" not in checkpoint or "bias" not in checkpoint:
            raise KeyError(f"Checkpoint missing required keys 'weight' or 'bias'. Found: {list(checkpoint.keys())}")
        
        if checkpoint["weight"].shape != fc5_layer.weight.shape:
            raise ValueError(
                f"fc5 weight shape mismatch: checkpoint {checkpoint['weight'].shape} vs model {fc5_layer.weight.shape}"
            )
        if checkpoint["bias"].shape != fc5_layer.bias.shape:
            raise ValueError(
                f"fc5 bias shape mismatch: checkpoint {checkpoint['bias'].shape} vs model {fc5_layer.bias.shape}"
            )

        fc5_layer.load_state_dict(checkpoint)
        self.model.eval()
        self._initialized = True
        elapsed = time.perf_counter() - t0
        print(f"[AUDIO MODEL] DF Arena 1B Fine-tuned successfully initialized in {elapsed:.2f}s.")

    def load_waveform(self, file_path: str) -> np.ndarray:
        """
        Loads any audio file (AAC, M4A, OPUS, MP3, WAV, FLAC, WhatsApp audio),
        resamples to 16kHz mono float32. Tries PyAV with packet-level fault tolerance,
        falling back to soundfile and librosa.
        """
        # 1. Try PyAV first with packet-level fault tolerance (handles AAC, WhatsApp audio, corrupted headers)
        try:
            import av
            container = av.open(file_path)
            audio_streams = [s for s in container.streams if s.type == "audio"]
            if audio_streams:
                stream = audio_streams[0]
                resampler = av.AudioResampler(format="fltp", layout="mono", rate=self.sample_rate)
                frames = []
                for packet in container.demux(stream):
                    try:
                        for frame in packet.decode():
                            if frame.samples > 0:
                                for rf in resampler.resample(frame):
                                    frames.append(rf.to_ndarray())
                    except Exception:
                        continue
                try:
                    for rf in resampler.resample(None):
                        frames.append(rf.to_ndarray())
                except Exception:
                    pass
                container.close()
                if frames:
                    waveform = np.concatenate(frames, axis=1).squeeze(0).astype(np.float32)
                    return waveform
        except Exception:
            pass

        # 2. Try soundfile
        try:
            y, sr = sf.read(file_path, dtype="float32")
            if y.ndim > 1:
                y = np.mean(y, axis=0) if y.shape[0] < y.shape[1] else np.mean(y, axis=1)
            if sr != self.sample_rate:
                y = librosa.resample(y.astype(np.float32), orig_sr=sr, target_sr=self.sample_rate)
            return y.astype(np.float32)
        except Exception:
            pass

        # 3. Try librosa
        y, _ = librosa.load(file_path, sr=self.sample_rate, mono=True)
        return y.astype(np.float32)

    def preprocess_audio(self, file_path: str) -> Tuple[List[np.ndarray], Dict[str, Any]]:
        """
        Loads, resamples to 16kHz, converts to mono, and generates 64600-sample windows.
        Returns: (chunks, audio_metadata)
        """
        y = self.load_waveform(file_path)

        total_samples = len(y)
        duration_sec = total_samples / self.sample_rate

        if total_samples < 1600 or duration_sec < 0.1:
            raise ValueError(f"Audio file is too short ({duration_sec:.2f}s). Minimum 0.1s required.")

        chunks = []
        if total_samples <= self.window_size:
            # Pad short audio using tile repeat strategy
            num_repeats = int(self.window_size / total_samples) + 1
            padded = np.tile(y, num_repeats)[:self.window_size]
            chunks.append(padded)
        else:
            # Overlapping sliding window chunking for long recordings
            start = 0
            while start + self.window_size <= total_samples:
                chunks.append(y[start : start + self.window_size])
                start += self.hop_size
            
            # If remaining tail has substantial audio (> 0.5s), pad and include
            remaining = total_samples - start
            if remaining >= 8000:
                tail = y[start:]
                num_repeats = int(self.window_size / len(tail)) + 1
                padded_tail = np.tile(tail, num_repeats)[:self.window_size]
                chunks.append(padded_tail)

        meta = {
            "duration_seconds": round(duration_sec, 3),
            "sample_rate": self.sample_rate,
            "channels": 1,
            "total_samples": total_samples,
            "chunk_count": len(chunks)
        }
        return chunks, meta

    def predict(self, file_path: str) -> Dict[str, Any]:
        """
        Executes end-to-end audio deepfake detection on the provided file.
        Returns complete forensic prediction dictionary.
        """
        self._lazy_init()
        t0 = time.perf_counter()

        chunks, meta = self.preprocess_audio(file_path)

        chunk_results = []
        all_logits = []

        total_dur = meta.get("duration_seconds", 0.0)

        with torch.inference_mode():
            for idx, chunk in enumerate(chunks):
                input_tensor = torch.from_numpy(chunk).to(self.device)  # shape: (64600,)
                outputs = self.model(input_tensor)
                logits = outputs["logits"]  # shape: (1, 2)
                probs = torch.softmax(logits, dim=-1)[0].cpu().numpy()

                spoof_p = float(probs[0])
                bonafide_p = float(probs[1])

                start_sec = round((idx * self.hop_size) / self.sample_rate, 2)
                end_sec = round(min(total_dur, (idx * self.hop_size + self.window_size) / self.sample_rate), 2)
                if end_sec <= start_sec:
                    end_sec = round(start_sec + (len(chunk) / self.sample_rate), 2)

                chunk_results.append({
                    "chunk_index": idx + 1,
                    "start_time_sec": start_sec,
                    "end_time_sec": end_sec,
                    "spoof_prob": round(spoof_p, 4),
                    "spoof_probability": round(spoof_p, 4),
                    "spoof_percentage": round(spoof_p * 100.0, 2),
                    "bonafide_prob": round(bonafide_p, 4),
                    "bonafide_probability": round(bonafide_p, 4),
                    "bonafide_percentage": round(bonafide_p * 100.0, 2),
                    "prediction": "spoof" if spoof_p >= 0.50 else "bonafide"
                })
                all_logits.append(logits.cpu().numpy()[0])

        # Aggregate logits across all chunks
        mean_logits = np.mean(all_logits, axis=0)
        overall_probs = torch.softmax(torch.from_numpy(mean_logits), dim=-1).numpy()

        overall_spoof = float(overall_probs[0])
        overall_bonafide = float(overall_probs[1])
        prediction = "spoof" if overall_spoof >= 0.50 else "bonafide"
        confidence = float(max(overall_spoof, overall_bonafide))

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        if prediction == "spoof":
            summary = (
                f"POTENTIAL AI-GENERATED AUDIO: High likelihood of speech synthesis, voice cloning, or replay spoofing "
                f"(Spoof probability: {overall_spoof * 100:.2f}%, Bonafide: {overall_bonafide * 100:.2f}%)."
            )
        else:
            summary = (
                f"GENUINE HUMAN SPEECH: Acoustic properties align with authentic human vocal tract characteristics "
                f"(Bonafide probability: {overall_bonafide * 100:.2f}%, Spoof: {overall_spoof * 100:.2f}%)."
            )

        return {
            "success": True,
            "prediction": prediction,
            "spoof_probability": round(overall_spoof, 4),
            "bonafide_probability": round(overall_bonafide, 4),
            "spoof_percentage": round(overall_spoof * 100.0, 2),
            "bonafide_percentage": round(overall_bonafide * 100.0, 2),
            "confidence": round(confidence, 4),
            "duration_seconds": total_dur,
            "sample_rate": meta.get("sample_rate", 16000),
            "num_chunks_evaluated": len(chunks),
            "model": "DF Arena 1B Fine-tuned",
            "architecture": "DF_Arena_1B_Antispoofing (Wav2Vec2 + 48-Layer Conformer)",
            "fine_tuned_layer": "model.backbone.conformer.fc5",
            "audio_metadata": meta,
            "execution_time_ms": round(elapsed_ms, 1),
            "chunk_predictions": chunk_results,
            "summary": summary,
            "interpretation": summary,
            "forensic_notice": (
                "Predictions reflect empirical outputs from the fine-tuned DF Arena 1B model. "
                "Results provide probabilistic forensic evidence and should be verified alongside provenance metadata."
            )
        }

audio_detector = AudioDeepfakeDetector()
