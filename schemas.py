from pydantic import BaseModel


class StudentCreate(BaseModel):
    max_user_id: int
    name: str
    university: str | None = None
    faculty: str | None = None
    course: int | None = None
    description: str | None = None
    desired_topic: str | None = None