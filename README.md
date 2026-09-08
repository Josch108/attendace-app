# Smart Attendance System - Database, Vision, WebSockets & Real-Time Dashboard

Classroom attendance tracking platform using computer vision (OpenCV + YOLOv8 + ByteTrack + InsightFace), WebSocket streaming, and a FastAPI + SQLAlchemy backend.

---

## ⚡ 1. Single-Command Startup (All-in-One)

You can launch the entire system (Backend server + Web Dashboard in browser + Camera Vision tracking) using **one single command** without opening multiple terminals:

```bash
./run.sh
```
*(Or alternatively: `./.venv/bin/python run.py`)*

### What this single command does:
1. **Starts the FastAPI Backend:** Launches the API and WebSocket engine on port `8000` in the background.
2. **Waits for Health Check:** Verifies the server is online and ready.
3. **Opens the Browser:** Automatically opens your default web browser to the **Instructor Live Dashboard** at `http://localhost:8000/dashboard`.
4. **Starts the Vision Pipeline:** Opens your webcam with YOLOv8 person detection and ByteTrack tracking, automatically linked to the active class session.
5. **Clean Shutdown:** Pressing **`q`** in the camera window or **`Ctrl+C`** in the terminal cleanly terminates all background processes without leaving zombie processes.

---

## 2. Instructor Live Dashboard (`/dashboard`)

The live dashboard connects directly to the backend via **WebSockets** (`/ws/class-sessions/{id}`) to stream real-time updates as the camera observes students:

1. **Session Controls:** Select academic cohort (e.g. *Group A*) and click **"Start Session"**. A running timer displays elapsed class time.
2. **Real-Time Metric Cards:**
   - **Enrolled:** Total students registered in the cohort.
   - **Present Now:** Glowing live counter of students inside the classroom.
   - **Absent / Left:** Students not yet seen or who stepped out past the absence timeout (45s).
   - **Avg. Attendance:** Progress bar and group percentage.
3. **Live Attendance Table:** Automatically shifts row colors and updates timestamps (`first_seen_at`, `last_seen_at`, `total_seconds`) when students are recognized.
4. **Chronological Event Feed:** Live stream of vision events (e.g. `10:15:02 - Josue Chan detected [PRESENT]`).
5. **Manual Overrides:** Teacher can click **"Edit"** on any student to override status with an auditable justification reason.
6. **Conclude Class:** Click **"End Class"** to lock all open intervals and finalize calculations.

---

## 3. Fast Student Face Enrollment (`/enroll`)

1. Step in front of the camera, enter **Full Name** and **Student ID (Matrícula)**.
2. Click **"Capture Photos"**: Triggers a 3-second countdown and takes a rapid burst of **3 to 5 photos** with camera flash.
3. Review thumbnails and click **"Confirm & Enroll"**.
4. **Anti-Duplication:** Automatically blocks duplicate student IDs and duplicate faces ($\ge 0.72$ similarity).
5. View, search, or delete enrolled students in the **Registered Students Directory** table.

Alternatively, run the desktop webcam kiosk from terminal:
```bash
./.venv/bin/python scripts/webcam_enroll.py
```

---

## 4. Manual / Individual Service Commands

If you ever want to run services in separate terminals:

```bash
# Terminal 1: Backend API & WebSockets
./.venv/bin/uvicorn app.main:app --reload --app-dir backend --port 8000

# Terminal 2: Vision Pipeline
./.venv/bin/python vision/main.py --source 0 --auto-session --group "Group A"
```

---

## 5. Database Architecture & Models

Dual compatibility via **SQLAlchemy**:
- **SQLite (default):** `attendance.db` in project root.
- **PostgreSQL:** Configure `DATABASE_URL` in `.env`.

### Relational Entities:
- `students`: Enrolled students (full name, student ID / roll number, active status).
- `face_embeddings`: Facial biometric vectors (512-dimensional float32 binary format), photo file path, model version, and quality score.
- `courses` & `groups`: Courses and academic cohorts.
- `enrollments`: Many-to-many relationship linking students to groups.
- `class_sessions`: Class sessions initiated by instructors.
- `attendance_records`: Summary record per student and session (status, first/last seen, seconds, percentage).
- `attendance_intervals`: Continuous presence intervals (`started_at`, `ended_at`, `close_reason`).
- `attendance_events`: Immutable audit log of vision and business events.
- `manual_corrections`: Teacher overrides and audit trail.
- `cameras`: Video capture sources.
- `users`: Teachers and administrators.

---

## 6. Utility Scripts

- **List registered students and embeddings:**
  ```bash
  ./.venv/bin/python scripts/list_students.py
  ```
- **Initialize or reset database tables:**
  ```bash
  ./.venv/bin/python scripts/init_db.py
  ```
