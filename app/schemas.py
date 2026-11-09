from pydantic import BaseModel, Field


class CourseIn(BaseModel):
    code: str = Field(min_length=2, max_length=20, examples=["CS F212"])
    name: str = Field(min_length=2, max_length=120)
    description: str = ""
    tags: list[str] = []


class CourseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class UserIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    name: str = Field(min_length=1, max_length=80)


class DocumentIn(BaseModel):
    course_id: str
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1)
    source: str = "upload"
    tags: list[str] = []


class DocumentUpdate(BaseModel):
    title: str | None = None
    tags: list[str] | None = None


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    course_id: str | None = None
    user_id: str | None = None
    k: int = Field(default=5, ge=1, le=20)
