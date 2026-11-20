import time
import os
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, List
from app.core.base_module import ForensicModule, ModuleResult, TaskStatus
from app.config import settings

class SIFTEngine(ForensicModule):
    @property
    def name(self) -> str:
        return "sift_engine"

    @property
    def display_name(self) -> str:
        return "OpenCV SIFT/ORB Local Keypoint Homography"

    def __init__(self):
        # Prefer SIFT if available, fallback to ORB
        try:
            self.detector = cv2.SIFT_create(nfeatures=1500)
            self.algo_name = "SIFT"
        except Exception:
            self.detector = cv2.ORB_create(nfeatures=1500)
            self.algo_name = "ORB"

    def _match_features(self, desc1: np.ndarray, desc2: np.ndarray) -> List[Any]:
        if desc1 is None or desc2 is None or len(desc1) < 4 or len(desc2) < 4:
            return []

        if self.algo_name == "SIFT":
            # FLANN parameters for SIFT
            FLANN_INDEX_KDTREE = 1
            index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
            search_params = dict(checks=50)
            flann = cv2.FlannBasedMatcher(index_params, search_params)
            matches = flann.knnMatch(desc1, desc2, k=2)
        else:
            # Hamming for ORB
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
            matches = bf.knnMatch(desc1, desc2, k=2)

        good_matches = []
        for m_n in matches:
            if len(m_n) == 2:
                m, n = m_n
                if m.distance < 0.75 * n.distance:
                    good_matches.append(m)
        return good_matches

    def analyze(self, image_path: str, context: Dict[str, Any]) -> ModuleResult:
        start_time = time.perf_counter()
        limitations = [
            "Local keypoint matching requires sufficient edge/corner contrast; fails on smooth textures or motion blur.",
            "Can only detect matches against images in the local indexed reference corpus.",
            "Homography check requires a minimum of 4 spatially robust inlier keypoints."
        ]

        try:
            query_img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if query_img is None:
                raise ValueError("Could not read query image for feature extraction.")

            kp_query, desc_query = self.detector.detectAndCompute(query_img, None)
            query_kp_count = len(kp_query) if kp_query else 0

            corpus_dir = settings.CORPUS_DIR
            corpus_files = [
                f for f in corpus_dir.iterdir() 
                if f.is_file() and f.suffix.lower() in settings.ALLOWED_EXTENSIONS
                and str(f.resolve()) != str(Path(image_path).resolve())
            ]

            matches_found = []
            for ref_path in corpus_files:
                ref_img = cv2.imread(str(ref_path), cv2.IMREAD_GRAYSCALE)
                if ref_img is None:
                    continue

                kp_ref, desc_ref = self.detector.detectAndCompute(ref_img, None)
                if desc_ref is None or len(desc_ref) < 4:
                    continue

                good = self._match_features(desc_query, desc_ref)
                
                # Check for geometric consistency if >= 8 good matches
                inliers = 0
                has_homography = False
                if len(good) >= 8:
                    src_pts = np.float32([kp_query[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
                    dst_pts = np.float32([kp_ref[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
                    
                    try:
                        H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
                        if mask is not None:
                            inliers = int(np.sum(mask))
                            has_homography = inliers >= 8
                    except Exception:
                        pass

                if has_homography or len(good) >= 12:
                    score = min(1.0, len(good) / 50.0)
                    matches_found.append({
                        "reference_image": ref_path.name,
                        "good_keypoint_matches": len(good),
                        "ransac_inliers": inliers,
                        "homography_verified": has_homography,
                        "geometric_similarity": round(score, 3)
                    })

            evidence_found = len(matches_found) > 0
            execution_time = (time.perf_counter() - start_time) * 1000.0

            return ModuleResult(
                module_name=self.name,
                status=TaskStatus.COMPLETED,
                result={
                    "algorithm": self.algo_name,
                    "query_keypoints_extracted": query_kp_count,
                    "corpus_images_checked": len(corpus_files),
                    "matches": matches_found
                },
                evidence_found=evidence_found,
                confidence=0.92 if evidence_found else None,
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
                error_message=f"SIFT/ORB matching error: {str(e)}",
                limitations=limitations
            )
