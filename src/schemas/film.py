from pydantic import BaseModel, ConfigDict, Field

from schemas.genre import Genre
from schemas.person import Person


class FilmResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: str = Field(validation_alias='id')
    title: str
    description: str | None = None
    imdb_rating: float | None = None
    genre: list[Genre] = Field(default_factory=list, validation_alias='genres')
    actors: list[Person] = Field(default_factory=list)
    directors: list[Person] = Field(default_factory=list)
    writers: list[Person] = Field(default_factory=list)


class FilmListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    uuid: str = Field(validation_alias='id')
    title: str
    imdb_rating: float | None = None
