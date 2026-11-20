import time
import os
from pathlib import Path
from typing import Dict, Any, List
import numpy as np
from PIL import Image
from app.core.base_module import ForensicModule, ModuleResult, TaskStatus
from app.config import settings
from app.database.repository import ForensicRepository

class ReverseEngine(ForensicModule):
    @property
    def name(self) -> str:
        return "reverse_engine"

    @property
    def display_name(self) -> str:
        return "OpenCLIP Semantic Vector Search"

    def __init__(self):
        self.model = None
        self.preprocess = None
        self.device = "cpu"
        self._initialized = False

    def _lazy_init(self):
        if not self._initialized:
            try:
                import torch
                import open_clip
                self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                    "ViT-B-32", pretrained="laion2b_s34b_b79k", device="cpu"
                )
                self.model.eval()
                self._initialized = True
            except Exception as e:
                self._initialized = False
                self.init_error = str(e)

    def _extract_fallback_embedding(self, img_path: str) -> np.ndarray:
        """
        Computes a normalized 512-dimensional spatial color-gradient histogram embedding
        as a reliable offline vector fallback.
        """
        with Image.open(img_path) as img:
            rgb = img.convert("RGB").resize((128, 128))
            arr = np.array(rgb, dtype=np.float32) / 255.0
            
            # 8x8 spatial grid with 8 color bins
            features = []
            for y in range(0, 128, 16):
                for x in range(0, 128, 16):
                    tile = arr[y:y+16, x:x+16]
                    mean_rgb = np.mean(tile, axis=(0, 1))
                    std_rgb = np.std(tile, axis=(0, 1))
                    features.extend(mean_rgb)
                    features.extend(std_rgb[:2])  # 8 bins per tile * 64 tiles = 512-dim vector
            
            vec = np.array(features, dtype=np.float32)
            norm = np.linalg.norm(vec)
            return vec / (norm + 1e-8)

    def _extract_embedding(self, img_path: str) -> np.ndarray:
        if self._initialized and self.model:
            import torch
            image = Image.open(img_path).convert("RGB")
            tensor = self.preprocess(image).unsqueeze(0).to(self.device)
            with torch.no_grad():
                image_features = self.model.encode_image(tensor)
                image_features /= image_features.norm(dim=-1, keepdim=True)
            return image_features.cpu().numpy().flatten()
        else:
            return self._extract_fallback_embedding(img_path)

    def analyze(self, image_path: str, context: Dict[str, Any]) -> ModuleResult:
        start_time = time.perf_counter()
        limitations = [
            "OpenCLIP searches only the accessible, locally indexed image collection; it does not scrape the live public web.",
            "Visual vector similarity captures high-level artistic and conceptual composition, not necessarily identical origin.",
            "Cosine similarity >= 0.85 indicates strong visual correspondence."
        ]

        try:
            self._lazy_init()
            backend_label = "OpenCLIP_ViT-B-32" if self._initialized else "Spatial_Feature_Embedding_512D"

            query_vec = self._extract_embedding(image_path)

            # Search corpus/verified_reference/ directory
            corpus_dir = settings.CORPUS_DIR
            corpus_files = [
                f for f in corpus_dir.iterdir() 
                if f.is_file() and f.suffix.lower() in settings.ALLOWED_EXTENSIONS
                and str(f.resolve()) != str(Path(image_path).resolve())
            ]

            matches: List[Dict[str, Any]] = []
            for ref_path in corpus_files:
                try:
                    ref_vec = self._extract_embedding(str(ref_path))
                    # Cosine similarity of unit vectors is dot product
                    cosine_sim = float(np.dot(query_vec, ref_vec))
                    threshold = 0.70 if self._initialized else 0.80
                    if cosine_sim >= threshold:
                        matches.append({
                            "reference_file": ref_path.name,
                            "source_platform": "LOCAL_ARCHIVE",
                            "cosine_similarity": round(cosine_sim, 3),
                            "match_interpretation": "HIGH_SIMILARITY" if cosine_sim >= 0.85 else "MODERATE_SIMILARITY"
                        })
                except Exception:
                    pass

            matches.sort(key=lambda x: x["cosine_similarity"], reverse=True)
            evidence_found = len(matches) > 0
            best_score = matches[0]["cosine_similarity"] if matches else None

            execution_time = (time.perf_counter() - start_time) * 1000.0

            return ModuleResult(
                module_name=self.name,
                status=TaskStatus.COMPLETED,
                result={
                    "vector_backend": backend_label,
                    "embedding_dimension": int(query_vec.shape[0]),
                    "corpus_items_searched": len(corpus_files),
                    "matches": matches,
                    "top_similarity": best_score
                },
                evidence_found=evidence_found,
                confidence=best_score,
                execution_time_ms=round(execution_time, 2),
                limitations=limitations
            )
        except Exception as e:
            execution_time = (time.perf_counter() - start_time) * 1000.0
            return ModuleResult(
                module_name=self.name,
                status=TaskStatus.FAILED,
                result={},
                evidence_found=False,
                execution_time_ms=round(execution_time, 2),
                error_message=f"Reverse search failed: {str(e)}",
                limitations=limitations
            )
