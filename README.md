# Smart Attendance System

An enterprise-grade, real-time classroom attendance platform powered by computer vision, deep learning biometrics, WebSocket streaming, and a high-performance FastAPI backend.

Rather than relying on manual, point-in-time roll calls that only tell if a student was seated at a specific minute, this system continuously detects and tracks students throughout the class period, computes effective duration and attendance percentages, accounts for temporary absences, and streams real-time telemetry to an interactive instructor dashboard.

---

## 1. Overview & Problem Statement

### The Problem
* Traditional roll calls consume between 5 to 15 minutes of instructional time per class session.
* Conventional attendance methods only verify presence at the moment of the call, failing to reflect whether a student arrived late, stepped out, or left early.
* Paper sheets and manual logs are prone to proxy attendance, human recording errors, and lack auditable timestamps.

### The Solution
* **Continuous Presence Tracking:** Uses deep learning person detection (YOLOv8) combined with temporal multi-object tracking (ByteTrack) to follow individuals inside the classroom.
* **Biometric Facial Recognition:** Employs InsightFace deep convolutional embeddings (512-dimensional feature vectors) to verify student identities when faces are visible.
* **Stateful Presence Intervals:** Automatically tracks entrance timestamps, exit timestamps, and continuous classroom presence while applying a configurable tolerance window (e.g., 15–45 seconds) to prevent false departures.
* **Real-Time Instructor Dashboard:** Streams attendance transitions, glowing presence counters, and live activity feeds via WebSockets without page reloads.
* **Dynamic Camera Switching:** Instructors can switch video sources (e.g., laptop built-in webcam to an external wide-angle USB classroom camera) directly from the web dashboard on the fly.
* **Automated Audit Reports:** Concluding a class locks all active intervals and exports a comprehensive, auditable CSV summary report.

---

## 2. Architecture & Pipeline

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                            VISION SERVICE                                   │
│                                                                             │
│  [ Video Source ]  ──>  [ OpenCV ]  ──>  [ YOLOv8 Person Detection ]       │
│  (Built-in / USB)         Capture             (Bounding Boxes)              │
│                              │                        │                     │
│                              ▼                        ▼                     │
│                      [ Dynamic Camera ]       [ ByteTrack Tracker ]         │
│                        Hot-Swapping            (Track IDs: #1, #2...)       │
│                                                       │                     │
│                                                       ▼                     │
│                                             [ InsightFace Biometrics ]      │
│                                             (512-D Cosine Similarity)       │
│                                                       │                     │
│                                                       ▼                     │
│                                             [ Attendance Manager ]          │
│                                             (Timeouts & Presence Logic)     │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Async HTTP Event Ingest
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BACKEND PLATFORM                                  │
│                                                                             │
│                      [ FastAPI ASGI Engine (Uvicorn) ]                      │
│                                      │                                      │
│               ┌──────────────────────┴──────────────────────┐               │
│               ▼                                             ▼               │
│     [ Database & Persistence ]                    [ WebSocket Manager ]     │
│      SQLAlchemy ORM Layer                         Bi-directional Pub/Sub    │
│      SQLite (default) / PostgreSQL                          │               │
│      - Biometric Embeddings                                 ▼               │
│      - Presence Intervals                     [ Real-Time Instructor Web ]  │
│      - Audit Events Log                       - Live Dashboard (/dashboard) │
│      - CSV Reports Generator                  - Face Kiosk (/enroll)        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Key Capabilities & Features

1. **Multi-Camera Selection & Dynamic Switching:**
   * Detects available system cameras (FaceTime HD, external USB webcams, capture cards).
   * Allows selecting the camera from the session launch banner or switching live during an ongoing class.
   * Seamlessly re-initializes OpenCV streams without stopping or restarting the vision pipeline.

2. **Continuous Attendance Tracking & Interval Engine:**
   * Records initial arrival time (`first_seen_at`) and latest detection (`last_seen_at`).
   * Opens and closes distinct continuous presence intervals (`started_at`, `ended_at`).
   * Computes exact classroom presence in seconds and calculates live attendance percentage against total elapsed class time.

3. **Dual Facial Enrollment Workflows:**
   * **Interactive Web Enrollment Station (`/enroll`):** Students enter their name and ID, view a live camera preview with an alignment guide, and capture a rapid 3-to-5 photo burst with flash feedback. Includes automatic anti-duplication protection (rejects existing student IDs or faces matching $\ge 0.72$ cosine similarity).
   * **Batch Enrollment Script (`scripts/bulk_enroll.py`):** Automatically processes entire directories of student photos organized in subfolders (`Name_Surname_StudentID/`) or loose image files.

4. **Zero-Downtime Biometric Hot-Reloading:**
   * The computer vision pipeline dynamically inspects the database for newly enrolled student embeddings every second, refreshing its in-memory vector index without needing a restart.

5. **Auditable Instructor Overrides:**
   * Instructors can manually override student attendance status (e.g. `PRESENT`, `ABSENT`, `LEFT`) directly from the dashboard table, requiring an auditable justification note saved in `manual_corrections`.

6. **Automatic CSV Summary Export:**
   * Concluding a class locks all open presence intervals, tallies average cohort attendance, and automatically outputs a downloadable CSV summary report to `outputs/`.

---

## 4. Tech Stack

| Component | Technologies Used |
| :--- | :--- |
| **Backend API** | Python 3.12, FastAPI, Uvicorn, Pydantic v2, Python-Multipart |
| **Real-Time Streaming** | WebSockets (Native ASGI), Asyncio Event Loops |
| **Computer Vision & AI** | OpenCV, Ultralytics YOLOv8 (`yolov8n`), ByteTrack, InsightFace (`buffalo_l`), ONNX Runtime, NumPy, Pillow |
| **Database & ORM** | SQLAlchemy 2.0, SQLite (default plug-and-play), PostgreSQL ready via `psycopg2-binary` |
| **Frontend Interfaces** | Responsive HTML5, Tailwind CSS, Native SVGs, Inter & JetBrains Mono typography, Vite / React 18 base |
| **Containerization** | Docker, Docker Compose (Multi-stage/Slim Linux) |

---

## 5. Deployment & Getting Started

You can run the system using **Docker Compose** (recommended for cross-platform containerized deployments) or **natively on the host machine** (ideal for local webcam access on macOS or Windows).

### Option A: Docker Compose (Containerized Backend & Dashboard)

Run the backend API, database, and real-time dashboard inside an isolated Docker container with zero local dependency headaches:

```bash
# 1. Clone the repository
git clone https://github.com/Josch108/attendace-app.git
cd attendace-app

# 2. Build and start services via Docker Compose
docker compose up --build
```

* The **Live Instructor Dashboard** will be available at: **[http://localhost:8000/dashboard](http://localhost:8000/dashboard)**
* The **Student Face Enrollment Station** will be available at: **[http://localhost:8000/enroll](http://localhost:8000/enroll)**
* Interactive OpenAPI Swagger documentation: **[http://localhost:8000/docs](http://localhost:8000/docs)**

> **Persistent Volumes:** The database file (`attendance.db`), biometric image storage (`data/`), and exported reports (`outputs/`) are mounted directly from your host directory, ensuring all data persists across container restarts.

#### Running the Vision Pipeline with Docker Backend
If running Docker Desktop on macOS/Windows (where direct USB webcam pass-through to containers is restricted), start the backend via Docker and run the vision pipeline locally on your host:

```bash
# In your host terminal:
python vision/main.py --backend-url http://localhost:8000 --source 0
```

*(On native Linux hosts, you can pass `/dev/video0` directly into the container using `docker compose --profile vision up`)*.

---

### Option B: Local Native Startup (Single-Command All-in-One)

You can run the complete system (Backend server + Browser Dashboard + Vision tracking with webcam) using a single command:

#### Prerequisites
* Python 3.10+ (Python 3.12 recommended)
* A working webcam or external USB camera

#### 1. Setup Virtual Environment
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### 2. Launch Everything in One Step
```bash
./run.sh
```
*(Alternatively on Windows or without bash: `python run.py`)*

**What this single command does automatically:**
1. Starts the FastAPI backend server on port `8000`.
2. Awaits the `/health` check until services are online.
3. Automatically opens your default web browser to the **Instructor Live Dashboard**.
4. Starts the Vision tracking pipeline in standby mode with your webcam.
5. Performs a clean shutdown of all background processes when you press `q` in the video window or `Ctrl+C` in the terminal.

---

### Option C: Running Services Individually (Modular Development)

For debugging or distributed setups across different machines:

```bash
# Terminal 1: Backend Server & WebSockets
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Vision Tracking Pipeline
python vision/main.py --source 0 --group "Group A" --backend-url http://localhost:8000
```

---

## 6. Student Enrollment Guide

To recognize students, the system needs their facial biometric vectors stored in the database. You can register students using either method:

### Method 1: Bulk Directory Import (Recommended for Existing Photos)
Organize your student photos into the `data/incoming_photos/` directory:

```text
data/incoming_photos/
├── JOHN_DOE_2309001/
│   ├── photo1.jpg
│   └── photo2.png
└── JANE_SMITH_2309002/
    ├── img_01.jpg
    └── img_02.jpg
```
*Note: Folder names can follow `SURNAME_NAME_STUDENTID` or `STUDENTID_NAME`. The script automatically parses the numeric student ID and the student's full name.*

Run the bulk enrollment script:
```bash
python scripts/bulk_enroll.py --folder data/incoming_photos --group "Group A"
```

### Method 2: Web Kiosk (`/enroll`)
1. Open **`http://localhost:8000/enroll`** in your browser.
2. Select your video capture device (built-in or external).
3. Enter the student's **Full Name** and **Student ID**.
4. Click **"Capture Photos"**: A 3-second countdown initiates, followed by a rapid burst of 3 to 5 photos with flash feedback.
5. Review the captured thumbnails and click **"Confirm & Enroll"**.
6. The system extracts InsightFace embeddings, verifies that no duplicate face already exists, and saves the biometric record.

### Inspecting Enrolled Students
To list all registered students, their assigned academic groups, and the number of active biometric vectors in the database:
```bash
python scripts/list_students.py
```

---

## 7. Configuration & Environment Variables

Create a `.env` file in the root directory (or copy from `.env.example`) to customize configuration parameters:

```bash
cp .env.example .env
```

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `PROJECT_NAME` | `Smart Attendance System` | Application display name |
| `ENVIRONMENT` | `development` | Environment mode (`development` / `production`) |
| `DATABASE_URL` | `sqlite:///attendance.db` | Database connection string (SQLite or PostgreSQL) |
| `STORAGE_PATH` | `data/students` | Local directory where enrolled student photos are stored |
| `OUTPUTS_DIR` | `outputs` | Directory where attendance CSV export files are saved |
| `ABSENCE_TIMEOUT_SECONDS` | `15` | Seconds of non-detection before marking a student absent/left |
| `FACE_MATCH_THRESHOLD` | `0.50` | Cosine similarity threshold for facial verification ($0.0 - 1.0$) |
| `FACE_CONFIRMATION_COUNT` | `3` | Consecutive facial confirmations required before locking identity |
| `MODEL_VERSION` | `insightface/buffalo_l` | Biometric facial model tag for audit logs |

---

## 8. Directory Structure

```text
attendance_app/
├── backend/
│   ├── app/
│   │   ├── api/             # REST API routers (students, sessions, events, cameras)
│   │   ├── db/              # SQLAlchemy database session and Base models
│   │   ├── models/          # Relational entities (Student, ClassSession, Record, etc.)
│   │   ├── schemas/         # Pydantic validation DTOs
│   │   ├── services/        # Face embedding extractor, CSV reporter, camera manager
│   │   ├── static/          # Enterprise frontend dashboards (dashboard.html, enroll.html)
│   │   ├── websockets/      # Real-time WebSocket connection manager and event broadcaster
│   │   ├── config.py        # Centralized settings loader (.env)
│   │   └── main.py          # FastAPI application entrypoint
│   └── requirements.txt     # Backend-specific requirements
├── vision/
│   ├── camera.py            # OpenCV camera stream wrapper with dynamic hot-swapping
│   ├── detector_tracker.py  # YOLOv8 person detector + ByteTrack temporal tracking
│   ├── face_recognizer.py   # InsightFace cosine similarity engine with hot-reloading
│   ├── attendance_manager.py# Stateful presence interval and timeout calculator
│   ├── attendance_client.py # Non-blocking asynchronous client to FastAPI backend
│   └── main.py              # Main vision pipeline with graphical video overlay
├── scripts/
│   ├── bulk_enroll.py       # Batch enrollment script for photo directory trees
│   ├── enroll_student.py    # CLI single-student enrollment utility
│   ├── list_students.py     # Database inspector for enrolled students and vectors
│   ├── webcam_enroll.py     # Desktop camera enrollment kiosk
│   └── init_db.py           # Database table initialization utility
├── data/
│   ├── incoming_photos/     # Staging directory for bulk student enrollment
│   └── students/            # Managed storage for enrolled reference facial crops
├── outputs/                 # Exported attendance session CSV audit reports
├── frontend/                # Optional React 18 + Vite client scaffold
├── Dockerfile               # Production container image definition
├── docker-compose.yml       # Multi-service orchestration configuration
├── .dockerignore            # Build context exclusions
├── run.sh                   # Single-command Bash launcher
├── run.py                   # Single-command Python cross-platform launcher
├── requirements.txt         # Consolidated Python dependencies
└── README.md                # Project documentation
```

---

## 9. Security, Privacy & Ethics

* **Biometric Vector Storage:** The system relies primarily on mathematical representations (512-dimensional floating-point vectors) rather than raw photographs for facial comparison.
* **Non-Persistent Video:** Real-time classroom video streams are processed in volatile memory for detection and tracking. Video is not recorded or stored to disk unless explicitly commanded with the `--output` flag.
* **Audit Trail:** Every manual status correction made by an instructor is permanently logged with timestamps, instructor IDs, and obligatory justification reasons.
* **Anti-Spoofing & Deduplication:** Prohibits duplicate enrollment by checking cosine distance against all previously enrolled biometric vectors.

---

## 10. License

This project is licensed under the [MIT License](LICENSE).
