-- Database initialization and reset script for Class Assistant Platform
-- This script drops existing tables and recreates the schema

-- Drop existing tables if they exist (in reverse order of dependencies)
DROP TABLE IF EXISTS presentation_questions CASCADE;
DROP TABLE IF EXISTS presentations CASCADE;
DROP TABLE IF EXISTS classes CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Create users table
-- Firebase Auth handles authentication, we store additional user data here
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    firebase_uid VARCHAR(128) UNIQUE NOT NULL,
    email VARCHAR(255) NOT NULL,
    telegram_chat_id BIGINT UNIQUE,  -- Linked via one-time code
    telegram_link_code VARCHAR(10) UNIQUE,  -- One-time code for linking Telegram
    telegram_link_code_expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create classes table
-- Each user can create multiple classes
CREATE TABLE classes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    class_name VARCHAR(255),  -- Optional
    subject VARCHAR(100) NOT NULL,  -- e.g., 'Math', 'Physics', 'Chemistry'
    difficulty_level VARCHAR(50) NOT NULL,  -- e.g., 'Beginner', 'Intermediate', 'Advanced'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create presentations table
-- Each class has one presentation associated with it
CREATE TABLE presentations (
    id SERIAL PRIMARY KEY,
    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    original_pptx_path VARCHAR(500),  -- Path to the original PowerPoint file
    ai_generated_slide_indices INTEGER[],  -- Array of slide indices that were AI-generated
    duration_seconds INTEGER,  -- Duration of the presentation in seconds
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create presentation_questions table
-- Stores questions asked during a presentation and their answers
CREATE TABLE presentation_questions (
    id SERIAL PRIMARY KEY,
    presentation_id INTEGER NOT NULL REFERENCES presentations(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    asked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    slide_index INTEGER  -- The slide index where this question was asked (optional)
);

-- Create indexes for better query performance
CREATE INDEX idx_users_firebase_uid ON users(firebase_uid);
CREATE INDEX idx_users_telegram_chat_id ON users(telegram_chat_id);
CREATE INDEX idx_users_telegram_link_code ON users(telegram_link_code);
CREATE INDEX idx_classes_user_id ON classes(user_id);
CREATE INDEX idx_presentations_class_id ON presentations(class_id);
CREATE INDEX idx_presentation_questions_presentation_id ON presentation_questions(presentation_id);

-- Create a function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers to automatically update the updated_at column
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_classes_updated_at BEFORE UPDATE ON classes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_presentations_updated_at BEFORE UPDATE ON presentations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert some sample data for testing (optional, remove in production)
-- Uncomment the lines below if you want to start with sample data

-- INSERT INTO users (firebase_uid, email) VALUES 
--     ('firebase_test_uid_1', 'student1@example.com'),
--     ('firebase_test_uid_2', 'student2@example.com');

-- INSERT INTO classes (user_id, class_name, subject, difficulty_level) VALUES
--     (1, 'Introduction to Calculus', 'Math', 'Intermediate'),
--     (1, 'Advanced Physics', 'Physics', 'Advanced');

-- INSERT INTO presentations (class_id, ai_generated_slide_indices, duration_seconds) VALUES
--     (1, ARRAY[5, 7, 12], 3600);

-- INSERT INTO presentation_questions (presentation_id, question, answer, slide_index) VALUES
--     (1, 'What is a derivative?', 'A derivative represents the rate of change of a function with respect to a variable.', 5);
