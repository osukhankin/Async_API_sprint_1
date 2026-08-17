from pydantic import BaseModel, Field


class Person(BaseModel):
    id: str
    name: str


class PersonFilm(BaseModel):
    id: str
    roles: list[str] = Field(default_factory=list)


class PersonFull(BaseModel):
    id: str
    full_name: str
    films: list[PersonFilm] = Field(default_factory=list)
