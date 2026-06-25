import uuid
import sqlite3
from flask import Flask, render_template, request, jsonify
from sync_engine import EduAccessSyncEngine

app = Flask(__name__)

# Instantiate the Core Replication and Sync Engine
# In production, remote_api_url points to your live Supabase/Railway REST endpoint
sync_engine = EduAccessSyncEngine(
    local_db_path="eduaccess_local.db",
    remote_api_url="https://your-supabase-app.railway.app/api/sync"
)

# Mock Course Database for Offline Presentation
OFFLINE_COURSES = {
    "CS-50X": {
        "title": "Harvard CS50x: Intro to Computer Science",
        "description": "Fundamental concepts of computer science and programming. Algorithms, data structures, resource management, and web development.",
        "modules": [
            {"id": "CS-50X-M1", "title": "Algorithmic Complexity & Big O", "points": 100},
            {"id": "CS-50X-M2", "title": "Memory Management & Pointer Arithmetic", "points": 100},
            {"id": "CS-50X-M3", "title": "Binary Search Trees & Heap Sorting", "points": 100}
        ]
    },
    "CYBER-SEC": {
        "title": "Google & Harvard Cybersecurity",
        "description": "Network security modeling, Linux administration, and protecting enterprise applications against SQL injection and loop cycles.",
        "modules": [
            {"id": "CYBER-SEC-M1", "title": "Preventing SQL Injection Attacks", "points": 100},
            {"id": "CYBER-SEC-M2", "title": "Network Traffic Analysis & Firewalls", "points": 100}
        ]
    }
}

@app.route("/")
def home():
    """Renders the offline student learning dashboard and system admin panel."""
    # Read the latest local progress records from the SQLite database
    conn = sqlite3.connect(sync_engine.local_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, student_id, course_id, module_completed, score, completed_at, synced FROM student_progress ORDER BY completed_at DESC")
    records = cursor.fetchall()
    conn.close()

    formatted_records = []
    unsynced_count = 0
    for rec in records:
        if rec[6] == 0:
            unsynced_count += 1
        formatted_records.append({
            "id": rec[0],
            "student_id": rec[1],
            "course_id": rec[2],
            "module_completed": rec[3],
            "score": rec[4],
            "completed_at": rec[5],
            "synced": rec[6]
        })

    return render_template("index.html", courses=OFFLINE_COURSES, records=formatted_records, unsynced_count=unsynced_count)

@app.route("/lesson/<course_id>/<module_id>")
def lesson(course_id, module_id):
    """Renders the offline interactive classroom layout for a specific lesson/quiz."""
    course = OFFLINE_COURSES.get(course_id)
    if not course:
        return "Course not found", 404
    
    module = next((m for m in course["modules"] if m["id"] == module_id), None)
    if not module:
        return "Module not found", 404

    return render_template("lesson.html", course_id=course_id, course_title=course["title"], module=module)

@app.route("/api/complete", methods=["POST"])
def complete_module():
    """API endpoint to record a student's completion state locally inside SQLite."""
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "Invalid payload"}), 400

    student_id = data.get("student_id", "STUDENT-OFFLINE")
    course_id = data.get("course_id")
    module_id = data.get("module_id")
    score = int(data.get("score", 100))
    progress_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"

    # Save to local SQLite database via sync_engine
    sync_engine.record_progress_offline(
        progress_id=progress_id,
        student_id=student_id,
        course_id=course_id,
        module=module_id,
        score=score
    )

    return jsonify({
        "success": True,
        "progress_id": progress_id,
        "message": f"Successfully stored progress offline for student {student_id}!"
    })

@app.route("/api/sync", methods=["POST"])
def trigger_sync():
    """Triggers the replication engine to attempt synchronization to the cloud."""
    success = sync_engine.sync_local_data_to_cloud()
    if success:
        return jsonify({
            "success": True,
            "message": "Data replication completed successfully! All local records synchronized to the cloud."
        })
    else:
        return jsonify({
            "success": False,
            "message": "Data replication failed. You are currently offline or the remote gateway is unreachable. Local progress is preserved safely."
        }), 503

if __name__ == "__main__":
    # In production, the server runs on 0.0.0.0 so students can connect to the local LAN router
    print("\n* =============================================================== *")
    print("* EDUPORTAL ACTIVE IN LOCAL OFFLINE-MODE                          *")
    print("* LAN ACCESS: http://127.0.0.1:5000                               *")
    print("* INSTRUCTION: Connect students to Wi-Fi to load lessons for $0  *")
    print("* =============================================================== *\n")
    app.run(host="0.0.0.0", port=5000, debug=True)
