import time
import os
import cv2
import numpy as np
from PIL import Image, ImageChops, ImageEnhance
from typing import Dict, Any, List
from app.core.base_module import ForensicModule, ModuleResult, TaskStatus
from app.config import settings

class ManipulationELAModule(ForensicModule):
    @property
    def name(self) -> str:
        return "manipulation_ela"

    @property
    def display_name(self) -> str:
        return "Manipulation, ELA & Noise Variance"

    def _compute_ela(self, image_path: str, job_id: str, quality: int = 95, scale: int = 15) -> Dict[str, Any]:
        """
        Computes Error Level Analysis by resaving image at a known JPEG quality
        and calculating pixel-level absolute difference.
        """
        temp_recompressed = str(settings.REPORTS_DIR / f"{job_id}_recomp.jpg")
        ela_output_filename = f"{job_id}_ela.jpg"
        ela_output_path = str(settings.REPORTS_DIR / ela_output_filename)

        with Image.open(image_path) as original:
            original_rgb = original.convert("RGB")
            original_rgb.save(temp_recompressed, "JPEG", quality=quality)
            
            with Image.open(temp_recompressed) as recompressed:
                diff = ImageChops.difference(original_rgb, recompressed)
                
                # Scale up error level for visual inspection
                stat = diff.getextrema()
                max_diff = max([ex[1] for ex in stat]) if stat else 0
                scale_factor = scale if max_diff > 0 else 1
                enhancer = ImageEnhance.Brightness(diff)
                ela_visual = enhancer.enhance(scale_factor)
                ela_visual.save(ela_output_path, "JPEG")
                
                # Analyze localized block discrepancies
                diff_np = np.array(diff, dtype=np.float32)
                mean_diff = float(np.mean(diff_np))
                std_diff = float(np.std(diff_np))
                max_val = float(np.max(diff_np))

                h_d, w_d, _ = diff_np.shape
                b_size = 16
                block_means = []
                for y in range(0, h_d - b_size, b_size):
                    for x in range(0, w_d - b_size, b_size):
                        block_means.append(np.mean(diff_np[y:y+b_size, x:x+b_size]))

                block_arr = np.array(block_means) if block_means else np.array([mean_diff])
                p95 = float(np.percentile(block_arr, 95))
                median_err = float(np.median(block_arr)) + 1e-4
                local_discrepancy = float(p95 / median_err)

                # Localized anomaly detected only when localized spike is significant and distinct
                ela_anomaly = bool(local_discrepancy > 3.8 and max_val > 48.0)

        # Cleanup temporary recompressed file
        if os.path.exists(temp_recompressed):
            try:
                os.remove(temp_recompressed)
            except Exception:
                pass

        return {
            "ela_image_url": f"/static/reports/{ela_output_filename}",
            "mean_error": round(mean_diff, 2),
            "std_error": round(std_diff, 2),
            "max_error": round(max_val, 2),
            "local_discrepancy_ratio": round(local_discrepancy, 2),
            "ela_anomaly_detected": ela_anomaly
        }

    def _compute_noise_variance(self, image_path: str) -> Dict[str, Any]:
        """
        Calculates local Laplacian variance to identify inconsistent noise distributions
        typical in spliced or composite imagery.
        """
        img_gray = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img_gray is None:
            return {"inconsistent_noise": False, "noise_variance": 0.0}

        laplacian = cv2.Laplacian(img_gray, cv2.CV_64F)
        h, w = laplacian.shape
        block_size = 32
        block_vars = []

        for y in range(0, h - block_size, block_size):
            for x in range(0, w - block_size, block_size):
                block = laplacian[y:y+block_size, x:x+block_size]
                block_vars.append(np.var(block))

        if not block_vars:
            return {"inconsistent_noise": False, "noise_variance": 0.0}

        mean_var = float(np.mean(block_vars))
        std_var = float(np.std(block_vars))
        cv_metric = (std_var / mean_var) if mean_var > 0 else 0.0

        # Calibrated threshold: natural bokeh / depth-of-field has high variance, 
        # but genuine sensor noise discrepancies in spliced composites exhibit extreme ratios > 2.8 with high variance
        is_inconsistent = bool(cv_metric > 2.8 and std_var > 350.0)

        return {
            "noise_mean_variance": round(mean_var, 2),
            "noise_std_variance": round(std_var, 2),
            "noise_inconsistency_ratio": round(cv_metric, 3),
            "inconsistent_noise": is_inconsistent
        }

    def _detect_copy_move(self, image_path: str) -> Dict[str, Any]:
        """
        Identifies potential copy-move clone regions using self-matched ORB keypoints.
        """
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return {"cloned_regions_found": False, "candidate_matches": 0}

        orb = cv2.ORB_create(nfeatures=1000)
        keypoints, descriptors = orb.detectAndCompute(img, None)

        if descriptors is None or len(descriptors) < 10:
            return {"cloned_regions_found": False, "candidate_matches": 0}

        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        matches = bf.knnMatch(descriptors, descriptors, k=2)

        vectors = []
        min_spatial_dist = 40.0

        for m, n in matches:
            if m.distance < 0.60 * n.distance:
                pt1 = keypoints[m.queryIdx].pt
                pt2 = keypoints[m.trainIdx].pt
                dx = pt1[0] - pt2[0]
                dy = pt1[1] - pt2[1]
                dist = np.sqrt(dx**2 + dy**2)
                if dist > min_spatial_dist:
                    vectors.append((dx, dy))

        # Real copy-move requires clustered translation vectors
        duplicate_clusters = len(vectors)
        cloned_found = duplicate_clusters >= 22

        return {
            "cloned_regions_found": cloned_found,
            "candidate_matches": duplicate_clusters
        }

    def analyze(self, image_path: str, context: Dict[str, Any]) -> ModuleResult:
        start_time = time.perf_counter()
        job_id = context.get("job_id", "default_job")
        limitations = [
            "ELA operates most effectively on original high-quality JPEGs; multiple recompressions flatten error differences.",
            "High frequency textures (hair, leaves, sand) naturally exhibit elevated error levels without tampering.",
            "Copy-move detector requires sufficient feature texture; plain flat backgrounds will not trigger matches."
        ]

        try:
            ela_results = self._compute_ela(image_path, job_id)
            noise_results = self._compute_noise_variance(image_path)
            copymove_results = self._detect_copy_move(image_path)

            evidence_found = (
                ela_results["ela_anomaly_detected"] or 
                noise_results["inconsistent_noise"] or 
                copymove_results["cloned_regions_found"]
            )

            # Calculate heuristic confidence
            confidence = None
            if evidence_found:
                signals = [
                    ela_results["ela_anomaly_detected"],
                    noise_results["inconsistent_noise"],
                    copymove_results["cloned_regions_found"]
                ]
                confidence = round(0.55 + (0.15 * sum(signals)), 2)

            execution_time = (time.perf_counter() - start_time) * 1000.0

            return ModuleResult(
                module_name=self.name,
                status=TaskStatus.COMPLETED,
                result={
                    "ela": ela_results,
                    "noise_analysis": noise_results,
                    "copy_move": copymove_results
                },
                evidence_found=evidence_found,
                confidence=confidence,
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
                error_message=f"Forensic manipulation analysis failed: {str(e)}",
                limitations=limitations
            )
