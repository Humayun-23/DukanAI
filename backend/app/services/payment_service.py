"""
Payment Tracking Service with UPI integration and reminder system
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from database.models import Payment, Invoice, User
import razorpay

class PaymentService:
    """Handle payment tracking and UPI integrations"""
    
    def __init__(self, db: Session, razorpay_key: str = None, razorpay_secret: str = None):
        self.db = db
        
        # Initialize Razorpay client for UPI payments
        if razorpay_key and razorpay_secret:
            self.razorpay_client = razorpay.Client(auth=(razorpay_key, razorpay_secret))
        else:
            self.razorpay_client = None
    
    async def record_payment(
        self,
        user_id: int,
        amount: float,
        payment_method: str = "UPI",
        invoice_id: Optional[int] = None,
        transaction_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record a payment transaction"""
        
        try:
            payment = Payment(
                user_id=user_id,
                invoice_id=invoice_id,
                amount=amount,
                payment_method=payment_method,
                upi_transaction_id=transaction_id,
                status='completed',
                created_at=datetime.now()
            )
            
            self.db.add(payment)
            
            # Update invoice status if linked
            if invoice_id:
                invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()
                if invoice:
                    invoice.status = 'paid'
            
            self.db.commit()
            
            return {
                'success': True,
                'payment_id': payment.id,
                'message': f'Payment of ₹{amount} recorded successfully'
            }
            
        except Exception as e:
            self.db.rollback()
            return {
                'success': False,
                'message': f'Payment recording failed: {str(e)}'
            }
    
    async def create_upi_payment_link(
        self,
        invoice_id: int,
        amount: float,
        customer_name: str,
        customer_phone: str
    ) -> Dict[str, Any]:
        """Create UPI payment link via Razorpay"""
        
        if not self.razorpay_client:
            return {
                'success': False,
                'message': 'Payment gateway not configured'
            }
        
        try:
            # Create payment link
            payment_link_data = {
                "amount": int(amount * 100),  # Convert to paise
                "currency": "INR",
                "accept_partial": False,
                "description": f"Invoice Payment - {invoice_id}",
                "customer": {
                    "name": customer_name,
                    "contact": customer_phone
                },
                "notify": {
                    "sms": True,
                    "whatsapp": True
                },
                "callback_url": f"https://yourdomain.com/payment/callback",
                "callback_method": "get"
            }
            
            payment_link = self.razorpay_client.payment_link.create(payment_link_data)
            
            return {
                'success': True,
                'payment_link': payment_link['short_url'],
                'payment_id': payment_link['id']
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Payment link creation failed: {str(e)}'
            }
    
    def get_pending_payments(self, user_id: Optional[int] = None) -> List[Invoice]:
        """Get all pending invoices/payments"""
        
        query = self.db.query(Invoice).filter(Invoice.status == 'pending')
        
        if user_id:
            query = query.filter(Invoice.user_id == user_id)
        
        return query.all()
    
    def get_overdue_payments(self, days: int = 30) -> List[Invoice]:
        """Get payments overdue by specified days"""
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        overdue = self.db.query(Invoice).filter(
            and_(
                Invoice.status == 'pending',
                Invoice.created_at < cutoff_date
            )
        ).all()
        
        return overdue
    
    def get_payment_summary(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get payment summary statistics"""
        
        query = self.db.query(Invoice)
        if user_id:
            query = query.filter(Invoice.user_id == user_id)
        
        all_invoices = query.all()
        
        total_revenue = sum(inv.total_price for inv in all_invoices)
        paid_invoices = [inv for inv in all_invoices if inv.status == 'paid']
        pending_invoices = [inv for inv in all_invoices if inv.status == 'pending']
        
        total_paid = sum(inv.total_price for inv in paid_invoices)
        total_pending = sum(inv.total_price for inv in pending_invoices)
        
        return {
            'total_invoices': len(all_invoices),
            'paid_invoices': len(paid_invoices),
            'pending_invoices': len(pending_invoices),
            'total_revenue': round(total_revenue, 2),
            'total_paid': round(total_paid, 2),
            'total_pending': round(total_pending, 2),
            'collection_rate': round((total_paid / total_revenue * 100), 2) if total_revenue > 0 else 0
        }
    
    def get_customer_payment_history(self, user_id: int) -> Dict[str, Any]:
        """Get complete payment history for a customer"""
        
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return {'success': False, 'message': 'Customer not found'}
        
        invoices = self.db.query(Invoice).filter(Invoice.user_id == user_id).all()
        payments = self.db.query(Payment).filter(Payment.user_id == user_id).all()
        
        invoice_data = [{
            'invoice_number': inv.invoice_number,
            'date': inv.created_at.strftime('%d-%m-%Y'),
            'amount': inv.total_price,
            'status': inv.status
        } for inv in invoices]
        
        payment_data = [{
            'date': pay.created_at.strftime('%d-%m-%Y'),
            'amount': pay.amount,
            'method': pay.payment_method,
            'transaction_id': pay.upi_transaction_id
        } for pay in payments]
        
        total_invoiced = sum(inv.total_price for inv in invoices)
        total_paid = sum(pay.amount for pay in payments)
        
        return {
            'success': True,
            'customer_name': user.name,
            'customer_phone': user.mobile_number,
            'total_invoiced': round(total_invoiced, 2),
            'total_paid': round(total_paid, 2),
            'balance': round(total_invoiced - total_paid, 2),
            'invoices': invoice_data,
            'payments': payment_data
        }
    
    async def verify_upi_payment(self, transaction_id: str) -> Dict[str, Any]:
        """Verify UPI transaction status"""
        
        # Check if payment already recorded
        existing_payment = self.db.query(Payment).filter(
            Payment.upi_transaction_id == transaction_id
        ).first()
        
        if existing_payment:
            return {
                'success': True,
                'verified': True,
                'status': existing_payment.status,
                'amount': existing_payment.amount
            }
        
        # In production, verify with payment gateway
        # For now, return unverified
        return {
            'success': False,
            'verified': False,
            'message': 'Transaction not found'
        }


class ReminderService:
    """Automated payment reminder system"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def generate_reminder_message(
        self,
        customer_name: str,
        invoice_number: str,
        amount: float,
        days_overdue: int,
        tone: str = 'polite'
    ) -> str:
        """Generate payment reminder message in Hinglish"""
        
        if tone == 'polite' and days_overdue <= 15:
            return f"""
नमस्ते {customer_name}!

यह एक friendly reminder है।

Invoice: #{invoice_number}
Amount: ₹{amount}
Due since: {days_overdue} days

कृपया जल्द से जल्द payment भेज दीजिये।

UPI: bharatbiz@paytm
या QR code scan कर सकते हैं।

धन्यवाद! 🙏
"""
        elif tone == 'firm' and days_overdue > 15:
            return f"""
Dear {customer_name},

Invoice #{invoice_number} का payment ₹{amount} अभी तक pending है ({days_overdue} days overdue).

कृपया तुरंत payment करें।

UPI: bharatbiz@paytm

सहयोग के लिए धन्यवाद।
"""
        else:
            return f"""
Hi {customer_name}!

Payment reminder:
Invoice: #{invoice_number}
Amount: ₹{amount}
Pending: {days_overdue} days

Please pay at your earliest convenience.
UPI: bharatbiz@paytm

Thanks!
"""
    
    def get_customers_for_reminder(self, days_threshold: int = 15) -> List[Dict[str, Any]]:
        """Get list of customers who need payment reminders"""
        
        cutoff_date = datetime.now() - timedelta(days=days_threshold)
        
        overdue_invoices = self.db.query(Invoice).filter(
            and_(
                Invoice.status == 'pending',
                Invoice.created_at < cutoff_date
            )
        ).all()
        
        reminder_list = []
        
        for invoice in overdue_invoices:
            days_overdue = (datetime.now() - invoice.created_at).days
            
            reminder_list.append({
                'customer_id': invoice.user_id,
                'customer_name': invoice.user.name,
                'customer_phone': invoice.user.mobile_number,
                'invoice_id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'amount': invoice.total_price,
                'days_overdue': days_overdue,
                'tone': 'polite' if days_overdue <= 15 else 'firm'
            })
        
        return reminder_list
    
    def schedule_automated_reminders(self) -> Dict[str, Any]:
        """Schedule reminders based on overdue days"""
        
        # Day 15: Polite reminder
        day_15_customers = self.get_customers_for_reminder(days_threshold=15)
        
        # Day 30: Firm reminder
        day_30_customers = self.get_customers_for_reminder(days_threshold=30)
        
        return {
            'day_15_reminders': len(day_15_customers),
            'day_30_reminders': len(day_30_customers),
            'total_reminders': len(day_15_customers) + len(day_30_customers)
        }
