from pydantic import BaseModel, Field, field_validator


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    priority: int = Field(ge=1, le=5)

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class TaskRead(BaseModel):
    id: int
    title: str
    priority: int
    is_done: bool
