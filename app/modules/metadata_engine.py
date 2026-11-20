import time
import os
from PIL import Image, ExifTags
import exifread
from typing import Dict, Any, List
from app.core.base_module import ForensicModule, ModuleResult, TaskStatus

SUSPICIOUS_SOFTWARE_KEYWORDS = [
    "photoshop", "gimp", "canva", "stable diffusion", "midjourney", 
    "dall-e", "novelai", "automatic1111", "comfyui", "affinity photo",
    "lightroom", "pixelmator", "snapseed", "faceapp"
]

class MetadataEngine(ForensicModule):
    @property
    def name(self) -> str:
        return "metadata_engine"

    @property
    def display_name(self) -> str:
        return "EXIF, Provenance & Content Credentials"

    def _check_c2pa_manifest(self, file_path: str) -> Dict[str, Any]:
        """
        Inspects binary chunks for standard JUMBF (JPEG Universal Metadata Box Format) 
        and C2PA (Coalition for Content Provenance and Authenticity) signatures.
        """
        c2pa_found = False
        details = "No C2PA/JUMBF provenance manifest found in binary headers."
        try:
            with open(file_path, "rb") as f:
                content = f.read(512 * 1024)  # Read initial 512KB
                if b"c2pa" in content or b"jumbf" in content:
                    c2pa_found = True
                    details = "C2PA / JUMBF Content Credentials binary markers identified in container headers."
        except Exception as e:
            details = f"C2PA inspection encountered an error: {str(e)}"

        return {
            "c2pa_present": c2pa_found,
            "details": details
        }

    def analyze(self, image_path: str, context: Dict[str, Any]) -> ModuleResult:
        start_time = time.perf_counter()
        limitations = [
            "Most social media platforms (Twitter/X, Facebook, WhatsApp) strip EXIF and C2PA metadata on upload.",
            "Missing metadata is common and does NOT constitute proof of tampering or synthetic generation.",
            "EXIF metadata can be easily forged or modified using free command-line tools."
        ]

        try:
            metadata_dict: Dict[str, Any] = {}
            editing_software_detected = []
            
            # 1. Parse via Pillow
            with Image.open(image_path) as img:
                metadata_dict["format"] = img.format
                metadata_dict["mode"] = img.mode
                metadata_dict["dimensions"] = list(img.size)
                
                info = getattr(img, "_getexif", None)
                if info and callable(info):
                    exif_data = info()
                    if exif_data:
                        for tag_id, val in exif_data.items():
                            tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                            # Clean values for JSON serialization
                            if isinstance(val, (bytes, bytearray)):
                                try:
                                    val = val.decode("utf-8", errors="ignore").strip()
                                except Exception:
                                    val = "<binary data>"
                            elif not isinstance(val, (str, int, float, list, dict)):
                                val = str(val)
                            metadata_dict[tag_name] = val

            # 2. Parse deep tags via exifread
            with open(image_path, "rb") as f:
                tags = exifread.process_file(f, details=False)
                for tag, val in tags.items():
                    if tag not in metadata_dict:
                        metadata_dict[tag] = str(val)

            # Check for suspicious editing software in tags
            for key, val in metadata_dict.items():
                val_str = str(val).lower()
                for keyword in SUSPICIOUS_SOFTWARE_KEYWORDS:
                    if keyword in val_str:
                        editing_software_detected.append(f"{key}: {val}")

            # 3. Check C2PA manifest
            c2pa_info = self._check_c2pa_manifest(image_path)
            
            has_exif = len(metadata_dict) > 3
            software_flag = len(editing_software_detected) > 0
            evidence_found = software_flag or c2pa_info["c2pa_present"]

            execution_time = (time.perf_counter() - start_time) * 1000.0

            return ModuleResult(
                module_name=self.name,
                status=TaskStatus.COMPLETED,
                result={
                    "has_exif": has_exif,
                    "exif_tags_count": len(metadata_dict),
                    "tags": metadata_dict,
                    "editing_software_detected": list(set(editing_software_detected)),
                    "c2pa": c2pa_info,
                    "camera_make": metadata_dict.get("Make") or metadata_dict.get("Image Make"),
                    "camera_model": metadata_dict.get("Model") or metadata_dict.get("Image Model"),
                    "date_time": metadata_dict.get("DateTimeOriginal") or metadata_dict.get("EXIF DateTimeOriginal")
                },
                evidence_found=evidence_found,
                confidence=0.85 if software_flag else None,
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
                error_message=f"Metadata analysis error: {str(e)}",
                limitations=limitations
            )
