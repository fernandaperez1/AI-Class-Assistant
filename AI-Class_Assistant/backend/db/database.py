import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'class_assistant'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}


@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()


@contextmanager
def get_db_cursor(commit=True):
    """Context manager for database cursor with automatic commit/rollback"""
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield cursor
            if commit:
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()


# User operations
def create_user(firebase_uid, email):
    """Create a new user"""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO users (firebase_uid, email)
            VALUES (%s, %s)
            RETURNING id, firebase_uid, email, telegram_chat_id, created_at
            """,
            (firebase_uid, email)
        )
        return dict(cursor.fetchone())


def get_user_by_firebase_uid(firebase_uid):
    """Get user by Firebase UID"""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, firebase_uid, email, telegram_chat_id, 
                   telegram_link_code, telegram_link_code_expires_at,
                   created_at, updated_at
            FROM users
            WHERE firebase_uid = %s
            """,
            (firebase_uid,)
        )
        result = cursor.fetchone()
        return dict(result) if result else None


def get_user_by_telegram_chat_id(telegram_chat_id):
    """Get user by Telegram chat ID"""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, firebase_uid, email, telegram_chat_id,
                   created_at, updated_at
            FROM users
            WHERE telegram_chat_id = %s
            """,
            (telegram_chat_id,)
        )
        result = cursor.fetchone()
        return dict(result) if result else None


def generate_telegram_link_code(user_id, code, expires_at):
    """Generate a one-time code for linking Telegram"""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE users
            SET telegram_link_code = %s, telegram_link_code_expires_at = %s
            WHERE id = %s
            RETURNING id, telegram_link_code
            """,
            (code, expires_at, user_id)
        )
        return dict(cursor.fetchone())


def link_telegram_account(link_code, telegram_chat_id):
    """Link a Telegram account using the one-time code"""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE users
            SET telegram_chat_id = %s,
                telegram_link_code = NULL,
                telegram_link_code_expires_at = NULL
            WHERE telegram_link_code = %s 
            AND telegram_link_code_expires_at > NOW()
            RETURNING id, firebase_uid, email, telegram_chat_id
            """,
            (telegram_chat_id, link_code)
        )
        result = cursor.fetchone()
        return dict(result) if result else None

def unlink_telegram_account(telegram_chat_id):
    """unlink a Telegram account using the one-time code"""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE users
            SET telegram_chat_id = NULL,
                telegram_link_code = NULL,
                telegram_link_code_expires_at = NULL
            WHERE telegram_chat_id = %s 
            RETURNING id, firebase_uid, email, telegram_chat_id
            """,
            (telegram_chat_id,)
        )
        result = cursor.fetchone()
        return dict(result) if result else None

# Class operations
def create_class(user_id, subject, difficulty_level, class_name=None):
    """Create a new class"""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO classes (user_id, class_name, subject, difficulty_level)
            VALUES (%s, %s, %s, %s)
            RETURNING id, user_id, class_name, subject, difficulty_level, created_at
            """,
            (user_id, class_name, subject, difficulty_level)
        )
        return dict(cursor.fetchone())
    

def delete_class(class_id, user_id):
    """Delete a class and its associated PPTX file if it exists."""
    try:
        with get_db_cursor() as cursor:
            # Get the associated pptx file path
            cursor.execute(
                """
                SELECT p.original_pptx_path
                FROM presentations p
                JOIN classes c ON p.class_id = c.id
                WHERE c.id = %s AND c.user_id = %s
                """,
                (class_id, user_id)
            )
            result = cursor.fetchone()
            if result and result.get("original_pptx_path"):
                pptx_path = result["original_pptx_path"]
                if os.path.exists(pptx_path):
                    try:
                        os.remove(pptx_path)
                        print(f"Deleted PPTX file: {pptx_path}")
                    except Exception as e:
                        print(f"Warning: Could not delete file {pptx_path}: {e}")

            cursor.execute(
                """
                DELETE FROM classes
                WHERE id = %s AND user_id = %s
                RETURNING id, user_id
                """,
                (class_id, user_id)
            )

            result = cursor.fetchone()
            return dict(result) if result else None

    except Exception as e:
        print("DB error:", e)
        raise


def get_class_by_id(class_id):
    """Get class by ID"""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, user_id, class_name, subject, difficulty_level,
                   created_at, updated_at
            FROM classes
            WHERE id = %s
            """,
            (class_id,)
        )
        result = cursor.fetchone()
        return dict(result) if result else None


def get_user_classes(user_id):
    """Get all classes for a user with presentation info"""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT c.id, c.user_id, c.class_name, c.subject, c.difficulty_level,
                   c.created_at, c.updated_at,
                   p.id as presentation_id, p.slide_count, p.original_pptx_path
            FROM classes c
            LEFT JOIN presentations p ON c.id = p.class_id
            WHERE c.user_id = %s
            ORDER BY c.created_at DESC
            """,
            (user_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


def update_class(class_id, **kwargs):
    """Update class fields"""
    allowed_fields = {'class_name', 'subject', 'difficulty_level'}
    update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
    
    if not update_fields:
        return None
    
    set_clause = ', '.join([f"{k} = %s" for k in update_fields.keys()])
    values = list(update_fields.values()) + [class_id]
    
    with get_db_cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE classes
            SET {set_clause}
            WHERE id = %s
            RETURNING id, user_id, class_name, subject, difficulty_level, updated_at
            """,
            values
        )
        result = cursor.fetchone()
        return dict(result) if result else None




# Presentation operations
def create_presentation(class_id, original_pptx_path=None):
    """Create a new presentation for a class"""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO presentations (class_id, original_pptx_path, ai_generated_slide_indices)
            VALUES (%s, %s, %s)
            RETURNING id, class_id, original_pptx_path, ai_generated_slide_indices,
                      duration_seconds, started_at, created_at
            """,
            (class_id, original_pptx_path, [])
        )
        return dict(cursor.fetchone())


def get_presentation_by_id(presentation_id):
    """Get presentation by ID with owner info."""
    with get_db_cursor(commit=False) as cursor:
        cursor.execute(
            """
            SELECT 
                p.id,
                p.current_slide,
                p.slide_count,
                p.class_id,
                p.original_pptx_path,
                p.ai_generated_slide_indices,
                p.duration_seconds,
                p.started_at,
                p.ended_at,
                p.created_at,
                p.updated_at,
                c.user_id AS owner_id,
                u.telegram_chat_id AS presenter_chat_id
            FROM presentations p
            JOIN classes c ON c.id = p.class_id
            LEFT JOIN users u ON u.id = c.user_id
            WHERE p.id = %s
            """,
            (presentation_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None



def get_presentation_by_class_id(class_id):
    """Get presentation for a class"""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, class_id, original_pptx_path, ai_generated_slide_indices,
                   duration_seconds, started_at, ended_at, created_at, updated_at
            FROM presentations
            WHERE class_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (class_id,)
        )
        result = cursor.fetchone()
        return dict(result) if result else None


def add_ai_generated_slide(presentation_id, slide_index):
    """Add a new AI-generated slide index to the presentation"""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE presentations
            SET ai_generated_slide_indices = array_append(ai_generated_slide_indices, %s)
            WHERE id = %s
            RETURNING id, ai_generated_slide_indices
            """,
            (slide_index, presentation_id)
        )
        result = cursor.fetchone()
        return dict(result) if result else None


def reset_ai_generated_slide_indices(presentation_id):
    """Reset the ai_generated_slide_indices array (used when resetting presentation)"""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE presentations
            SET ai_generated_slide_indices = ARRAY[]::INTEGER[]
            WHERE id = %s
            RETURNING id, ai_generated_slide_indices
            """,
            (presentation_id,)
        )
        result = cursor.fetchone()
        return dict(result) if result else None


def start_presentation(presentation_id):
    """Mark presentation as started"""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE presentations
            SET started_at = NOW()
            WHERE id = %s
            RETURNING id, started_at
            """,
            (presentation_id,)
        )
        result = cursor.fetchone()
        return dict(result) if result else None


def end_presentation(presentation_id):
    """Mark presentation as ended and calculate duration"""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE presentations
            SET ended_at = NOW(),
                duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::INTEGER
            WHERE id = %s
            RETURNING id, started_at, ended_at, duration_seconds
            """,
            (presentation_id,)
        )
        result = cursor.fetchone()
        return dict(result) if result else None


# AI Slide operations
def add_ai_slide(presentation_id, slide_content, user_input, answer=None, slide_index=None):
    """Add an AI-generated slide (example or question) to a presentation"""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO presentation_AI_slide 
            (presentation_id, slide_content, user_input, answer, slide_index)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, presentation_id, slide_content, user_input, answer, slide_index, created_at
            """,
            (presentation_id, slide_content, user_input, answer, slide_index)
        )
        return dict(cursor.fetchone())


def get_presentation_ai_slides(presentation_id):
    """Get all AI-generated slides for a presentation"""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, presentation_id, slide_content, user_input, answer, slide_index, created_at
            FROM presentation_AI_slide
            WHERE presentation_id = %s
            ORDER BY created_at ASC
            """,
            (presentation_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


def delete_presentation_ai_slides(presentation_id):
    """Delete all AI-generated slides for a presentation (used when resetting)"""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM presentation_AI_slide
            WHERE presentation_id = %s
            RETURNING id
            """,
            (presentation_id,)
        )
        deleted_rows = cursor.fetchall()
        return len(deleted_rows)


def update_ai_slide_indices_after_insertion(presentation_id, inserted_at_index):
    """
    Update slide indices for AI slides that come after the newly inserted slide.
    When a slide is inserted at position N, all AI slides at position >= N need to be incremented.
    Also updates the ai_generated_slide_indices array in the presentations table.
    """
    with get_db_cursor() as cursor:
        #get the current ai_generated_slide_indices array
        cursor.execute(
            """
            SELECT ai_generated_slide_indices
            FROM presentations
            WHERE id = %s
            """,
            (presentation_id,)
        )
        result = cursor.fetchone()
        current_indices = result['ai_generated_slide_indices'] if result else []
        
        # Update the indices, increment any index >= inserted_at_index
        updated_indices = [idx + 1 if idx >= inserted_at_index else idx for idx in current_indices]
        
        # Update the array in the presentations table
        cursor.execute(
            """
            UPDATE presentations
            SET ai_generated_slide_indices = %s
            WHERE id = %s
            """,
            (updated_indices, presentation_id)
        )
        
        # Update slide_index in presentation_AI_slide table
        cursor.execute(
            """
            UPDATE presentation_AI_slide
            SET slide_index = slide_index + 1
            WHERE presentation_id = %s AND slide_index >= %s
            RETURNING id, slide_index
            """,
            (presentation_id, inserted_at_index)
        )
        updated_rows = cursor.fetchall()
        return [dict(row) for row in updated_rows]


def get_active_presentation_for_user(user_id: int):
    with get_db_cursor(commit=False) as cursor:
        cursor.execute(
            """
            SELECT p.id
            FROM presentations p
            JOIN classes c ON c.id = p.class_id
            WHERE c.user_id = %s
              AND p.started_at IS NOT NULL
              AND p.ended_at IS NULL
            ORDER BY p.started_at DESC
            LIMIT 1
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        return row["id"] if row else None


def get_presentation_owner(presentation_id):
    with get_db_cursor(commit=False) as cursor:
        cursor.execute(
            """
            SELECT c.user_id
            FROM presentations p
            JOIN classes c ON c.id = p.class_id
            WHERE p.id = %s
            """,
            (presentation_id,),
        )
        row = cursor.fetchone()
        return row["user_id"] if row else None

def update_current_slide(presentation_id: int, slide: int):
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE presentations
            SET current_slide = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING id, current_slide, slide_count
            """,
            (slide, presentation_id),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def update_slide_metadata(presentation_id: int, *, current_slide: int | None = None,
                          slide_count: int | None = None):
    """Updates the current slide and the slide count."""
    fields = []
    values = []

    if current_slide is not None:
        fields.append("current_slide = %s")
        values.append(current_slide)

    if slide_count is not None:
        fields.append("slide_count = %s")
        values.append(slide_count)

    if not fields:
        return None

    query = f"""
        UPDATE presentations
        SET {', '.join(fields)}, updated_at = NOW()
        WHERE id = %s
        RETURNING id, current_slide, slide_count
    """
    values.append(presentation_id)

    with get_db_cursor() as cursor:
        cursor.execute(query, tuple(values))
        row = cursor.fetchone()
        return dict(row) if row else None
