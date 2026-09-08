const API_BASE = "http://localhost:8000/api";

export async function fetchStudents() {
  const res = await fetch(`${API_BASE}/students`);
  if (!res.ok) throw new Error("Failed to fetch students");
  return res.json();
}

export async function enrollStudentBase64(payload) {
  const res = await fetch(`${API_BASE}/students/enroll-base64`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Enrollment failed");
  }
  return res.json();
}

export async function deleteStudent(studentId) {
  const res = await fetch(`${API_BASE}/students/${studentId}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete student");
  return res.json();
}

export async function startClassSession(groupName = "Group A") {
  const res = await fetch(`${API_BASE}/class-sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ group_name: groupName, course_code: "COURSE-101" })
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to start session");
  }
  return res.json();
}

export async function fetchSessionAttendance(sessionId) {
  const res = await fetch(`${API_BASE}/class-sessions/${sessionId}/attendance`);
  if (!res.ok) throw new Error("Failed to fetch session attendance");
  return res.json();
}

export async function endClassSession(sessionId) {
  const res = await fetch(`${API_BASE}/class-sessions/${sessionId}/end`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to end session");
  return res.json();
}

export async function manualAttendanceCorrection(sessionId, recordId, newStatus, reason) {
  const res = await fetch(`${API_BASE}/class-sessions/${sessionId}/attendance/${recordId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ new_status: newStatus, reason: reason })
  });
  if (!res.ok) throw new Error("Failed to submit manual correction");
  return res.json();
}
