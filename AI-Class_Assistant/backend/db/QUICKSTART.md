# Database Quick Start Guide

## Setup

### 1. Start the Database with Docker

```bash
docker-compose up db -d
```

The database will be automatically initialized with the schema from `backend/db/init.sql`.

### 2. Verify the Database

You can connect to the database using:

```bash
docker-compose exec db psql -U postgres -d class_assistant
```

List tables:
```sql
\dt
```

View table structure:
```sql
\d users
\d classes
\d presentations
\d presentation_questions
```

### 3. Reset the Database

If you need to reset the database (drop all tables and recreate):

**Option A: Using the Python script**
```bash
docker-compose exec backend python db/reset_db.py
```

**Option B: Using psql directly**
```bash
docker-compose exec db psql -U postgres -d class_assistant -f /docker-entrypoint-initdb.d/init.sql
```

**Option C: Recreate the container (nuclear option)**
```bash
docker-compose down -v  # This will delete ALL data
docker-compose up db -d
```

## Usage in Your Flask App

### Import the database module

```python
from db import database as db
```

### Example: Create a user after Firebase authentication

```python
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.json
    # After verifying Firebase token...
    user = db.create_user(
        firebase_uid=data["firebase_uid"],
        email=data["email"]
    )
    return jsonify(user), 201
```

### Example: Link Telegram account

```python
# 1. Generate a linking code when user clicks "Link Telegram"
@app.route("/api/generate-link-code", methods=["POST"])
def generate_code():
    user_id = request.json["user_id"]
    code = generate_random_code()  # 6-digit code
    expires = datetime.now() + timedelta(minutes=15)
    
    db.generate_telegram_link_code(user_id, code, expires)
    return jsonify({"code": code})

# 2. Telegram bot receives the code from user and calls this
@app.route("/api/telegram/link", methods=["POST"])
def link_telegram():
    data = request.json
    user = db.link_telegram_account(
        link_code=data["code"],
        telegram_chat_id=data["chat_id"]
    )
    return jsonify(user)
```

### Example: Create a class

```python
@socketio.on("create_class")
def handle_create_class(data):
    new_class = db.create_class(
        user_id=data["user_id"],
        subject=data["subject"],
        difficulty_level=data["difficulty_level"],
        class_name=data.get("class_name")
    )
    emit("class_created", new_class)
```

### Example: Handle presentation with questions

```python
# Start a presentation
presentation = db.create_presentation(class_id=class_id, original_pptx_path="path/to/file.pptx")
db.start_presentation(presentation["id"])

# When a question is asked
db.add_question(
    presentation_id=presentation["id"],
    question="What is calculus?",
    answer="Calculus is the study of continuous change...",
    slide_index=5
)

# When AI generates a new slide
db.add_ai_generated_slide(
    presentation_id=presentation["id"],
    slide_index=15  # The new slide was inserted at position 15
)

# End the presentation
db.end_presentation(presentation["id"])
```

## Database Schema Summary

### Users
- Managed by Firebase Auth
- Linked to Telegram via one-time codes
- Fields: `firebase_uid`, `email`, `telegram_chat_id`

### Classes
- Created by users
- Fields: `class_name` (optional), `subject`, `difficulty_level`
- Each class has one presentation

### Presentations
- Linked to a class
- Tracks AI-generated slides: `ai_generated_slide_indices` (array)
- Tracks duration: `started_at`, `ended_at`, `duration_seconds`
- Stores PowerPoint path: `original_pptx_path`

### Presentation Questions
- Questions asked during presentations
- Fields: `question`, `answer`, `asked_at`, `slide_index`

## Environment Variables

Make sure your `.env` file in the backend folder contains:

```env
DB_HOST=db
DB_PORT=5432
DB_NAME=class_assistant
DB_USER=postgres
DB_PASSWORD=postgres
```

## Troubleshooting

### Connection refused
Make sure the database container is running:
```bash
docker-compose ps
```

### Tables don't exist
Reset the database:
```bash
docker-compose exec backend python db/reset_db.py
```

### Can't see data
Connect to the database and check:
```bash
docker-compose exec db psql -U postgres -d class_assistant -c "SELECT * FROM users;"
```
