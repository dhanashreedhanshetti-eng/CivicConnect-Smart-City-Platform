import webbrowser
from threading import Timer
import os
from datetime import datetime, timezone
from bson import ObjectId
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from pymongo import MongoClient, DESCENDING
from pymongo.errors import PyMongoError
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-development-secret")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
db = client["citizen_grievance_db"]

# Collections are based on the supplied ER diagram.
citizens = db["citizens"]
complaints = db["complaints"]
categories = db["categories"]
departments = db["departments"]
staff = db["staff"]
assignments = db["complaint_assignments"]
history = db["complaint_history"]

def now_utc():
    return datetime.now(timezone.utc)

def seed_reference_data():
    """Insert starter categories/departments only when the collections are empty."""
    if categories.count_documents({}) == 0:
        categories.insert_many([
            {"category_name": "Roads & Potholes", "description": "Damaged roads, potholes and footpaths", "active": True},
            {"category_name": "Water Supply", "description": "Water leakage or interrupted supply", "active": True},
            {"category_name": "Waste Management", "description": "Garbage collection and cleanliness", "active": True},
            {"category_name": "Streetlights", "description": "Broken or non-working streetlights", "active": True},
            {"category_name": "Other", "description": "Other civic issues", "active": True},
        ])
    if departments.count_documents({}) == 0:
        departments.insert_many([
            {"department_name": "Public Works", "contact_email": "pwd@example.gov", "contact_phone": "020-0000001"},
            {"department_name": "Water Department", "contact_email": "water@example.gov", "contact_phone": "020-0000002"},
            {"department_name": "Sanitation Department", "contact_email": "sanitation@example.gov", "contact_phone": "020-0000003"},
            {"department_name": "Electrical Department", "contact_email": "electric@example.gov", "contact_phone": "020-0000004"},
            {"department_name": "General Grievances", "contact_email": "helpdesk@example.gov", "contact_phone": "020-0000000"},
        ])

def available():
    try:
        client.admin.command("ping")
        seed_reference_data()
        return True
    except PyMongoError:
        return False

@app.context_processor
def inject_globals():
    try:
        return {"db_connected": available()}
    except Exception:
        return {"db_connected": False}

@app.route("/")
def index():
    try:
        total = complaints.count_documents({})
        open_count = complaints.count_documents({"status": {"$in": ["Submitted", "In Progress"]}})
        resolved = complaints.count_documents({"status": "Resolved"})
        recent = list(complaints.find().sort("created_at", DESCENDING).limit(5))
        for c in recent:
            c["_id"] = str(c["_id"])
            c["citizen_name"] = (citizens.find_one({"_id": c.get("citizen_id")}) or {}).get("full_name", "Citizen")
            c["category_name"] = (categories.find_one({"_id": c.get("category_id")}) or {}).get("category_name", "Other")
        return render_template("index.html", total=total, open_count=open_count, resolved=resolved, recent=recent)
    except PyMongoError:
        return render_template("index.html", total=0, open_count=0, resolved=0, recent=[])

@app.route("/complaints/new", methods=["GET", "POST"])
def new_complaint():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category_id = request.form.get("category_id", "").strip()
        priority = request.form.get("priority", "Medium")
        if not all([full_name, email, phone, address, title, description, category_id]):
            flash("Please complete all required fields.", "error")
            return redirect(url_for("new_complaint"))
        try:
            cat = categories.find_one({"_id": ObjectId(category_id)})
            if not cat:
                flash("Please select a valid complaint category.", "error")
                return redirect(url_for("new_complaint"))
            citizen = citizens.find_one({"email": email})
            if citizen:
                citizens.update_one({"_id": citizen["_id"]}, {"$set": {
                    "full_name": full_name, "phone": phone, "address": address
                }})
                citizen_id = citizen["_id"]
            else:
                result = citizens.insert_one({
                    "full_name": full_name,
                    "email": email,
                    "phone": phone,
                    "address": address,
                    # A real production portal should use a registration/login flow.
                    "password_hash": generate_password_hash(os.getenv("DEMO_DEFAULT_PASSWORD", "change-me")),
                    "created_at": now_utc()
                })
                citizen_id = result.inserted_id

            # Simple category-to-department mapping for the demo.
            mapping = {
                "Roads & Potholes": "Public Works",
                "Water Supply": "Water Department",
                "Waste Management": "Sanitation Department",
                "Streetlights": "Electrical Department",
            }
            dept = departments.find_one({"department_name": mapping.get(cat["category_name"], "General Grievances")})
            complaint_doc = {
                "citizen_id": citizen_id,       # referenced document
                "category_id": cat["_id"],      # referenced document
                "department_id": dept["_id"] if dept else None,
                "title": title,
                "description": description,
                "location": {"address": address},  # embedded document
                "status": "Submitted",
                "priority": priority if priority in ["Low", "Medium", "High"] else "Medium",
                "created_at": now_utc(),
                "updated_at": now_utc()
            }
            result = complaints.insert_one(complaint_doc)
            history.insert_one({
                "complaint_id": result.inserted_id,
                "updated_by": citizen_id,
                "status": "Submitted",
                "remarks": "Complaint submitted through the citizen web portal.",
                "timestamp": now_utc()
            })
            flash(f"Complaint submitted successfully. Your complaint ID is {result.inserted_id}. Save it to track progress.", "success")
            return redirect(url_for("track_complaint", complaint_id=str(result.inserted_id)))
        except (PyMongoError, ValueError) as exc:
            flash("Could not save your complaint. Check that MongoDB is running and try again.", "error")
            app.logger.exception(exc)
            return redirect(url_for("new_complaint"))

    try:
        cats = list(categories.find({"active": {"$ne": False}}).sort("category_name", 1))
    except PyMongoError:
        cats = []
    return render_template("new_complaint.html", categories=cats)

@app.route("/track", methods=["GET", "POST"])
def track():
    complaint_id = request.values.get("complaint_id", "").strip()
    if complaint_id:
        return redirect(url_for("track_complaint", complaint_id=complaint_id))
    return render_template("track.html", complaint=None, timeline=[])

@app.route("/track/<complaint_id>")
def track_complaint(complaint_id):
    complaint = None
    timeline = []
    error = None
    try:
        complaint = complaints.find_one({"_id": ObjectId(complaint_id)})
        if complaint:
            citizen = citizens.find_one({"_id": complaint.get("citizen_id")}) or {}
            cat = categories.find_one({"_id": complaint.get("category_id")}) or {}
            dept = departments.find_one({"_id": complaint.get("department_id")}) or {}
            complaint["id_text"] = str(complaint["_id"])
            complaint["citizen_name"] = citizen.get("full_name", "Citizen")
            complaint["category_name"] = cat.get("category_name", "Other")
            complaint["department_name"] = dept.get("department_name", "Not assigned")
            timeline = list(history.find({"complaint_id": complaint["_id"]}).sort("timestamp", 1))
            for item in timeline:
                item["timestamp_text"] = item.get("timestamp").strftime("%d %b %Y, %I:%M %p") if item.get("timestamp") else ""
        else:
            error = "No complaint found with that ID."
    except (ValueError, PyMongoError):
        error = "That ID is not valid, or the database is unavailable."
    return render_template("track.html", complaint=complaint, timeline=timeline, error=error)

@app.route("/admin", methods=["GET", "POST"])
def admin():
    # Classroom demo only: protect this route with real authentication before public deployment.
    if request.method == "POST":
        cid = request.form.get("complaint_id", "")
        new_status = request.form.get("status", "")
        remarks = request.form.get("remarks", "").strip()
        allowed = ["Submitted", "In Progress", "Resolved", "Rejected"]
        if new_status not in allowed:
            flash("Choose a valid status.", "error")
            return redirect(url_for("admin"))
        try:
            complaint = complaints.find_one({"_id": ObjectId(cid)})
            if not complaint:
                flash("Complaint not found.", "error")
            else:
                complaints.update_one({"_id": complaint["_id"]}, {"$set": {
                    "status": new_status, "updated_at": now_utc()
                }})
                history.insert_one({
                    "complaint_id": complaint["_id"],
                    "updated_by": "admin-demo",
                    "status": new_status,
                    "remarks": remarks or f"Status changed to {new_status}.",
                    "timestamp": now_utc()
                })
                flash("Complaint status updated.", "success")
        except (ValueError, PyMongoError):
            flash("Could not update status. Check the complaint ID and MongoDB connection.", "error")
        return redirect(url_for("admin"))
    try:
        all_complaints = list(complaints.find().sort("created_at", DESCENDING).limit(100))
        for c in all_complaints:
            c["id_text"] = str(c["_id"])
            c["citizen_name"] = (citizens.find_one({"_id": c.get("citizen_id")}) or {}).get("full_name", "Citizen")
            c["category_name"] = (categories.find_one({"_id": c.get("category_id")}) or {}).get("category_name", "Other")
    except PyMongoError:
        all_complaints = []
    return render_template("admin.html", complaints=all_complaints)

@app.route("/api/complaints")
def api_complaints():
    """Small JSON endpoint for demonstrating backend/database connectivity."""
    try:
        rows = []
        for c in complaints.find().sort("created_at", DESCENDING).limit(100):
            rows.append({
                "id": str(c["_id"]),
                "title": c.get("title"),
                "status": c.get("status"),
                "priority": c.get("priority"),
                "created_at": c.get("created_at").isoformat() if c.get("created_at") else None
            })
        return jsonify({"count": len(rows), "complaints": rows})
    except PyMongoError:
        return jsonify({"error": "MongoDB unavailable"}), 503

if __name__ == "__main__":
    if available():
        print("Connected to MongoDB database: citizen_grievance_db")
    else:
        print("MongoDB is not reachable. Start MongoDB or set MONGO_URI.")

    Timer(2, lambda: webbrowser.open("http://127.0.0.1:5000")).start()

    app.run(debug=True, use_reloader=False, port=int(os.getenv("PORT", "5000")))