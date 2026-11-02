# CivicConnect — Citizen Complaints & Grievance Management

A small Flask + MongoDB web portal based on the ER diagram supplied for the MIS assignment.

## Features
- Citizen submits a complaint from the website.
- Backend saves citizen, complaint, and initial history in MongoDB.
- Complaint categories and departments are stored in their own collections.
- Complaint ID is returned so the citizen can track status.
- Demo admin can update status and add remarks.
- `/api/complaints` returns complaint records as JSON.

## 1. Requirements
- Python 3.10+
- MongoDB Community Server running locally, or a MongoDB Atlas connection string.
- Internet is needed only to load the Google Fonts stylesheet; the site otherwise works without it.

## 2. Install and run (Windows)
Open Command Prompt or VS Code terminal inside this folder:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Start MongoDB Community Server, or create a free MongoDB Atlas database and set `MONGO_URI`.

For local MongoDB, the default URI is already:
`mongodb://localhost:27017/`

Then run:

```bash
python app.py
```

Open `http://127.0.0.1:5000`.

## 3. Pages
- `/` — citizen portal home/dashboard
- `/complaints/new` — file a complaint
- `/track` — track using complaint ID
- `/admin` — demo staff status updates
- `/api/complaints` — JSON API

## 4. MongoDB collections
- `citizens`: citizen contact/profile information
- `complaints`: main complaint record; references citizen, category and department by MongoDB ObjectId; embeds location
- `categories`: category names and descriptions
- `departments`: department contact information
- `staff`: staff records (collection included for ERD; authentication/assignment UI can be added)
- `complaint_assignments`: assignment records (collection included for ERD; assignment UI can be added)
- `complaint_history`: timeline of status changes

MongoDB automatically creates a collection on first insert. The app seeds categories and departments automatically.

## 5. Sample JSON documents

### citizens
```json
{
  "_id": {"$oid": "665000000000000000000001"},
  "full_name": "Aditi Patil",
  "email": "aditi@example.com",
  "phone": "9876543210",
  "address": "Shivaji Nagar, Pune",
  "password_hash": "hashed-password-not-plain-text",
  "created_at": {"$date": "2026-10-29T10:00:00Z"}
}
```

### complaints
```json
{
  "_id": {"$oid": "665000000000000000000010"},
  "citizen_id": {"$oid": "665000000000000000000001"},
  "category_id": {"$oid": "665000000000000000000002"},
  "department_id": {"$oid": "665000000000000000000003"},
  "title": "Pothole near bus stop",
  "description": "A large pothole is causing traffic issues.",
  "location": {
    "address": "Shivaji Nagar bus stop, Pune"
  },
  "status": "Submitted",
  "priority": "High",
  "created_at": {"$date": "2026-10-29T10:05:00Z"},
  "updated_at": {"$date": "2026-10-29T10:05:00Z"}
}
```

## 6. Important for the assignment
This is a learning/demo implementation, not a production government portal. Before real deployment:
- Add secure citizen and staff login, role-based access control, CSRF protection, input validation and rate limiting.
- Do not expose the admin page publicly without authentication.
- Use environment secrets; never commit passwords or production MongoDB credentials.
- Add indexes and backups; use HTTPS and a managed MongoDB deployment.
- The ERD includes `staff` and `complaint_assignments`; the collections are part of the schema, but the demo currently focuses on citizen complaint submission, tracking, and status history.

## 7. Useful MongoDB shell operations
```javascript
use citizen_grievance_db
show collections
db.complaints.find().pretty()
db.complaints.countDocuments({ status: "Submitted" })
db.complaints.find({ status: "Resolved" })
db.complaint_history.find({ complaint_id: ObjectId("PASTE_COMPLAINT_ID") }).sort({ timestamp: 1 })
```
