from pydantic import BaseModel


class StudentCreate(BaseModel):
    max_user_id: int
    name: str
    university: str | None = None
    faculty: str | None = None
    course: int | None = None
    description: str | None = None
    desired_topic: str | None = None
    photo_url: str | None = None

class SupervisorCreate(BaseModel):
    max_user_id: int
    name: str
    university: str | None = None
    department: str | None = None
    academic_degree: str | None = None
    description: str | None = None
    available_places: int = 0
    email: str | None = None
    photo_url: str | None = None

class InterestsUpdate(BaseModel):
    interest_ids: list[int]

class ApplicationCreate(BaseModel):
    student_id: int
    supervisor_id: int
    message: str | None = None

class EmailCodeVerify(BaseModel):
    code: str