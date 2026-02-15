from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Time, Float, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from .db import Base
import enum

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name= Column(String, nullable=False)
    mobile_number = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    created_at = Column(DateTime)
    invoices = relationship("Invoice", back_populates="user")
    payments = relationship("Payment", back_populates="user")

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
    unit_price = Column(Float, nullable=False, default=0.0)
    gst_rate = Column(Float, nullable=False, default=0.0)  # GST percentage
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)
    gst_amount = Column(Float, nullable=False, default=0.0)
    total_price = Column(Float, nullable=False)
    invoice_pdf_path = Column(String, nullable=True)
    payment_qr_code = Column(String, nullable=True)
    created_at = Column(DateTime)
    status = Column(String, default="pending")  # pending, paid, overdue

    user = relationship("User", back_populates="invoices")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    amount = Column(Float, nullable=False)
    payment_method = Column(String, nullable=False)  # UPI, Cash, Card
    upi_transaction_id = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, completed, failed
    created_at = Column(DateTime)
    
    user = relationship("User", back_populates="payments")

class ConversationContext(Base):
    """Store conversation context for proactive agent actions"""
    __tablename__ = "conversation_contexts"
    id = Column(Integer, primary_key=True, index=True)
    user_phone = Column(String, nullable=False, index=True)
    context_type = Column(String, nullable=False)  # invoice, payment, inventory
    context_data = Column(Text, nullable=True)  # JSON string
    last_interaction = Column(DateTime)
    created_at = Column(DateTime)

class PendingAction(Base):
    """Human-in-the-loop confirmation queue"""
    __tablename__ = "pending_actions"
    id = Column(Integer, primary_key=True, index=True)
    user_phone = Column(String, nullable=False)
    action_type = Column(String, nullable=False)  # send_invoice, send_reminder, update_inventory
    action_data = Column(Text, nullable=False)  # JSON string with action details
    confirmation_message = Column(Text, nullable=False)
    status = Column(String, default="pending")  # pending, confirmed, rejected, expired
    created_at = Column(DateTime)
    expires_at = Column(DateTime, nullable=True)
    
class ProactiveReminder(Base):
    """Schedule and track proactive reminders"""
    __tablename__ = "proactive_reminders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reminder_type = Column(String, nullable=False)  # payment_due, stock_low, follow_up
    message = Column(Text, nullable=False)
    scheduled_at = Column(DateTime)
    sent_at = Column(DateTime, nullable=True)
    status = Column(String, default="scheduled")  # scheduled, sent, cancelled