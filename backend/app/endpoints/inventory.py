from fastapi import APIRouter, Depends, HTTPException, status
import datetime
from backend.app.database.models import Inventory
from backend.app.schema.inventory import InventoryOut, InventoryCreate, InventoryUpdate
from sqlalchemy.orm import Session
from database import db

router = APIRouter()

@router.post("/items/", response_model=InventoryOut, status_code=status.HTTP_201_CREATED)
def create_item(inventory: InventoryCreate,db: Session = Depends(db.get_db)):
    new_item = Inventory(
        id=inventory.id,
        product_name=inventory.product_name,
        available_quantity=inventory.available_quantity,
        created_at=datetime.datetime.now()
        
    )
    
    
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item

@router.put("/items/{item_id}", response_model=InventoryOut)
def update_item(item_id: int, inventory: InventoryUpdate, db: Session = Depends(db.get_db)):
    item = db.query(Inventory).filter(Inventory.id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    
    if inventory.product_name is not None:
        item.product_name = inventory.product_name
    if inventory.available_quantity is not None:
        item.available_quantity = inventory.available_quantity
    db.commit()
    db.refresh(item)
    return item

@router.get("/items/{item_id}", response_model=InventoryOut)
def read_item(item_id: int, db: Session = Depends(db.get_db)):
    item = db.query(Inventory).filter(Inventory.id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item

@router.get("/items/{name}", response_model=InventoryOut)
def read_item_by_name(name: str, db: Session = Depends(db.get_db)):
    item = db.query(Inventory).filter(Inventory.product_name == name).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item