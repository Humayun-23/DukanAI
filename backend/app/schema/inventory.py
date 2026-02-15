from pydantic import BaseModel, ConfigDict

class InventoryCreate(BaseModel):
    id: int
    product_name: str
    available_quantity: int
    created_at: str

class InventoryOut(InventoryCreate):
    pass
    model_config = ConfigDict(from_attributes=True)

class InventoryUpdate(BaseModel):
    product_name: str | None = None
    available_quantity: int | None = None
    model_config = ConfigDict(from_attributes=True)