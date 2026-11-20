from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class AnalysisJobModel(BaseModel):
    id: str
    created_at: str
    status: str
    source_filename: str
    file_path: str
    mime_type: str
    file_size_bytes: int
    total_execution_time_ms: float = 0.0

class ImageHashesModel(BaseModel):
    job_id: str
    sha256: str
    phash: str
    dhash: str
    ahash: str
    whash: str
    colorhash: str
    crop_resistant_hash: Optional[str] = None

class IndexedImageModel(BaseModel):
    id: str
    source_platform: str
    external_media_id: Optional[str] = None
    source_url: Optional[str] = None
    account_identifier: Optional[str] = None
    publication_timestamp: Optional[str] = None
    file_path: str
    sha256: str
    phash: str

class EvidenceRecordModel(BaseModel):
    job_id: str
    module_name: str
    status: str
    evidence_found: bool
    confidence_score: Optional[float] = None
    raw_payload_json: str
    execution_time_ms: float
    error_message: Optional[str] = None

class FinalReportModel(BaseModel):
    job_id: str
    metadata: Dict[str, Any]
    fingerprints: Dict[str, Any]
    reverse_matches: List[Dict[str, Any]]
    forensic_integrity: Dict[str, Any]
    metadata_provenance: Dict[str, Any]
    ai_generation_detection: Dict[str, Any]
    social_sources: List[Dict[str, Any]]
    execution_summary: Dict[str, Any]
    verdict: Dict[str, Any]
