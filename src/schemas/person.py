from pydantic import BaseModel, ConfigDict, Field


class Person(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: str = Field(validation_alias='id')
    full_name: str = Field(validation_alias='name')


class PersonFilm(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: str = Field(validation_alias='id')
    roles: list[str] = Field(default_factory=list)


class PersonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: str = Field(validation_alias='id')
    full_name: str
    films: list[PersonFilm] = Field(default_factory=list)
