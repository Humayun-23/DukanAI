"""
Dashboard API endpoints for monitoring and management
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from database.db import get_db
from database.models import Invoice, Payment, Inventory, PendingAction, ProactiveReminder, User
from services.payment_service import PaymentService
from pydantic import BaseModel

router = APIRouter()


# Pydantic models for API responses
class DashboardStats(BaseModel):
    total_revenue: float
    total_pending: float
    total_paid: float
    pending_invoices: int
    overdue_invoices: int
    low_stock_items: int
    pending_actions: int


class InvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    customer_name: str
    customer_phone: str
    amount: float
    gst_amount: float
    total: float
    status: str
    created_at: datetime
    days_pending: Optional[int] = None
    
    class Config:
        from_attributes = True


class PendingActionResponse(BaseModel):
    id: int
    action_type: str
    confirmation_message: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """Get overall business statistics"""
    
    payment_service = PaymentService(db)
    summary = payment_service.get_payment_summary()
    
    # Count overdue invoices (30+ days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    overdue_count = db.query(Invoice).filter(
        Invoice.status == 'pending',
        Invoice.created_at < thirty_days_ago
    ).count()
    
    # Count low stock items
    low_stock_count = db.query(Inventory).filter(
        Inventory.available_quantity < 10
    ).count()
    
    # Count pending actions
    pending_actions_count = db.query(PendingAction).filter(
        PendingAction.status == 'pending'
    ).count()
    
    return DashboardStats(
        total_revenue=summary['total_revenue'],
        total_pending=summary['total_pending'],
        total_paid=summary['total_paid'],
        pending_invoices=summary['pending_invoices'],
        overdue_invoices=overdue_count,
        low_stock_items=low_stock_count,
        pending_actions=pending_actions_count
    )


@router.get("/invoices/pending", response_model=List[InvoiceResponse])
async def get_pending_invoices(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get all pending invoices"""
    
    invoices = db.query(Invoice).filter(
        Invoice.status == 'pending'
    ).order_by(Invoice.created_at.desc()).limit(limit).all()
    
    result = []
    for inv in invoices:
        days_pending = (datetime.now() - inv.created_at).days
        result.append(InvoiceResponse(
            id=inv.id,
            invoice_number=inv.invoice_number,
            customer_name=inv.user.name,
            customer_phone=inv.user.mobile_number,
            amount=inv.subtotal,
            gst_amount=inv.gst_amount,
            total=inv.total_price,
            status=inv.status,
            created_at=inv.created_at,
            days_pending=days_pending
        ))
    
    return result


@router.get("/invoices/overdue", response_model=List[InvoiceResponse])
async def get_overdue_invoices(
    days: int = Query(30, ge=1),
    db: Session = Depends(get_db)
):
    """Get overdue invoices"""
    
    cutoff_date = datetime.now() - timedelta(days=days)
    
    invoices = db.query(Invoice).filter(
        Invoice.status == 'pending',
        Invoice.created_at < cutoff_date
    ).order_by(Invoice.created_at).all()
    
    result = []
    for inv in invoices:
        days_overdue = (datetime.now() - inv.created_at).days
        result.append(InvoiceResponse(
            id=inv.id,
            invoice_number=inv.invoice_number,
            customer_name=inv.user.name,
            customer_phone=inv.user.mobile_number,
            amount=inv.subtotal,
            gst_amount=inv.gst_amount,
            total=inv.total_price,
            status=inv.status,
            created_at=inv.created_at,
            days_pending=days_overdue
        ))
    
    return result


@router.get("/actions/pending", response_model=List[PendingActionResponse])
async def get_pending_actions(db: Session = Depends(get_db)):
    """Get all pending actions awaiting confirmation"""
    
    actions = db.query(PendingAction).filter(
        PendingAction.status == 'pending'
    ).order_by(PendingAction.created_at.desc()).all()
    
    return [
        PendingActionResponse(
            id=action.id,
            action_type=action.action_type,
            confirmation_message=action.confirmation_message,
            status=action.status,
            created_at=action.created_at
        )
        for action in actions
    ]


@router.post("/actions/{action_id}/confirm")
async def confirm_pending_action(
    action_id: int,
    confirmed: bool,
    db: Session = Depends(get_db)
):
    """Manually confirm or reject a pending action"""
    
    from services.workflow_engine import WorkflowEngine
    
    workflow_engine = WorkflowEngine(db)
    result = await workflow_engine.confirm_action(action_id, confirmed)
    
    return result


@router.get("/inventory/low-stock")
async def get_low_stock_items(
    threshold: int = Query(10, ge=0),
    db: Session = Depends(get_db)
):
    """Get inventory items below threshold"""
    
    items = db.query(Inventory).filter(
        Inventory.available_quantity < threshold
    ).all()
    
    return [{
        'id': item.id,
        'product_name': item.product_name,
        'available_quantity': item.available_quantity,
        'unit_price': item.unit_price,
        'gst_rate': item.gst_rate
    } for item in items]


@router.get("/customers/top-debtors")
async def get_top_debtors(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get customers with highest pending amounts"""
    
    # Group invoices by user and sum pending amounts
    from sqlalchemy import func
    
    debtors = db.query(
        User.id,
        User.name,
        User.mobile_number,
        func.sum(Invoice.total_price).label('total_due'),
        func.count(Invoice.id).label('invoice_count')
    ).join(Invoice).filter(
        Invoice.status == 'pending'
    ).group_by(User.id).order_by(
        func.sum(Invoice.total_price).desc()
    ).limit(limit).all()
    
    return [{
        'customer_id': debtor[0],
        'customer_name': debtor[1],
        'customer_phone': debtor[2],
        'total_due': float(debtor[3]),
        'pending_invoices': debtor[4]
    } for debtor in debtors]


@router.get("/reminders/scheduled")
async def get_scheduled_reminders(db: Session = Depends(get_db)):
    """Get all scheduled proactive reminders"""
    
    reminders = db.query(ProactiveReminder).filter(
        ProactiveReminder.status == 'scheduled'
    ).order_by(ProactiveReminder.scheduled_at).all()
    
    return [{
        'id': reminder.id,
        'reminder_type': reminder.reminder_type,
        'message': reminder.message,
        'scheduled_at': reminder.scheduled_at,
        'customer_id': reminder.user_id
    } for reminder in reminders]


@router.get("/analytics/monthly")
async def get_monthly_analytics(db: Session = Depends(get_db)):
    """Get monthly business analytics"""
    
    from sqlalchemy import func, extract
    
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    # Monthly revenue
    monthly_invoices = db.query(
        func.sum(Invoice.total_price).label('total'),
        func.count(Invoice.id).label('count')
    ).filter(
        extract('month', Invoice.created_at) == current_month,
        extract('year', Invoice.created_at) == current_year
    ).first()
    
    # Monthly payments
    monthly_payments = db.query(
        func.sum(Payment.amount).label('total'),
        func.count(Payment.id).label('count')
    ).filter(
        extract('month', Payment.created_at) == current_month,
        extract('year', Payment.created_at) == current_year
    ).first()
    
    return {
        'month': datetime.now().strftime('%B %Y'),
        'invoices': {
            'total_amount': float(monthly_invoices[0] or 0),
            'count': monthly_invoices[1] or 0
        },
        'payments': {
            'total_amount': float(monthly_payments[0] or 0),
            'count': monthly_payments[1] or 0
        },
        'collection_rate': round(
            (float(monthly_payments[0] or 0) / float(monthly_invoices[0] or 1)) * 100, 2
        )
    }


@router.get("/customer/{customer_id}/history")
async def get_customer_history(customer_id: int, db: Session = Depends(get_db)):
    """Get complete transaction history for a customer"""
    
    payment_service = PaymentService(db)
    history = payment_service.get_customer_payment_history(customer_id)
    
    if not history['success']:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    return history
