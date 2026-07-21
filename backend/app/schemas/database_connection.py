from typing import Literal

from pydantic import BaseModel, Field, SecretStr


class DatabaseConnectionCreate(BaseModel):
    database_type: Literal["postgresql", "mysql"]
    host: str = Field(min_length=1)
    port: int = Field(gt=0, le=65535)
    database_name: str = Field(min_length=1)
    username: str = Field(min_length=1)
    password: SecretStr = Field(min_length=1)
    ssl_mode: str | None = "prefer"


class DatabaseConnectionResponse(BaseModel):
    success: bool
    message: str
    database_type: str
    database_name: str
