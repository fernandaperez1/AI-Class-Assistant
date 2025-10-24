import os
import shutil
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

load_dotenv()

# Database configuration from environment variables
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "class_assistant")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")


def get_connection(database=None):
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=database if database else DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to database: {e}")
        return None


def create_database():
    conn = get_connection(database="postgres")
    if not conn:
        return False
    
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    try:
        # Check if database exists
        cursor.execute(
            "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
            (DB_NAME,)
        )
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute(f'CREATE DATABASE {DB_NAME}')
            print(f"Database '{DB_NAME}' created successfully")
        else:
            print(f"Database '{DB_NAME}' already exists")
        
        cursor.close()
        conn.close()
        return True
    except psycopg2.Error as e:
        print(f"Error creating database: {e}")
        cursor.close()
        conn.close()
        return False


def reset_database():
    """Reset the database by running the init.sql script"""
    conn = get_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    try:
        # Read the SQL initialization script
        script_path = os.path.join(os.path.dirname(__file__), "init.sql")
        with open(script_path, "r") as f:
            sql_script = f.read()
        
        # Execute the script
        cursor.execute(sql_script)
        conn.commit()
        
        print("Database schema reset successfully")
        print("Tables created:")
        print("  - users")
        print("  - classes")
        print("  - presentations")
        print("  - presentation_AI_slide")
        
        cursor.close()
        conn.close()
        return True
    except psycopg2.Error as e:
        print(f"Error resetting database: {e}")
        conn.rollback()
        cursor.close()
        conn.close()
        return False
    except FileNotFoundError:
        print(f"Error: init.sql file not found at {script_path}")
        cursor.close()
        conn.close()
        return False


def delete_uploaded_files():
    """Delete all files in uploads and slides folders"""
    # Get the backend directory path
    backend_dir = os.path.dirname(os.path.dirname(__file__))
    uploads_dir = os.path.join(backend_dir, "uploads")
    slides_dir = os.path.join(backend_dir, "slides")
    
    deleted_count = 0
    
    try:
        # Delete all files in uploads folder (except README.md)
        if os.path.exists(uploads_dir):
            print(f"Cleaning uploads folder: {uploads_dir}")
            for filename in os.listdir(uploads_dir):
                if filename != "README.md":
                    file_path = os.path.join(uploads_dir, filename)
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                            deleted_count += 1
                            print(f"  - Deleted: {filename}")
                    except Exception as e:
                        print(f"  - Error deleting {filename}: {e}")
        
        # Delete all files and folders in slides folder (except README.md)
        if os.path.exists(slides_dir):
            print(f"Cleaning slides folder: {slides_dir}")
            for item in os.listdir(slides_dir):
                if item != "README.md":
                    item_path = os.path.join(slides_dir, item)
                    try:
                        if os.path.isfile(item_path):
                            os.remove(item_path)
                            deleted_count += 1
                            print(f"  - Deleted file: {item}")
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                            deleted_count += 1
                            print(f"  - Deleted folder: {item}")
                    except Exception as e:
                        print(f"  - Error deleting {item}: {e}")
        
        print(f"\nTotal items deleted: {deleted_count}")
        return True
    except Exception as e:
        print(f"Error cleaning files: {e}")
        return False


def verify_schema():
    conn = get_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        
        print("\nExisting tables:")
        for table in tables:
            print(f"  - {table[0]}")
        
        cursor.close()
        conn.close()
        return True
    except psycopg2.Error as e:
        print(f"Error verifying schema: {e}")
        cursor.close()
        conn.close()
        return False

#to run this shit from docker
if __name__ == "__main__":
    print("=" * 60)
    print("Class Assistant Platform - Database Reset Utility")
    print("=" * 60)
    print()
    
    print("Step 1: Creating database if needed...")
    if not create_database():
        print("Failed to create database. Exiting.")
        exit(1)
    print()
    
    print("Step 2: Resetting database schema...")
    if not reset_database():
        print("Failed to reset database schema. Exiting.")
        exit(1)
    print()
    
    print("Step 3: Deleting uploaded files...")
    if not delete_uploaded_files():
        print("Warning: Failed to delete some files.")
    print()
    
    print("Step 4: Verifying schema...")
    if not verify_schema():
        print("Failed to verify schema.")
        exit(1)
    print()
    
    print("=" * 60)
    print("Database reset completed successfully!")
    print("All uploaded files and slides have been deleted!")
    print("=" * 60)
