import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings:
    APP_NAME: str = "IMAGE TRACE"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Storage Paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    UPLOADS_DIR: Path = BASE_DIR / "data" / "uploads"
    REPORTS_DIR: Path = BASE_DIR / "data" / "reports"
    CORPUS_DIR: Path = BASE_DIR / "corpus" / "verified_reference"
    DB_PATH: Path = BASE_DIR / "data" / "image_trace.db"
    AUDIO_MODELS_DIR: Path = BASE_DIR / "data" / "models" / "audio"
    AUDIO_UPLOADS_DIR: Path = BASE_DIR / "data" / "uploads" / "audio"
    VIDEO_MODELS_DIR: Path = BASE_DIR / "data" / "models" / "video"
    VIDEO_UPLOADS_DIR: Path = BASE_DIR / "data" / "uploads" / "video"
    
    # Audio Deepfake Detection Configuration
    AUDIO_MODEL_ID: str = "Speech-Arena-2025/DF_Arena_1B_V_1"
    AUDIO_CHECKPOINT_PATH: Path = BASE_DIR / "data" / "models" / "audio" / "DF_Arena_Finetuned_Final.pt"
    AUDIO_SAMPLE_RATE: int = 16000
    MAX_AUDIO_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    MAX_AUDIO_DURATION_SECONDS: float = 300.0  # 5 minutes
    ALLOWED_AUDIO_EXTENSIONS: set = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".opus"}
    
    # Dual Video Detection Configuration (GenD + DeMamba)
    # Model 1: DeMamba (X-CLIP + Mamba, GenVideo-100K) -> AI-Generated Video Detection
    DEMAMBA_MODEL_DIR: Path = BASE_DIR / "data" / "models" / "video" / "demamba"
    DEMAMBA_CHECKPOINT_PATH: Path = BASE_DIR / "data" / "models" / "video" / "demamba" / "best_acc.pth"
    DEMAMBA_STANDALONE_SCRIPT: Path = BASE_DIR / "data" / "models" / "video" / "demamba" / "eval_demamba_standalone.py"
    
    # Model 2: GenD CLIP-L/14 (WACV 2026, yermandy/gend) -> Deepfake Facial Manipulation Detection
    GEND_MODEL_DIR: Path = BASE_DIR / "data" / "models" / "video" / "gend"
    GEND_CHECKPOINT_PATH: Path = BASE_DIR / "data" / "models" / "video" / "gend" / "model.safetensors"
    GEND_CONFIG_PATH: Path = BASE_DIR / "data" / "models" / "video" / "gend" / "config.json"
    
    # Face Detector Configuration
    YUNET_FACE_MODEL: Path = BASE_DIR / "data" / "models" / "face" / "face_detection_yunet_2023mar.onnx"
    MAX_VIDEO_UPLOAD_SIZE_BYTES: int = 100 * 1024 * 1024  # 100 MB
    MAX_VIDEO_DURATION_SECONDS: float = 300.0  # 5 minutes
    ALLOWED_VIDEO_EXTENSIONS: set = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    
    # Upload limits
    MAX_UPLOAD_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB
    ALLOWED_EXTENSIONS: set = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp"}
    
    # Social Connector API Tokens (Optional - status will be NOT_CONFIGURED if empty)
    INSTAGRAM_ACCESS_TOKEN: str = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    INSTAGRAM_USER_ID: str = os.getenv("INSTAGRAM_USER_ID", "")
    FB_PAGE_ACCESS_TOKEN: str = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
    FB_PAGE_ID: str = os.getenv("FB_PAGE_ID", "")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

settings = Settings()

# Ensure directories exist
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
settings.CORPUS_DIR.mkdir(parents=True, exist_ok=True)
settings.AUDIO_MODELS_DIR.mkdir(parents=True, exist_ok=True)
settings.AUDIO_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
settings.VIDEO_MODELS_DIR.mkdir(parents=True, exist_ok=True)
settings.VIDEO_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
