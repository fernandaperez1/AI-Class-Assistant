# Database Setup and Reset

This folder contains the database initialization and reset scripts for the Class Assistant Platform.

## Files

- **`init.sql`**: PostgreSQL schema definition with all tables, indexes, and triggers
- **`reset_db.py`**: Python script to reset the database programmatically
- **`README.md`**: This file

## Database Schema

### Tables

1. **`users`**
   - Stores user information linked to Firebase Auth
   - Contains telegram chat ID and one-time linking code
   - Fields: `id`, `firebase_uid`, `email`, `telegram_chat_id`, `telegram_link_code`, `telegram_link_code_expires_at`

2. **`classes`**
   - Stores classes created by users
   - Fields: `id`, `user_id`, `class_name` (optional), `subject`, `difficulty_level`

3. **`presentations`**
   - Stores presentation data for each class
   - Fields: `id`, `class_id`, `original_pptx_path`, `ai_generated_slide_indices`, `duration_seconds`, `started_at`, `ended_at`

4. **`presentation_AI_slide`**
   - Stores AI-generated slides (examples and questions) created during presentations
   - Fields: `id`, `presentation_id`, `slide_content`, `user_input`, `answer` (optional), `slide_index`, `created_at`
   - The `answer` field is optional - it's NULL for examples and contains the quiz answer for questions

## Usage

### Option 1: Using Docker (Recommended)

The database will be automatically initialized when you start your Docker containers. Make sure your `docker-compose.yml` includes:

```yaml
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: class_assistant
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - ./backend/db/init.sql:/docker-entrypoint-initdb.d/init.sql
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

To reset the database while running:
```bash
docker-compose exec db psql -U postgres -d class_assistant -f /docker-entrypoint-initdb.d/init.sql
```

### Option 2: Using the Python Script

1. Make sure you have the required packages installed:
   ```bash
   pip install psycopg2-binary python-dotenv
   ```

2. Set up your environment variables in `.env`:
   ```
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=class_assistant
   DB_USER=postgres
   DB_PASSWORD=postgres
   ```

3. Run the reset script:
   ```bash
   python backend/db/reset_db.py
   ```

### Option 3: Using psql directly

```bash
psql -U postgres -d class_assistant -f backend/db/init.sql
```

## Environment Variables

The following environment variables are used:

- `DB_HOST`: Database host (default: `localhost`)
- `DB_PORT`: Database port (default: `5432`)
- `DB_NAME`: Database name (default: `class_assistant`)
- `DB_USER`: Database user (default: `postgres`)
- `DB_PASSWORD`: Database password (default: `postgres`)

## Notes

- The script automatically creates the database if it doesn't exist
- All tables are dropped and recreated when running the reset
- Timestamps are automatically managed with triggers
- Sample data is commented out in `init.sql` - uncomment if needed for testing
