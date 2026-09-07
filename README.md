# Smart Attendance System - Database, Vision & Tracking

Real-time classroom attendance tracking platform using computer vision (OpenCV + YOLOv8 + ByteTrack + InsightFace) and a FastAPI + SQLAlchemy backend.

---

## 1. Database Architecture & Setup

The system utilizes **SQLAlchemy** with dual compatibility:
- **Local SQLite (default):** An `attendance.db` file is automatically generated in the project root for immediate development and local testing without external dependencies.
- **PostgreSQL:** For production or Docker deployments, configure `DATABASE_URL` in `.env`:
  ```env
  DATABASE_URL=postgresql://user:password@localhost:5432/attendance_db
  ```

### Relational Entities (12 tables):
- `students`: Enrolled students (full name, student ID / roll number, active status).
- `face_embeddings`: Facial biometric vectors (512-dimensional float32 binary format), photo file path, model version, and quality score.
- `courses` & `groups`: Courses and academic cohorts/groups.
- `enrollments`: Many-to-many relationship linking students to groups.
- `class_sessions`: Class sessions initiated by instructors.
- `attendance_records`: Summary record per student and session (presence status, first/last seen timestamps, accumulated presence seconds, percentage).
- `attendance_intervals`: Continuous presence intervals (`started_at`, `ended_at`, `close_reason`).
- `attendance_events`: Immutable, idempotent audit log of vision and business events.
- `manual_corrections`: Auditable log of teacher overrides and justifications.
- `cameras`: Video capture sources and classroom camera devices.
- `users`: Teachers and administrators.

---

## 2. Real-Time Vision & Tracking Pipeline

The `vision/` module implements continuous detection and identity tracking:

```text
Camera (OpenCV) ──▶ YOLOv8 (Persons) ──▶ ByteTrack (Temporal track_id)
                                                │
                                    InsightFace (Selective Extraction)
                                                │
                                    Cosine Similarity vs Registered Embeddings
                                                │
                                       AttendanceManager
                     (States: ABSENT -> PRESENT -> TEMPORARILY_MISSING -> LEFT)
```

### Running the Vision Pipeline:

1. **Using your webcam (default device index 0):**
   ```bash
   ./.venv/bin/python vision/main.py --source 0
   ```

2. **Using a video file for reproducible testing:**
   ```bash
   ./.venv/bin/python vision/main.py --source /path/to/test_video.mp4
   ```

3. **Configurable parameters & CLI flags:**
   - `--conf 0.40`: YOLOv8 person detection confidence threshold.
   - `--threshold 0.50`: Cosine similarity threshold against registered face embeddings.
   - `--timeout 45.0`: Absence tolerance in seconds before closing intervals and marking `LEFT`.
   - `--recheck 5`: Frame interval to re-evaluate faces on active tracks.
   - `--output result.mp4`: Save an annotated video file with bounding boxes and overlay.
   - `--no-gui`: Run in headless mode without a GUI window.

Press `q` inside the video window to quit. Upon exit, a consolidated attendance summary is displayed in the terminal.

---

## 3. How to Enroll Students & Facial Photos

### Option A: Bulk Enrollment from Directory (Recommended)
Place student photos inside `data/incoming_photos/`. You can organize them in two formats:

1. **Subfolder per student (recommended for multiple photos per student to boost accuracy):**
   ```text
   data/incoming_photos/
   ├── John_Doe_20230001/
   │   ├── frontal.jpg
   │   └── side_angle.jpg
   └── Mary_Smith_20230002/
       └── photo1.png
   ```

2. **Single image files:**
   ```text
   data/incoming_photos/
   ├── John_Doe_20230001.jpg
   └── Mary_Smith_20230002.png
   ```

Run the bulk enrollment script:
```bash
./.venv/bin/python scripts/bulk_enroll.py --folder data/incoming_photos --group "Group A"
```

The script will:
- Parse student name and ID.
- Create or update the student in the database.
- Enroll them into the specified group.
- Store photos securely under `data/students/{student_id}/`.
- Extract 512D facial embeddings with InsightFace and store them in the database.

---

### Option B: Single Student Enrollment via CLI
```bash
./.venv/bin/python scripts/enroll_student.py --name "John Doe" --number "20230001" --group "Group A" --photo /path/to/photo.jpg
```
Or run interactively (the script prompts for each field):
```bash
./.venv/bin/python scripts/enroll_student.py
```

---

## 4. Utility Scripts

- **List registered students and embeddings:**
  ```bash
  ./.venv/bin/python scripts/list_students.py
  ```
- **Initialize or reset database tables:**
  ```bash
  ./.venv/bin/python scripts/init_db.py
  ```
