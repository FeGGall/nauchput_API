from fastapi import FastAPI

from database import check_database

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import check_database, get_db
from schemas import StudentCreate

app = FastAPI(
    title="НаучПуть API",
    version="0.1.0"
)


@app.get("/health")
def health():
    return {
        "status": "ok"
    }

@app.get("/")  
def root():
    return {
        "service": "НаучПуть API",
        "status": "running"
    }

@app.get("/db-health")
def db_health():
    return {
        "database": "ok" if check_database() else "error"
    }

@app.post("/students")
def create_student(
    student: StudentCreate,
    db: Session = Depends(get_db)
):
    
    existing_user = db.execute(
        text("""
            SELECT id
            FROM users
            WHERE max_user_id = :max_user_id
        """),
        {
            "max_user_id": student.max_user_id
        }
    ).fetchone()

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="User already exists"
        )

    try:
       
        result = db.execute(
            text("""
                INSERT INTO users (
                    max_user_id,
                    role,
                    name
                )
                VALUES (
                    :max_user_id,
                    'student',
                    :name
                )
            """),
            {
                "max_user_id": student.max_user_id,
                "name": student.name
            }
        )

        user_id = result.lastrowid

        
        result = db.execute(
            text("""
                INSERT INTO students (
                    user_id,
                    university,
                    faculty,
                    course,
                    description,
                    desired_topic
                )
                VALUES (
                    :user_id,
                    :university,
                    :faculty,
                    :course,
                    :description,
                    :desired_topic
                )
            """),
            {
                "user_id": user_id,
                "university": student.university,
                "faculty": student.faculty,
                "course": student.course,
                "description": student.description,
                "desired_topic": student.desired_topic
            }
        )

        student_id = result.lastrowid

        db.commit()

        return {
            "status": "created",
            "user_id": user_id,
            "student_id": student_id
        }

    except Exception:
        db.rollback()
        raise

@app.get("/students/{max_user_id}")
def get_student(
    max_user_id: int,
    db: Session = Depends(get_db)
):
    result = db.execute(
        text("""
            SELECT
                students.id AS student_id,
                users.id AS user_id,
                users.max_user_id,
                users.name,
                students.university,
                students.faculty,
                students.course,
                students.description,
                students.desired_topic,
                students.is_active
            FROM users
            JOIN students
                ON students.user_id = users.id
            WHERE users.max_user_id = :max_user_id
        """),
        {
            "max_user_id": max_user_id
        }
    ).mappings().fetchone()

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Student not found"
        )

    return dict(result)