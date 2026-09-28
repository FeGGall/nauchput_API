import os
import secrets
from datetime import datetime, timedelta
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import text
from sqlalchemy.orm import Session
from database import get_db, check_database
from schemas import (
    StudentCreate,
    SupervisorCreate,
    InterestsUpdate,
    ApplicationCreate,
    EmailCodeVerify,
)
from email_service import send_verification_email
load_dotenv()
API_KEY = os.getenv("API_KEY")
app = FastAPI(
    title="НаучПуть API",
    description="API сервиса подбора научных руководителей",
    version="1.0.0",
)
api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
)
def verify_api_key(api_key: str = Security(api_key_header)):
    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="API_KEY is not configured",
        )
    if api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )
@app.get("/")
def root():
    return {
        "service": "НаучПуть API",
        "status": "ok",
    }
@app.get("/health")
def health():
    return {
        "status": "ok",
    }
@app.get("/db-health")
def db_health():
    try:
        check_database()
        return {
            "database": "ok",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}",
        )
@app.post("/students")
def create_student(
    student: StudentCreate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    try:
        existing_user = db.execute(
            text("""
                SELECT id
                FROM users
                WHERE max_user_id = :max_user_id
            """),
            {
                "max_user_id": student.max_user_id,
            },
        ).mappings().first()
        if existing_user:
            raise HTTPException(
                status_code=409,
                detail="User with this max_user_id already exists",
            )
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
                "name": student.name,
            },
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
                    desired_topic,
                    photo_url
                )
                VALUES (
                    :user_id,
                    :university,
                    :faculty,
                    :course,
                    :description,
                    :desired_topic,
                    :photo_url
                )
            """),
            {
                "user_id": user_id,
                "university": student.university,
                "faculty": student.faculty,
                "course": student.course,
                "description": student.description,
                "desired_topic": student.desired_topic,
                "photo_url": student.photo_url,
            },
        )
        student_id = result.lastrowid
        db.commit()
        return {
            "status": "created",
            "student_id": student_id,
            "user_id": user_id,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
@app.get("/students/{max_user_id}")
def get_student(
    max_user_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    student = db.execute(
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
students.photo_url,
                students.is_active,
                users.created_at,
                users.updated_at
            FROM users
            JOIN students
                ON students.user_id = users.id
            WHERE users.max_user_id = :max_user_id
              AND users.role = 'student'
        """),
        {
            "max_user_id": max_user_id,
        },
    ).mappings().first()
    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student not found",
        )
    return dict(student)
@app.post("/students/{student_id}/interests")
def update_student_interests(
    student_id: int,
    data: InterestsUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    try:
        student = db.execute(
            text("""
                SELECT id
                FROM students
                WHERE id = :student_id
            """),
            {
                "student_id": student_id,
            },
        ).first()
        if not student:
            raise HTTPException(
                status_code=404,
                detail="Student not found",
            )
        db.execute(
            text("""
                DELETE FROM student_interests
                WHERE student_id = :student_id
            """),
            {
                "student_id": student_id,
            },
        )
        for interest_id in data.interest_ids:
            interest = db.execute(
                text("""
                    SELECT id
                    FROM research_interests
                    WHERE id = :interest_id
                """),
                {
                    "interest_id": interest_id,
                },
            ).first()
            if not interest:
                raise HTTPException(
                    status_code=400,
                    detail=f"Interest {interest_id} does not exist",
                )
            db.execute(
                text("""
                    INSERT INTO student_interests (
                        student_id,
                        interest_id
                    )
                    VALUES (
                        :student_id,
                        :interest_id
                    )
                """),
                {
                    "student_id": student_id,
                    "interest_id": interest_id,
                },
            )
        db.commit()
        return {
            "status": "updated",
            "student_id": student_id,
            "interest_ids": data.interest_ids,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
@app.get("/students/{student_id}/matches")
def get_student_matches(
    student_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    student = db.execute(
        text("""
            SELECT id
            FROM students
            WHERE id = :student_id
        """),
        {
            "student_id": student_id,
        },
    ).first()
    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student not found",
        )
    matches = db.execute(
        text("""
            SELECT
                supervisors.id AS supervisor_id,
                users.name,
                supervisors.university,
                supervisors.department,
                supervisors.academic_degree,
                supervisors.description,
                supervisors.available_places,
                supervisors.email,
                COUNT(research_interests.id) AS common_interests,
                GROUP_CONCAT(
                    research_interests.name
                    ORDER BY research_interests.name
                    SEPARATOR ', '
                ) AS matched_interests
            FROM student_interests
            JOIN supervisor_interests
                ON student_interests.interest_id =
                   supervisor_interests.interest_id
            JOIN research_interests
                ON research_interests.id =
                   student_interests.interest_id
            JOIN supervisors
                ON supervisors.id =
                   supervisor_interests.supervisor_id
            JOIN users
                ON users.id = supervisors.user_id
            WHERE student_interests.student_id = :student_id
              AND supervisors.is_active = 1
              AND supervisors.available_places > 0
              AND supervisors.email_verified = 1
            GROUP BY
                supervisors.id,
                users.name,
                supervisors.university,
                supervisors.department,
                supervisors.academic_degree,
                supervisors.description,
                supervisors.available_places,
                supervisors.email
            ORDER BY common_interests DESC
        """),
        {
            "student_id": student_id,
        },
    ).mappings().all()
    return {
        "student_id": student_id,
        "matches": [dict(match) for match in matches],
    }
@app.post("/supervisors")
def create_supervisor(
    supervisor: SupervisorCreate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    try:
        existing_user = db.execute(
            text("""
                SELECT id
                FROM users
                WHERE max_user_id = :max_user_id
            """),
            {
                "max_user_id": supervisor.max_user_id,
            },
        ).mappings().first()
        if existing_user:
            raise HTTPException(
                status_code=409,
                detail="User with this max_user_id already exists",
            )
        result = db.execute(
            text("""
                INSERT INTO users (
                    max_user_id,
                    role,
                    name
                )
                VALUES (
                    :max_user_id,
                    'supervisor',
                    :name
                )
            """),
            {
                "max_user_id": supervisor.max_user_id,
                "name": supervisor.name,
            },
        )
        user_id = result.lastrowid
        result = db.execute(
            text("""
                INSERT INTO supervisors (
                    user_id,
                    university,
                    department,
                    academic_degree,
                    description,
                    available_places,
                    email
                )
                VALUES (
                    :user_id,
                    :university,
                    :department,
                    :academic_degree,
                    :description,
                    :available_places,
                    :email
                )
            """),
            {
                "user_id": user_id,
                "university": supervisor.university,
                "department": supervisor.department,
                "academic_degree": supervisor.academic_degree,
                "description": supervisor.description,
                "available_places": supervisor.available_places,
                "email": supervisor.email,
            },
        )
        supervisor_id = result.lastrowid
        db.commit()
        return {
            "status": "created",
            "supervisor_id": supervisor_id,
            "user_id": user_id,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
@app.get("/supervisors/{max_user_id}")
def get_supervisor(
    max_user_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    supervisor = db.execute(
        text("""
            SELECT
                supervisors.id AS supervisor_id,
                users.id AS user_id,
                users.max_user_id,
                users.name,
                supervisors.university,
                supervisors.department,
                supervisors.academic_degree,
                supervisors.description,
                supervisors.available_places,
                supervisors.email,
                supervisors.email_verified,
                supervisors.supervisor_verified,
supervisors.verified_at,
                supervisors.photo_url,
                supervisors.is_active,
                users.created_at,
                users.updated_at
            FROM users
            JOIN supervisors
                ON supervisors.user_id = users.id
            WHERE users.max_user_id = :max_user_id
              AND users.role = 'supervisor'
        """),
        {
            "max_user_id": max_user_id,
        },
    ).mappings().first()
    if not supervisor:
        raise HTTPException(
            status_code=404,
            detail="Supervisor not found",
        )
    return dict(supervisor)
@app.post("/supervisors/{supervisor_id}/interests")
def update_supervisor_interests(
    supervisor_id: int,
    data: InterestsUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    try:
        supervisor = db.execute(
            text("""
                SELECT id
                FROM supervisors
                WHERE id = :supervisor_id
            """),
            {
                "supervisor_id": supervisor_id,
            },
        ).first()
        if not supervisor:
            raise HTTPException(
                status_code=404,
                detail="Supervisor not found",
            )
        db.execute(
            text("""
                DELETE FROM supervisor_interests
                WHERE supervisor_id = :supervisor_id
            """),
            {
                "supervisor_id": supervisor_id,
            },
        )
        for interest_id in data.interest_ids:
            interest = db.execute(
                text("""
                    SELECT id
                    FROM research_interests
                    WHERE id = :interest_id
                """),
                {
                    "interest_id": interest_id,
                },
            ).first()
            if not interest:
                raise HTTPException(
                    status_code=400,
                    detail=f"Interest {interest_id} does not exist",
                )
            db.execute(
                text("""
                    INSERT INTO supervisor_interests (
                        supervisor_id,
                        interest_id
                    )
                    VALUES (
                        :supervisor_id,
                        :interest_id
                    )
                """),
                {
                    "supervisor_id": supervisor_id,
                    "interest_id": interest_id,
                },
            )
        db.commit()
        return {
            "status": "updated",
            "supervisor_id": supervisor_id,
            "interest_ids": data.interest_ids,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
@app.post("/applications")
def create_application(
    application: ApplicationCreate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    try:
        student = db.execute(
            text("""
                SELECT id
                FROM students
                WHERE id = :student_id
                  AND is_active = 1
            """),
            {
                "student_id": application.student_id,
            },
        ).first()
        if not student:
            raise HTTPException(
                status_code=404,
                detail="Student not found",
            )
        supervisor = db.execute(
            text("""
                SELECT
                    id,
                    is_active,
                    available_places
                FROM supervisors
                WHERE id = :supervisor_id
            """),
            {
                "supervisor_id": application.supervisor_id,
            },
        ).mappings().first()
        if not supervisor:
            raise HTTPException(
                status_code=404,
                detail="Supervisor not found",
            )
        if not supervisor["is_active"]:
            raise HTTPException(
                status_code=400,
                detail="Supervisor is inactive",
            )
        if supervisor["available_places"] <= 0:
            raise HTTPException(
                status_code=400,
                detail="Supervisor has no available places",
            )
        existing = db.execute(
            text("""
                SELECT id
                FROM applications
                WHERE student_id = :student_id
                  AND supervisor_id = :supervisor_id
                  AND status = 'pending'
            """),
            {
                "student_id": application.student_id,
                "supervisor_id": application.supervisor_id,
            },
        ).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Pending application already exists",
            )
        result = db.execute(
            text("""
                INSERT INTO applications (
                    student_id,
                    supervisor_id,
                    message,
                    status
                )
                VALUES (
                    :student_id,
                    :supervisor_id,
                    :message,
                    'pending'
                )
            """),
            {
                "student_id": application.student_id,
                "supervisor_id": application.supervisor_id,
                "message": application.message,
            },
        )
        application_id = result.lastrowid
        db.commit()
        return {
            "status": "created",
            "application_id": application_id,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
@app.get("/students/{student_id}/applications")
def get_student_applications(
    student_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    applications = db.execute(
        text("""
            SELECT
                applications.id AS application_id,
                applications.student_id,
                applications.supervisor_id,
                applications.message,
                applications.status,
                applications.created_at,
                applications.updated_at,
                users.name AS supervisor_name,
                supervisors.university,
                supervisors.department,
                supervisors.academic_degree
            FROM applications
            JOIN supervisors
                ON supervisors.id = applications.supervisor_id
            JOIN users
                ON users.id = supervisors.user_id
            WHERE applications.student_id = :student_id
            ORDER BY applications.created_at DESC
        """),
        {
            "student_id": student_id,
        },
    ).mappings().all()
    return {
        "student_id": student_id,
        "applications": [dict(application) for application in applications],
    }
@app.get("/supervisors/{supervisor_id}/applications")
def get_supervisor_applications(
    supervisor_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    applications = db.execute(
        text("""
            SELECT
                applications.id AS application_id,
                applications.student_id,
                applications.supervisor_id,
                applications.message,
                applications.status,
                applications.created_at,
                applications.updated_at,
                users.name AS student_name,
                students.university,
                students.faculty,
                students.course,
                students.description,
                students.desired_topic
            FROM applications
            JOIN students
                ON students.id = applications.student_id
            JOIN users
                ON users.id = students.user_id
            WHERE applications.supervisor_id = :supervisor_id
            ORDER BY applications.created_at DESC
        """),
        {
            "supervisor_id": supervisor_id,
        },
    ).mappings().all()
    return {
        "supervisor_id": supervisor_id,
        "applications": [dict(application) for application in applications],
    }
@app.patch("/applications/{application_id}/accept")
def accept_application(
    application_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    try:
        application = db.execute(
            text("""
                SELECT
                    id,
                    supervisor_id,
                    status
                FROM applications
                WHERE id = :application_id
                FOR UPDATE
            """),
            {
                "application_id": application_id,
            },
        ).mappings().first()
        if not application:
            raise HTTPException(
                status_code=404,
                detail="Application not found",
            )
        if application["status"] != "pending":
            raise HTTPException(
                status_code=400,
                detail="Application is not pending",
            )
        supervisor = db.execute(
            text("""
                SELECT
                    id,
                    available_places
                FROM supervisors
                WHERE id = :supervisor_id
                FOR UPDATE
            """),
            {
                "supervisor_id": application["supervisor_id"],
            },
        ).mappings().first()
        if not supervisor:
            raise HTTPException(
                status_code=404,
                detail="Supervisor not found",
            )
        if supervisor["available_places"] <= 0:
            raise HTTPException(
                status_code=400,
                detail="Supervisor has no available places",
            )
        db.execute(
            text("""
                UPDATE applications
                SET status = 'accepted'
                WHERE id = :application_id
            """),
            {
                "application_id": application_id,
            },
        )
        db.execute(
            text("""
                UPDATE supervisors
                SET available_places = available_places - 1
                WHERE id = :supervisor_id
            """),
            {
                "supervisor_id": application["supervisor_id"],
            },
        )
        db.commit()
        return {
            "status": "accepted",
            "application_id": application_id,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
@app.patch("/applications/{application_id}/reject")
def reject_application(
    application_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    try:
        application = db.execute(
            text("""
                SELECT
                    id,
                    status
                FROM applications
                WHERE id = :application_id
            """),
            {
                "application_id": application_id,
            },
        ).mappings().first()
        if not application:
            raise HTTPException(
                status_code=404,
                detail="Application not found",
            )
        if application["status"] != "pending":
            raise HTTPException(
                status_code=400,
                detail="Application is not pending",
            )
        db.execute(
            text("""
                UPDATE applications
                SET status = 'rejected'
                WHERE id = :application_id
            """),
            {
                "application_id": application_id,
            },
        )
        db.commit()
        return {
            "status": "rejected",
            "application_id": application_id,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
@app.post("/supervisors/{supervisor_id}/email/check-domain")
def check_supervisor_email_domain(
    supervisor_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    supervisor = db.execute(
        text("""
            SELECT
                id,
                email,
                university
            FROM supervisors
            WHERE id = :supervisor_id
        """),
        {
            "supervisor_id": supervisor_id,
        },
    ).mappings().first()
    if not supervisor:
        raise HTTPException(
            status_code=404,
            detail="Supervisor not found",
        )
    email = supervisor["email"]
    if not email or "@" not in email:
        return {
            "valid": False,
            "detail": "Invalid email",
        }
    email_domain = email.rsplit("@", 1)[1].lower().strip()
    university = db.execute(
        text("""
            SELECT id
            FROM universities
            WHERE name = :university
               OR short_name = :university
            LIMIT 1
        """),
        {
            "university": supervisor["university"],
        },
    ).mappings().first()
    if not university:
        return {
            "valid": False,
            "detail": "University not found",
        }
    domain = db.execute(
        text("""
            SELECT id
            FROM university_domains
            WHERE university_id = :university_id
              AND LOWER(domain) = :domain
            LIMIT 1
        """),
        {
            "university_id": university["id"],
            "domain": email_domain,
        },
    ).first()
    return {
        "valid": domain is not None,
        "domain": email_domain,
    }
@app.post("/supervisors/{supervisor_id}/email/send-code")
def send_supervisor_email_code(
    supervisor_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    try:
        supervisor = db.execute(
            text("""
                SELECT
                    id,
                    email,
                    university
                FROM supervisors
                WHERE id = :supervisor_id
            """),
            {
                "supervisor_id": supervisor_id,
            },
        ).mappings().first()
        if not supervisor:
            raise HTTPException(
                status_code=404,
                detail="Supervisor not found",
            )
        email = supervisor["email"]
        if not email or "@" not in email:
            raise HTTPException(
                status_code=400,
                detail="Invalid email",
            )
        email_domain = email.rsplit("@", 1)[1].lower().strip()
        university = db.execute(
            text("""
                SELECT id
                FROM universities
                WHERE name = :university
                   OR short_name = :university
                LIMIT 1
            """),
            {
                "university": supervisor["university"],
            },
        ).mappings().first()
        if not university:
            raise HTTPException(
                status_code=400,
                detail="University not found",
            )
        allowed_domain = db.execute(
            text("""
                SELECT id
                FROM university_domains
                WHERE university_id = :university_id
                  AND LOWER(domain) = :domain
                LIMIT 1
            """),
            {
                "university_id": university["id"],
                "domain": email_domain,
            },
        ).first()
        if not allowed_domain:
            raise HTTPException(
                status_code=400,
                detail="Email domain does not match university",
            )
        code = f"{secrets.randbelow(1000000):06d}"
        expires_at = datetime.now() + timedelta(minutes=10)
        db.execute(
            text("""
                DELETE FROM email_verification_codes
                WHERE supervisor_id = :supervisor_id
            """),
            {
                "supervisor_id": supervisor_id,
            },
        )
        db.execute(
            text("""
                INSERT INTO email_verification_codes (
                    supervisor_id,
                    code,
                    expires_at
                )
                VALUES (
                    :supervisor_id,
                    :code,
                    :expires_at
                )
            """),
            {
                "supervisor_id": supervisor_id,
                "code": code,
                "expires_at": expires_at,
            },
        )
        db.commit()
        try:
            send_verification_email(email, code)
        except Exception as e:
            db.execute(
                text("""
                    DELETE FROM email_verification_codes
                    WHERE supervisor_id = :supervisor_id
                """),
                {
                    "supervisor_id": supervisor_id,
                },
            )
            db.commit()
            raise HTTPException(
                status_code=500,
                detail=f"Email sending error: {str(e)}",
            )
        return {
            "status": "sent",
            "expires_in_seconds": 600,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
@app.post("/supervisors/{supervisor_id}/email/verify-code")
def verify_supervisor_email_code(
    supervisor_id: int,
    data: EmailCodeVerify,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    try:
        supervisor = db.execute(
            text("""
                SELECT id
                FROM supervisors
                WHERE id = :supervisor_id
            """),
            {
                "supervisor_id": supervisor_id,
            },
        ).first()
        if not supervisor:
            raise HTTPException(
                status_code=404,
                detail="Supervisor not found",
            )
        verification = db.execute(
            text("""
                SELECT
                    id,
                    code,
                    expires_at
                FROM email_verification_codes
                WHERE supervisor_id = :supervisor_id
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {
                "supervisor_id": supervisor_id,
            },
        ).mappings().first()
        if not verification:
            raise HTTPException(
                status_code=400,
                detail="Verification code not found",
            )
        if datetime.now() > verification["expires_at"]:
            db.execute(
                text("""
                    DELETE FROM email_verification_codes
                    WHERE supervisor_id = :supervisor_id
                """),
                {
                    "supervisor_id": supervisor_id,
                },
            )
            db.commit()
            raise HTTPException(
                status_code=400,
                detail="Verification code expired",
            )
        if data.code != verification["code"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid verification code",
            )
        db.execute(
            text("""
                UPDATE supervisors
                SET
                    email_verified = TRUE,
                    verified_at = CURRENT_TIMESTAMP
                WHERE id = :supervisor_id
            """),
            {
                "supervisor_id": supervisor_id,
            },
        )
        db.execute(
            text("""
                DELETE FROM email_verification_codes
                WHERE supervisor_id = :supervisor_id
            """),
            {
                "supervisor_id": supervisor_id,
            },
        )
        db.commit()
        return {
            "status": "verified",
            "supervisor_id": supervisor_id,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
