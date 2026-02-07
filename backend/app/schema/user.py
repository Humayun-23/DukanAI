from pydantic import BaseModel, ConfigDict

class UserCreate(BaseModel):
    id: int
    name: str
    mobile_number: str
    password: str
    created_at: str
    model_config = ConfigDict(from_attributes=True)

class UserOut(BaseModel):
    name: str
    mobile_number: str
    model_config = ConfigDict(from_attributes=True)

class UserUpdate(BaseModel):
    name: str | None = None
    mobile_number: str | None = None
    password: str | None = None
    model_config = ConfigDict(from_attributes=True)

