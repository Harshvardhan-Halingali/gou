# IMAGE TRACE — Digital Authenticity & Forensic Investigation Workbench

IMAGE TRACE is a modular, high-performance digital forensic workbench built with **FastAPI**, **OpenCV**, **ImageHash**, **OpenCLIP**, and local vision/audio/video transformers. It empowers researchers, investigative journalists, OSINT practitioners, and forensic analysts to investigate media authenticity, detect synthetic AI manipulation and deepfakes across images, video, and audio, extract provenance metadata, and trace near-duplicates.

---

## Key Capabilities & Forensic Engine

1. **Multi-Algorithm Cryptographic & Perceptual Hashing**
   - **SHA-256**: Bitwise exact duplicate detection.
   - **pHash**: Discrete Cosine Transform (DCT) perceptual similarity.
   - **dHash**: Gradient and difference comparison.
   - **aHash**: Average luminance profile.
   - **wHash**: Haar Discrete Wavelet Transform (DWT) frequency decomposition.
   - **ColorHash**: Color space HSV distribution binning.
   - **Crop-Resistant Hash**: $3\times 3$ sliding spatial grid hash.

2. **Tamper & Manipulation Analysis**
   - **Error Level Analysis (ELA)**: Dynamic JPEG recompression difference heatmap (Quality 95, 15x amplification).
   - **Noise Variance Inconsistency**: Local Laplacian sliding-window variance check to expose spliced regions.
   - **Copy-Move Forgery Detection**: ORB keypoint self-matching with RANSAC cluster validation.

3. **AI-Generated Image & Deepfake Detection**
   - Local Vision Transformer classifier (`Organika/sdxl-detector`) running on CPU with zero paid API dependencies.
   - 2D Fast Fourier Transform (FFT) high-frequency spectrum analysis for diffusion and GAN radial artifact detection.

4. **Dual Video Deepfake & AI-Generation Detection**
   - **DeMamba (X-CLIP + Mamba)**: Temporal and spatial frequency signature inspection for synthetic generative video (Sora, Gen-2, Pika, etc.).
   - **GenD (CLIP-L/14)**: Generalized facial deepfake and reenactment artifact detection.
   - **YuNet Face Tracking**: Real-time neural face detection and bounding box alignment.

5. **Audio Deepfake & Voice Synthesis Detection**
   - Deepfake audio detection utilizing acoustic frequency representations and classification pipelines (`Speech-Arena DF Arena 1B`).

6. **Context & OSINT Analysis Engine**
   - Automated visual entity recognition, landmark discovery, reverse image search scaffolding, and historical provenance cross-referencing.

7. **Provenance & Metadata Inspection**
   - Comprehensive EXIF & XMP extraction via `Pillow` and `exifread`.
   - Automated detection of editing software tags (Photoshop, GIMP, Canva, Stable Diffusion WebUI, ComfyUI).
   - Coalition for Content Provenance and Authenticity (**C2PA**) / JUMBF header verification.

8. **Semantic Reverse Tracing & Local Keypoint Homography**
   - **OpenCLIP (`ViT-B-32`)**: Local semantic visual embedding extraction against indexed reference archives.
   - **OpenCV SIFT/ORB**: Geometric homography verification with Lowe's ratio test ($0.75$) and RANSAC inlier filtering.

9. **Social Media Connector Scaffolding**
   - Modular ingestion connectors for **Instagram** (Meta Graph API), **Facebook Pages**, and **Telegram Bot** (`getFile`).
   - Graceful status reporting (`NOT_CONFIGURED` when credentials are absent; never fabricates mock data).

10. **Real-Time Live Progress Dashboard**
    - Server-Sent Events (SSE) streaming live execution states, individual task duration in milliseconds, and real completion percentages.

---

## Project Structure

```
├── app/
│   ├── config.py                # System settings and upload boundaries
│   ├── main.py                  # FastAPI server & route handlers
│   ├── core/
│   │   ├── base_module.py       # Abstract Base Class (ForensicModule)
│   │   ├── orchestrator.py      # Multithreaded pipeline & SSE publisher
│   │   └── security.py          # Magic byte inspection & file sanitization
│   ├── modules/
│   │   ├── hashing_engine.py    # 7-algorithm image fingerprinting
│   │   ├── metadata_engine.py   # EXIF, XMP, and C2PA manifest checking
│   │   ├── manipulation_ela.py  # ELA, noise variance & copy-move detection
│   │   ├── sift_engine.py       # OpenCV SIFT/ORB keypoints & homography
│   │   ├── reverse_engine.py    # OpenCLIP embedding & vector search
│   │   ├── ai_detector.py       # Hugging Face ViT & 2D FFT spectral analysis
│   │   ├── audio_detector.py    # Audio deepfake & synthetic voice detection
│   │   ├── video_detector.py    # Dual video detector orchestrator (DeMamba + GenD)
│   │   ├── context_osint_engine.py # Contextual OSINT analysis engine
│   │   └── video_network/       # Deep learning video network architectures
│   │       ├── demamba.py       # DeMamba X-CLIP + Mamba model
│   │       ├── gend.py          # GenD CLIP-L/14 model architecture
│   │       ├── gend_config.json # GenD configuration
│   │       ├── xception.py      # FaceForensics Xception network
│   │       └── mesonet.py       # MesoNet facial classification
│   ├── connectors/
│   │   ├── base_connector.py    # Social platform ingestion abstraction
│   │   ├── instagram_connector.py
│   │   ├── facebook_connector.py
│   │   └── telegram_connector.py
│   ├── database/
│   │   ├── connection.py        # SQLite WAL mode connection pool
│   │   ├── models.py            # Pydantic and data schemas
│   │   └── repository.py        # Persistent evidence store
│   └── static/
│       ├── index.html           # Dark-mode forensic dashboard
│       ├── css/style.css        # Professional forensic UI styling
│       └── js/app.js            # SSE streaming listener & dossier rendering
├── corpus/
│   └── verified_reference/      # Local image archive for reverse indexing
├── data/
│   ├── uploads/                 # Temporary ingest buffer (.gitignored)
│   ├── reports/                 # Generated ELA heatmaps (.gitignored)
│   └── models/                  # Offline model weights directory (.gitignored)
├── tests/
│   ├── test_pipeline.py         # Forensic engine unit tests
│   ├── test_api.py              # API route integration tests
│   ├── test_video_pipeline.py   # Video deepfake integration tests
│   ├── test_dual_video_detector.py # GenD + DeMamba unit verification
│   └── fixtures/                # Lightweight test media fixtures
├── .env.example
├── .gitignore
├── requirements.txt
├── download_models.py           # Pre-cache & download AI models
└── run.py                       # Server launch entry point
```

---

## Quickstart

### 1. Install Dependencies
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

### 2. Check and Pre-cache Models
```bash
# Check status of local model checkpoints
python download_models.py --check

# Pre-cache image models (Organika/sdxl-detector, OpenCLIP)
python download_models.py
```

### 3. Launch the Application
```bash
# Start the FastAPI server
python run.py
```
Open your browser and navigate to:
```
http://127.0.0.1:8080
```

### 4. Run Test Suite
```bash
python tests/test_pipeline.py
python tests/test_api.py
```

---

## Configuration (`.env`)

Optional social platform and server configuration:
```ini
HOST=127.0.0.1
PORT=8080
RELOAD=false

INSTAGRAM_ACCESS_TOKEN=
INSTAGRAM_USER_ID=

FB_PAGE_ACCESS_TOKEN=
FB_PAGE_ID=

TELEGRAM_BOT_TOKEN=
```
If connector tokens are left unset, the platform connectors report status `NOT_CONFIGURED` without impacting the local forensic pipeline.
