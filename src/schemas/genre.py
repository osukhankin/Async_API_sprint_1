from pydantic import BaseModel, ConfigDict, Field


class Genre(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    uuid: str = Field(validation_alias='id')
    name: str
