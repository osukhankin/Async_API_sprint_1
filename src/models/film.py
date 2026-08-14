from pydantic import BaseModel, ConfigDict, Field

from models.genre import Genre
from models.person import Person


class Film(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str
    title: str
    description: str | None = None
    imdb_rating: float | None = None
    genres: list[Genre] = Field(default_factory=list)
    actors: list[Person] = Field(default_factory=list)
    directors: list[Person] = Field(default_factory=list)
    writers: list[Person] = Field(default_factory=list)


class FilmShort(BaseModel):
    id: str
    title: str
    imdb_rating: float | None = None
