from fastapi import FastAPI

from database import check_database

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import check_database, get_db
from schemas import StudentCreate, SupervisorCreate, InterestsUpdate, ApplicationCreate, EmailCodeVerify

from datetime import datetime, timedelta

from email_service import (
    generate_code,
    send_verification_email
)

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

@app.post("/supervisors")
def create_supervisor(
    supervisor: SupervisorCreate,
    db: Session = Depends(get_db)
):
    existing_user = db.execute(
        text("""
            SELECT id
            FROM users
            WHERE max_user_id = :max_user_id
        """),
        {
            "max_user_id": supervisor.max_user_id
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
                    'supervisor',
                    :name
                )
            """),
            {
                "max_user_id": supervisor.max_user_id,
                "name": supervisor.name
            }
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
                "email": supervisor.email
            }
        )

        supervisor_id = result.lastrowid

        db.commit()

        return {
            "status": "created",
            "user_id": user_id,
            "supervisor_id": supervisor_id
        }

    except Exception:
        db.rollback()
        raise

@app.get("/supervisors/{max_user_id}")
def get_supervisor(
    max_user_id: int,
    db: Session = Depends(get_db)
):
    result = db.execute(
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
                supervisors.is_active
            FROM users
            JOIN supervisors
                ON supervisors.user_id = users.id
            WHERE users.max_user_id = :max_user_id
        """),
        {
            "max_user_id": max_user_id
        }
    ).mappings().fetchone()

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Supervisor not found"
        )

    return dict(result)

@app.post("/students/{student_id}/interests")
def set_student_interests(
    student_id: int,
    data: InterestsUpdate,
    db: Session = Depends(get_db)
):
    # Проверяем, что студент существует
    student = db.execute(
        text("""
            SELECT id
            FROM students
            WHERE id = :student_id
        """),
        {"student_id": student_id}
    ).fetchone()

    if student is None:
        raise HTTPException(
            status_code=404,
            detail="Student not found"
        )

    try:
        # Удаляем старые интересы
        db.execute(
            text("""
                DELETE FROM student_interests
                WHERE student_id = :student_id
            """),
            {"student_id": student_id}
        )

        # Добавляем новые
        for interest_id in data.interest_ids:
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
                    "interest_id": interest_id
                }
            )

        db.commit()

        return {
            "status": "updated",
            "student_id": student_id,
            "interest_ids": data.interest_ids
        }

    except Exception:
        db.rollback()
        raise

@app.post("/supervisors/{supervisor_id}/interests")
def set_supervisor_interests(
    supervisor_id: int,
    data: InterestsUpdate,
    db: Session = Depends(get_db)
):
    supervisor = db.execute(
        text("""
            SELECT id
            FROM supervisors
            WHERE id = :supervisor_id
        """),
        {"supervisor_id": supervisor_id}
    ).fetchone()

    if supervisor is None:
        raise HTTPException(
            status_code=404,
            detail="Supervisor not found"
        )

    try:
        db.execute(
            text("""
                DELETE FROM supervisor_interests
                WHERE supervisor_id = :supervisor_id
            """),
            {"supervisor_id": supervisor_id}
        )

        for interest_id in data.interest_ids:
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
                    "interest_id": interest_id
                }
            )

        db.commit()

        return {
            "status": "updated",
            "supervisor_id": supervisor_id,
            "interest_ids": data.interest_ids
        }

    except Exception:
        db.rollback()
        raise

@app.get("/students/{student_id}/matches")
def get_matches(
    student_id: int,
    db: Session = Depends(get_db)
):
    student = db.execute(
        text("""
            SELECT id
            FROM students
            WHERE id = :student_id
        """),
        {"student_id": student_id}
    ).fetchone()

    if student is None:
        raise HTTPException(
            status_code=404,
            detail="Student not found"
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

                COUNT(*) AS common_interests,

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
                ON supervisor_interests.supervisor_id =
                   supervisors.id

            JOIN users
                ON supervisors.user_id = users.id

            WHERE
                student_interests.student_id = :student_id
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
                supervisors.available_places

            ORDER BY common_interests DESC
        """),
        {"student_id": student_id}
    ).mappings().all()

    return {
        "student_id": student_id,
        "matches": [dict(row) for row in matches]
    }

@app.post("/applications")
def create_application(
    application: ApplicationCreate,
    db: Session = Depends(get_db)
):
    # Проверяем студента
    student = db.execute(
        text("""
            SELECT id
            FROM students
            WHERE id = :student_id
        """),
        {"student_id": application.student_id}
    ).fetchone()

    if student is None:
        raise HTTPException(
            status_code=404,
            detail="Student not found"
        )

    # Проверяем руководителя
    supervisor = db.execute(
        text("""
            SELECT id, available_places, is_active
            FROM supervisors
            WHERE id = :supervisor_id
        """),
        {"supervisor_id": application.supervisor_id}
    ).mappings().fetchone()

    if supervisor is None:
        raise HTTPException(
            status_code=404,
            detail="Supervisor not found"
        )

    if supervisor["is_active"] != 1:
        raise HTTPException(
            status_code=400,
            detail="Supervisor is inactive"
        )

    if supervisor["available_places"] <= 0:
        raise HTTPException(
            status_code=400,
            detail="Supervisor has no available places"
        )

    # Проверяем, нет ли уже активной заявки
    existing_application = db.execute(
        text("""
            SELECT id
            FROM applications
            WHERE student_id = :student_id
              AND supervisor_id = :supervisor_id
              AND status = 'pending'
        """),
        {
            "student_id": application.student_id,
            "supervisor_id": application.supervisor_id
        }
    ).fetchone()

    if existing_application:
        raise HTTPException(
            status_code=409,
            detail="Pending application already exists"
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
            "message": application.message
        }
    )

    db.commit()

    return {
        "status": "created",
        "application_id": result.lastrowid
    }

@app.get("/students/{student_id}/applications")
def get_student_applications(
    student_id: int,
    db: Session = Depends(get_db)
):
    applications = db.execute(
        text("""
            SELECT
                applications.id AS application_id,
                applications.status,
                applications.message,
                applications.created_at,

                supervisors.id AS supervisor_id,
                users.name AS supervisor_name,
                supervisors.university,
                supervisors.department,
                supervisors.academic_degree

            FROM applications

            JOIN supervisors
                ON applications.supervisor_id = supervisors.id

            JOIN users
                ON supervisors.user_id = users.id

            WHERE applications.student_id = :student_id

            ORDER BY applications.created_at DESC
        """),
        {"student_id": student_id}
    ).mappings().all()

    return {
        "student_id": student_id,
        "applications": [dict(row) for row in applications]
    }

@app.get("/supervisors/{supervisor_id}/applications")
def get_supervisor_applications(
    supervisor_id: int,
    db: Session = Depends(get_db)
):
    applications = db.execute(
        text("""
            SELECT
                applications.id AS application_id,
                applications.status,
                applications.message,
                applications.created_at,

                students.id AS student_id,
                users.name AS student_name,
                students.university,
                students.faculty,
                students.course,
                students.desired_topic

            FROM applications

            JOIN students
                ON applications.student_id = students.id

            JOIN users
                ON students.user_id = users.id

            WHERE applications.supervisor_id = :supervisor_id

            ORDER BY applications.created_at DESC
        """),
        {"supervisor_id": supervisor_id}
    ).mappings().all()

    return {
        "supervisor_id": supervisor_id,
        "applications": [dict(row) for row in applications]
    }

@app.patch("/applications/{application_id}/accept")
def accept_application(
    application_id: int,
    db: Session = Depends(get_db)
):
    application = db.execute(
        text("""
            SELECT
                id,
                student_id,
                supervisor_id,
                status
            FROM applications
            WHERE id = :application_id
        """),
        {"application_id": application_id}
    ).mappings().fetchone()

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found"
        )

    if application["status"] != "pending":
        raise HTTPException(
            status_code=400,
            detail="Application is not pending"
        )

    supervisor = db.execute(
        text("""
            SELECT
                id,
                available_places
            FROM supervisors
            WHERE id = :supervisor_id
        """),
        {"supervisor_id": application["supervisor_id"]}
    ).mappings().fetchone()

    if supervisor is None:
        raise HTTPException(
            status_code=404,
            detail="Supervisor not found"
        )

    if supervisor["available_places"] <= 0:
        raise HTTPException(
            status_code=400,
            detail="Supervisor has no available places"
        )

    try:
        db.execute(
            text("""
                UPDATE applications
                SET status = 'accepted'
                WHERE id = :application_id
            """),
            {"application_id": application_id}
        )

        db.execute(
            text("""
                UPDATE supervisors
                SET available_places = available_places - 1
                WHERE id = :supervisor_id
            """),
            {"supervisor_id": application["supervisor_id"]}
        )

        db.commit()

        return {
            "status": "accepted",
            "application_id": application_id
        }

    except Exception:
        db.rollback()
        raise

@app.patch("/applications/{application_id}/reject")
def reject_application(
    application_id: int,
    db: Session = Depends(get_db)
):
    application = db.execute(
        text("""
            SELECT
                id,
                status
            FROM applications
            WHERE id = :application_id
        """),
        {"application_id": application_id}
    ).mappings().fetchone()

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found"
        )

    if application["status"] != "pending":
        raise HTTPException(
            status_code=400,
            detail="Application is not pending"
        )

    db.execute(
        text("""
            UPDATE applications
            SET status = 'rejected'
            WHERE id = :application_id
        """),
        {"application_id": application_id}
    )

    db.commit()

    return {
        "status": "rejected",
        "application_id": application_id
    }

@app.post("/supervisors/{supervisor_id}/email/check-domain")
def check_supervisor_email_domain(
    supervisor_id: int,
    db: Session = Depends(get_db)
):
    supervisor = db.execute(
        text("""
            SELECT
                id,
                university,
                email
            FROM supervisors
            WHERE id = :supervisor_id
        """),
        {"supervisor_id": supervisor_id}
    ).mappings().fetchone()

    if supervisor is None:
        raise HTTPException(
            status_code=404,
            detail="Supervisor not found"
        )

    if not supervisor["email"]:
        raise HTTPException(
            status_code=400,
            detail="Email is not specified"
        )

    if "@" not in supervisor["email"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid email"
        )

    email_domain = supervisor["email"].split("@")[-1].lower()

    university = db.execute(
        text("""
            SELECT id
            FROM universities
            WHERE name = :university
               OR short_name = :university
            LIMIT 1
        """),
        {
            "university": supervisor["university"]
        }
    ).mappings().fetchone()

    if university is None:
        raise HTTPException(
            status_code=404,
            detail="University not found in directory"
        )

    domain = db.execute(
        text("""
            SELECT id
            FROM university_domains
            WHERE university_id = :university_id
              AND domain = :domain
            LIMIT 1
        """),
        {
            "university_id": university["id"],
            "domain": email_domain
        }
    ).fetchone()

    if domain is None:
        return {
            "valid": False,
            "email_domain": email_domain,
            "reason": "Email domain does not match university"
        }

    return {
        "valid": True,
        "email_domain": email_domain,
        "university_id": university["id"]
    }

@app.post("/supervisors/{supervisor_id}/email/send-code")
def send_email_code(
    supervisor_id: int,
    db: Session = Depends(get_db)
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
        {"supervisor_id": supervisor_id}
    ).mappings().fetchone()

    if supervisor is None:
        raise HTTPException(
            status_code=404,
            detail="Supervisor not found"
        )

    if not supervisor["email"]:
        raise HTTPException(
            status_code=400,
            detail="Email is not specified"
        )

    email_domain = supervisor["email"].split("@")[-1].lower()

    university = db.execute(
        text("""
            SELECT id
            FROM universities
            WHERE name = :university
               OR short_name = :university
            LIMIT 1
        """),
        {
            "university": supervisor["university"]
        }
    ).mappings().fetchone()

    if university is None:
        raise HTTPException(
            status_code=404,
            detail="University not found"
        )

    valid_domain = db.execute(
        text("""
            SELECT id
            FROM university_domains
            WHERE university_id = :university_id
              AND domain = :domain
        """),
        {
            "university_id": university["id"],
            "domain": email_domain
        }
    ).fetchone()

    if valid_domain is None:
        raise HTTPException(
            status_code=400,
            detail="Email domain does not match university"
        )

    code = generate_code()

    expires_at = datetime.now() + timedelta(minutes=10)

    db.execute(
        text("""
            DELETE FROM email_verification_codes
            WHERE supervisor_id = :supervisor_id
        """),
        {
            "supervisor_id": supervisor_id
        }
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
            "expires_at": expires_at
        }
    )

    db.commit()

    send_verification_email(
        supervisor["email"],
        code
    )

    return {
        "status": "sent",
        "expires_in_seconds": 600
    }

@app.post("/supervisors/{supervisor_id}/email/verify-code")
def verify_email_code(
    supervisor_id: int,
    data: EmailCodeVerify,
    db: Session = Depends(get_db)
):
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
        {"supervisor_id": supervisor_id}
    ).mappings().fetchone()

    if verification is None:
        raise HTTPException(
            status_code=404,
            detail="Verification code not found"
        )

    if verification["expires_at"] < datetime.now():
        raise HTTPException(
            status_code=400,
            detail="Verification code has expired"
        )

    if verification["code"] != data.code:
        raise HTTPException(
            status_code=400,
            detail="Invalid verification code"
        )

    try:
        db.execute(
            text("""
                UPDATE supervisors
                SET
                    email_verified = TRUE,
                    verified_at = CURRENT_TIMESTAMP
                WHERE id = :supervisor_id
            """),
            {"supervisor_id": supervisor_id}
        )

        db.execute(
            text("""
                DELETE FROM email_verification_codes
                WHERE supervisor_id = :supervisor_id
            """),
            {"supervisor_id": supervisor_id}
        )

        db.commit()

        return {
            "status": "verified",
            "supervisor_id": supervisor_id,
            "email_verified": True
        }

    except Exception:
        db.rollback()
        raise