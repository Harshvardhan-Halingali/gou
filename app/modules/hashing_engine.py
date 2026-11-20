import time
import hashlib
import numpy as np
from PIL import Image
import imagehash
from typing import Dict, Any, List
from app.core.base_module import ForensicModule, ModuleResult, TaskStatus
from app.database.repository import ForensicRepository

class HashingEngine(ForensicModule):
    @property
    def name(self) -> str:
        return "hashing_engine"

    @property
    def display_name(self) -> str:
        return "Multi-Algorithm Image Fingerprinting"

    def _compute_crop_resistant_hash(self, img: Image.Image) -> str:
        """
        Divides the image into a 3x3 grid of overlapping sub-regions
        and calculates dHash for each tile, combining into a composite tile signature.
        """
        width, height = img.size
        tile_w = width // 3
        tile_h = height // 3
        tile_hashes = []

        for i in range(3):
            for j in range(3):
                box = (j * tile_w, i * tile_h, (j + 1) * tile_w, (i + 1) * tile_h)
                tile = img.crop(box)
                h = str(imagehash.dhash(tile))
                tile_hashes.append(h)
        return "|".join(tile_hashes)

    def analyze(self, image_path: str, context: Dict[str, Any]) -> ModuleResult:
        start_time = time.perf_counter()
        limitations = [
            "Perceptual hashes are resilient to compression and slight scaling, but susceptible to severe non-uniform crops (>40%) and rotation.",
            "ColorHash captures palette distribution only, not spatial layout.",
            "Hash similarity indicates visual proximity, never definitive proof of original ownership."
        ]
        
        try:
            # 1. Cryptographic SHA-256
            sha256_hash = hashlib.sha256()
            with open(image_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    sha256_hash.update(chunk)
            sha256_str = sha256_hash.hexdigest()

            # 2. Perceptual Hashes via Pillow
            with Image.open(image_path) as img:
                img_rgb = img.convert("RGB")
                
                phash_val = str(imagehash.phash(img_rgb))
                dhash_val = str(imagehash.dhash(img_rgb))
                ahash_val = str(imagehash.average_hash(img_rgb))
                whash_val = str(imagehash.whash(img_rgb))
                colorhash_val = str(imagehash.colorhash(img_rgb))
                crop_resistant_val = self._compute_crop_resistant_hash(img_rgb)

            fingerprints = {
                "sha256": sha256_str,
                "phash": phash_val,
                "dhash": dhash_val,
                "ahash": ahash_val,
                "whash": whash_val,
                "colorhash": colorhash_val,
                "crop_resistant_hash": crop_resistant_val,
            }

            # 3. Match against known indexed database
            repo = ForensicRepository()
            matches = repo.find_matching_hashes(sha256_str, phash_val, max_hamming_dist=10)
            
            # Save hashes to database for future matching
            job_id = context.get("job_id", "")
            if job_id:
                repo.save_hashes(job_id, fingerprints)

            evidence_found = len(matches) > 0
            execution_time = (time.perf_counter() - start_time) * 1000.0

            return ModuleResult(
                module_name=self.name,
                status=TaskStatus.COMPLETED,
                result={
                    "fingerprints": fingerprints,
                    "matches": matches,
                    "total_matches_found": len(matches)
                },
                evidence_found=evidence_found,
                confidence=1.0 if evidence_found else None,
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
                error_message=f"Fingerprinting failed: {str(e)}",
                limitations=limitations
            )
