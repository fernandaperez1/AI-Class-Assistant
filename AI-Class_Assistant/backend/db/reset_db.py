"""
Database reset utility for Class Assistant Platform
This script connects to PostgreSQL and resets the database schema
"""
import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration from environment variables
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "class_assistant")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")


def get_connection(database=None):
    """Create a database connection"""
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
    """Create the database if it doesn't exist"""
    # Connect to the default 'postgres' database to create our database
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
        print("  - presentation_questions")
        
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
    
    print("Step 3: Verifying schema...")
    if not verify_schema():
        print("Failed to verify schema.")
        exit(1)
    print()
    
    print("=" * 60)
    print("Database reset completed successfully!")
    print("=" * 60)
