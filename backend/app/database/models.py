from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Time
from sqlalchemy.orm import relationship
from .db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name= Column(String, nullable=False)
    mobile_number = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    created_at = Column(DateTime)

class Admin(Base):
    __tablename__= "admins"
    id = Column(Integer, primary_key=True, index=True)
    name= Column(String, nullable=False)
    mobile_number = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime)
    
class Inventory(Base):
    __tablename__ = "inventory"
    id= Column(Integer, primary_key=True, index=True)
    product_name = Column(String, nullable=False)
    available_quantity = Column(Integer, nullable=False)
    created_at = Column(DateTime)

class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    total_price = Column(Integer, nullable=False)
    created_at = Column(DateTime)

    user = relationship("User", back_populates="invoices")