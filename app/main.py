import uuid
import os
import shutil
import asyncio
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database.connection import init_db
from app.database.repository import ForensicRepository
from app.core.security import validate_image_file, validate_audio_file, validate_video_file, sanitize_filename
from app.core.orchestrator import orchestrator
from app.modules.audio_detector import audio_detector
from app.modules.video_detector import video_detector

from contextlib import asynccontextmanager

# Initialize SQLite database and pre-warm models on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("[STARTUP] Pre-warming local AI detection and feature models...")
    for mod in orchestrator.modules:
        if hasattr(mod, "_lazy_init"):
            try:
                mod._lazy_init()
            except Exception as e:
                print(f"[STARTUP] Warning warming {mod.name}: {e}")
    try:
        print("[STARTUP] Pre-warming DF Arena 1B Audio Deepfake Detector...")
        audio_detector._lazy_init()
        print("[STARTUP] DF Arena 1B Audio Deepfake Detector ready.")
    except Exception as e:
        print(f"[STARTUP] Notice: Audio detector initialization deferred: {e}")
    try:
        print("[STARTUP] Pre-warming Dual Video Detector (GenD + DeMamba)...")
        video_detector._lazy_init()
        print("[STARTUP] Dual Video Detector (GenD + DeMamba) ready.")
    except Exception as e:
        print(f"[STARTUP] Notice: Video detector initialization deferred: {e}")
    print("[STARTUP] Forensic engine models warmed up and ready in memory.")
    yield

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Modular Digital Authenticity & Forensic Investigation Workbench",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static/css", StaticFiles(directory=settings.BASE_DIR / "app" / "static" / "css"), name="css")
app.mount("/static/js", StaticFiles(directory=settings.BASE_DIR / "app" / "static" / "js"), name="js")
app.mount("/static/reports", StaticFiles(directory=settings.REPORTS_DIR), name="reports")
app.mount("/static/uploads/audio", StaticFiles(directory=settings.AUDIO_UPLOADS_DIR), name="audio_uploads")
app.mount("/static/uploads/video", StaticFiles(directory=settings.VIDEO_UPLOADS_DIR), name="video_uploads")
app.mount("/static/uploads", StaticFiles(directory=settings.UPLOADS_DIR), name="uploads")

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    index_file = settings.BASE_DIR / "app" / "static" / "index.html"
    if not index_file.is_file():
        raise HTTPException(status_code=404, detail="Dashboard UI not found.")
    return FileResponse(index_file)

@app.post("/api/v1/investigate")
async def start_investigation(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Receives image, validates magic bytes, and launches forensic investigation."""
    job_id = str(uuid.uuid4())
    safe_filename = sanitize_filename(file.filename or "uploaded_image.jpg")
    destination = settings.UPLOADS_DIR / f"{job_id}_{safe_filename}"

    # Save to disk safely
    try:
        with open(destination, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save upload: {str(e)}")

    # Validate Magic Bytes & Size
    is_valid, mime_type, error_msg = validate_image_file(str(destination), settings.MAX_UPLOAD_SIZE_BYTES)
    if not is_valid:
        if destination.exists():
            destination.unlink()
        raise HTTPException(status_code=400, detail=f"Image validation rejected: {error_msg}")

    file_size = destination.stat().st_size
    repo = ForensicRepository()
    repo.create_job(job_id, safe_filename, str(destination), mime_type, file_size)

    # Launch pipeline in background task
    background_tasks.add_task(orchestrator.run_pipeline, job_id, str(destination), safe_filename)

    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "filename": safe_filename,
            "mime_type": mime_type,
            "file_size": file_size,
            "status": "QUEUED",
            "stream_url": f"/api/v1/stream/{job_id}",
            "report_url": f"/api/v1/report/{job_id}",
            "image_url": f"/static/uploads/{job_id}_{safe_filename}"
        }
    )

@app.get("/api/v1/stream/{job_id}")
async def stream_analysis_progress(job_id: str):
    """Server-Sent Events (SSE) live progress channel."""
    queue = orchestrator.register_stream(job_id)

    async def event_generator():
        try:
            while True:
                data = await queue.get()
                yield f"data: {json.dumps(data)}\n\n"
                if data.get("step") == "FINAL_REPORT" or data.get("status") == "FAILED":
                    break
        finally:
            orchestrator.unregister_stream(job_id)

    import json
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/api/v1/report/{job_id}")
async def get_report(job_id: str):
    """Fetches the compiled forensic dossier."""
    dossier = orchestrator.generate_dossier(job_id)
    if "error" in dossier:
        raise HTTPException(status_code=404, detail="Forensic report not found for specified Job ID.")
    return JSONResponse(content=dossier)

@app.get("/api/v1/connectors/status")
async def get_connector_statuses():
    """Returns real configuration status of all social platform connectors."""
    statuses = []
    for conn in orchestrator.connectors:
        statuses.append({
            "platform": conn.platform_name,
            "configured": conn.is_configured(),
            "status": "READY" if conn.is_configured() else "NOT_CONFIGURED",
            "details": "Ready for authorized ingestion" if conn.is_configured() else "Tokens not provided in .env."
        })
    return JSONResponse(content={"connectors": statuses})

@app.post("/api/v1/reference/upload")
async def upload_reference_corpus_image(file: UploadFile = File(...)):
    """Allows uploading verified reference images to the local reverse-search corpus."""
    safe_name = sanitize_filename(file.filename or "ref.jpg")
    dest = settings.CORPUS_DIR / safe_name
    with open(dest, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    is_valid, mime, err = validate_image_file(str(dest))
    if not is_valid:
        if dest.exists():
            dest.unlink()
        raise HTTPException(status_code=400, detail=f"Reference image invalid: {err}")
        
    return JSONResponse(content={"status": "INDEXED", "filename": safe_name})

@app.post("/api/v1/detect/audio")
@app.post("/api/detect/audio")
async def detect_audio_deepfake(file: UploadFile = File(...)):
    """
    Receives an audio file (WAV, MP3, OGG, FLAC, M4A), validates headers and duration,
    and runs the fine-tuned DF Arena 1B model (fc5 restored) to detect AI synthesis / voice cloning.
    """
    safe_filename = sanitize_filename(file.filename or "audio_sample.wav")
    dest_path = settings.AUDIO_UPLOADS_DIR / f"{uuid.uuid4()}_{safe_filename}"

    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Failed to save uploaded audio: {str(e)}"}
        )

    # Validate audio file format, size, and readable stream
    file_bytes_on_disk = dest_path.stat().st_size if dest_path.exists() else 0
    print(f"[AUDIO UPLOAD] Received: {safe_filename}, bytes on disk: {file_bytes_on_disk}")
    
    is_valid, mime_type, err_msg = validate_audio_file(str(dest_path), settings.MAX_AUDIO_UPLOAD_SIZE_BYTES)
    if not is_valid:
        print(f"[AUDIO VALIDATION REJECTED] File: {safe_filename}, Error: {err_msg}")
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": f"Invalid or unsupported audio file: {err_msg}"}
        )

    # Run inference with fine-tuned DF Arena 1B in executor
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, audio_detector.predict, str(dest_path))
        result["filename"] = safe_filename
        result["audio_url"] = f"/static/uploads/audio/{dest_path.name}"
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Audio inference failed: {str(e)}"}
        )

@app.post("/api/v1/detect/video")
@app.post("/api/detect/video")
async def detect_video_deepfake(file: UploadFile = File(...)):
    """
    Receives a video file (MP4, AVI, MOV, MKV, WebM), validates frames and codecs,
    and runs the HongguLiu FaceForensics++ Xception network to detect deepfake facial manipulation.
    """
    safe_filename = sanitize_filename(file.filename or "video_sample.mp4")
    dest_path = settings.VIDEO_UPLOADS_DIR / f"{uuid.uuid4()}_{safe_filename}"

    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Failed to save uploaded video: {str(e)}"}
        )

    file_bytes_on_disk = dest_path.stat().st_size if dest_path.exists() else 0
    print(f"[VIDEO UPLOAD] Received: {safe_filename}, bytes on disk: {file_bytes_on_disk}")

    is_valid, mime_type, err_msg = validate_video_file(str(dest_path), settings.MAX_VIDEO_UPLOAD_SIZE_BYTES)
    if not is_valid:
        print(f"[VIDEO VALIDATION REJECTED] File: {safe_filename}, Error: {err_msg}")
        if dest_path.exists():
            dest_path.unlink()
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": f"Invalid or unsupported video file: {err_msg}"}
        )

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, video_detector.predict, str(dest_path))
        result["filename"] = safe_filename
        result["video_url"] = f"/static/uploads/video/{dest_path.name}"
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Video deepfake inference failed: {str(e)}"}
        )
