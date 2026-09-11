import sqlite3
from datetime import datetime

def init_db():

    connection = sqlite3.connect("learnwise.db")

    cursor = connection.cursor()


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS study_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            filename TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER,
            summary TEXT,
            FOREIGN KEY (material_id) REFERENCES study_materials(id)
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER,
            question TEXT,
            answer TEXT,
            FOREIGN KEY (material_id) REFERENCES study_materials(id)
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS generated_quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER,
            quiz_data TEXT,
            FOREIGN KEY (material_id) REFERENCES study_materials(id)
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            quiz_id INTEGER,
            score INTEGER,
            percentage REAL,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (quiz_id) REFERENCES generated_quizzes(id)
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS topic_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id INTEGER,
            topic TEXT,
            correct INTEGER,
            total INTEGER,
            percentage REAL,
            FOREIGN KEY (attempt_id) REFERENCES quiz_attempts(id)
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS weak_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id INTEGER,
            topic TEXT,
            percentage REAL,
            competency_gap TEXT,
            recommendation TEXT,
            FOREIGN KEY (attempt_id) REFERENCES quiz_attempts(id)
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS study_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            attempt_id INTEGER,
            plan TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (attempt_id) REFERENCES quiz_attempts(id)
        )
    """)
 
        # Add date and time to existing tables
    try:
        cursor.execute(
            "ALTER TABLE study_materials ADD COLUMN created_at TEXT"
        )
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute(
            "ALTER TABLE ai_questions ADD COLUMN created_at TEXT"
        )
    except sqlite3.OperationalError:
        pass

    connection.commit()

    connection.close()
init_db()