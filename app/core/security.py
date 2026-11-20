import os
import re
from pathlib import Path
from typing import Tuple

MAGIC_NUMBERS = {
    b"\xFF\xD8\xFF": ("image/jpeg", ".jpg"),
    b"\x89PNG\r\n\x1a\n": ("image/png", ".png"),
    b"RIFF": ("image/webp", ".webp"),  # Starts with RIFF and has WEBP at offset 8
    b"II*\x00": ("image/tiff", ".tiff"),
    b"MM\x00*": ("image/tiff", ".tiff"),
    b"BM": ("image/bmp", ".bmp"),
}

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and invalid characters."""
    filename = os.path.basename(filename)
    filename = re.sub(r"[^\w\.\-]", "_", filename)
    if not filename or filename.startswith("."):
        filename = f"upload_{filename}"
    return filename

def validate_image_file(file_path: str, max_size_bytes: int = 25 * 1024 * 1024) -> Tuple[bool, str, str]:
    """
    Validates file exists, checks size, and verifies genuine image magic bytes.
    Returns: (is_valid, mime_type, error_message)
    """
    path = Path(file_path)
    if not path.is_file():
        return False, "", "File does not exist on disk."
    
    file_size = path.stat().st_size
    if file_size == 0:
        return False, "", "File is empty (0 bytes)."
    
    if file_size > max_size_bytes:
        return False, "", f"File size ({file_size} bytes) exceeds limit ({max_size_bytes} bytes)."
    
    # Read first 32 bytes for magic number identification
    with open(path, "rb") as f:
        header = f.read(32)
        
    for magic, (mime, _) in MAGIC_NUMBERS.items():
        if header.startswith(magic):
            if magic == b"RIFF":
                if len(header) >= 12 and header[8:12] == b"WEBP":
                    return True, "image/webp", ""
                continue
            return True, mime, ""
            
    return False, "", "File failed magic byte header validation; not a supported image format."

def validate_audio_file(file_path: str, max_size_bytes: int = 50 * 1024 * 1024) -> Tuple[bool, str, str]:
    """
    Validates audio file existence, size, header magic bytes, and readable audio stream.
    Returns: (is_valid, mime_type, error_message)
    """
    path = Path(file_path)
    if not path.is_file():
        return False, "", "Audio file does not exist on disk."
    
    file_size = path.stat().st_size
    if file_size == 0:
        return False, "", "Audio file is empty (0 bytes)."
        
    if file_size > max_size_bytes:
        return False, "", f"Audio file size ({file_size} bytes) exceeds limit ({max_size_bytes} bytes)."

    # Read first 32 bytes for magic number identification
    with open(path, "rb") as f:
        header = f.read(32)

    mime_type = None
    if header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WAVE":
        mime_type = "audio/wav"
    elif header.startswith(b"ID3") or header.startswith(b"\xFF\xFB") or header.startswith(b"\xFF\xF3") or header.startswith(b"\xFF\xF2"):
        mime_type = "audio/mpeg"
    elif header.startswith(b"OggS"):
        mime_type = "audio/ogg"
    elif header.startswith(b"fLaC"):
        mime_type = "audio/flac"
    elif len(header) >= 8 and header[4:8] == b"ftyp":
        mime_type = "audio/mp4"
    elif header.startswith(b"\xFF\xF1") or header.startswith(b"\xFF\xF9"):
        mime_type = "audio/aac"

    # 1. Verify decodeable with PyAV (handles AAC, M4A, OPUS, MP3, WAV, FLAC, WhatsApp audio)
    try:
        import av
        container = av.open(file_path)
        audio_streams = [s for s in container.streams if s.type == "audio"]
        print(f"[SECURITY] PyAV opened {file_path}. Found {len(audio_streams)} audio streams: {[s.codec_context.name for s in audio_streams]}")
        if not audio_streams:
            container.close()
            return False, "", "Audio file contains no audio streams."
        
        # Verify decode of at least one packet/frame with packet error tolerance
        decoded_any = False
        for packet in container.demux(audio_streams[0]):
            try:
                for frame in packet.decode():
                    if frame.samples > 0:
                        decoded_any = True
                        break
            except Exception:
                continue
            if decoded_any:
                break
        container.close()

        if decoded_any:
            detected_mime = mime_type or f"audio/{audio_streams[0].codec_context.name or 'aac'}"
            print(f"[SECURITY] PyAV successfully decoded frame. MIME: {detected_mime}")
            return True, detected_mime, ""
        else:
            print(f"[SECURITY] PyAV decoded zero samples from stream {audio_streams[0]}")
    except Exception as av_err:
        print(f"[SECURITY] PyAV open/decode exception on {file_path}: {type(av_err).__name__}: {av_err}")

    # 2. Fallback to soundfile
    try:
        import soundfile as sf
        info = sf.info(file_path)
        if info.frames == 0:
            return False, "", "Audio file contains zero audio frames."
        if info.duration < 0.1:
            return False, "", "Audio file duration is too short (< 0.1 seconds)."
        detected_mime = mime_type or "audio/wav"
        return True, detected_mime, ""
    except Exception:
        pass

    # 3. Fallback to librosa
    try:
        import librosa
        dur = librosa.get_duration(path=file_path)
        if dur < 0.1:
            return False, "", "Audio file duration is too short (< 0.1 seconds)."
        detected_mime = mime_type or "audio/mpeg"
        return True, detected_mime, ""
    except Exception as e:
        if mime_type:
            return False, mime_type, f"Audio file stream corrupted or unreadable: {str(e)}"
        return False, "", f"Unsupported or corrupted audio format: {str(e)}"

def validate_video_file(file_path: str, max_size_bytes: int = 100 * 1024 * 1024) -> Tuple[bool, str, str]:
    """
    Validates video file existence, size, header magic bytes, and stream decodeability.
    Returns: (is_valid, mime_type, error_message)
    """
    path = Path(file_path)
    if not path.is_file():
        return False, "", "Video file does not exist on disk."
    
    file_size = path.stat().st_size
    if file_size == 0:
        return False, "", "Video file is empty (0 bytes)."
        
    if file_size > max_size_bytes:
        return False, "", f"Video file size ({file_size} bytes) exceeds limit ({max_size_bytes} bytes)."

    with open(path, "rb") as f:
        header = f.read(32)

    mime_type = None
    if len(header) >= 8 and (header[4:8] == b"ftyp" or header[4:8] == b"moov" or header[4:8] == b"mdat"):
        mime_type = "video/mp4"
    elif header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"AVI ":
        mime_type = "video/x-msvideo"
    elif header.startswith(b"\x1a\x45\xdf\xa3"):
        mime_type = "video/webm"

    # Verify video stream decodeability using OpenCV
    try:
        import cv2
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            cap.release()
            return False, "", "Unable to open video stream; corrupted or unsupported codec."
            
        ret, frame = cap.read()
        cap.release()
        
        if not ret or frame is None or frame.size == 0:
            return False, "", "Video contains zero decodeable video frames."
            
        return True, mime_type or "video/mp4", ""
    except Exception as e:
        return False, "", f"Video stream verification error: {str(e)}"
