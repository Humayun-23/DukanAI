"""
Bharat Biz-Agent Workflow Orchestration Engine
Autonomous execution of business workflows with human-in-the-loop confirmations
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database.models import (
    PendingAction, ConversationContext, Invoice, 
    Payment, Inventory, User, ProactiveReminder
)
from services import invoice_service, payment_service, notification_service

class WorkflowEngine:
    """Orchestrates autonomous business workflows"""
    
    def __init__(self, db: Session):
        self.db = db
        self.workflow_handlers = {
            'create_invoice': self.handle_create_invoice,
            'send_reminder': self.handle_send_reminder,
            'update_inventory': self.handle_update_inventory,
            'record_payment': self.handle_record_payment,
            'check_inventory': self.handle_check_inventory,
            'query_status': self.handle_query_status
        }
    
    async def execute_workflow(
        self, 
        intent: str, 
        extracted_data: Dict[str, Any],
        user_phone: str,
        requires_confirmation: bool = False
    ) -> Dict[str, Any]:
        """
        Main workflow execution entry point
        Routes to appropriate handler and manages confirmation flow
        """
        
        if intent not in self.workflow_handlers:
            return {
                'success': False,
                'message': f"Unknown workflow: {intent}",
                'requires_user_input': False
            }
        
        # Check if this requires human-in-the-loop confirmation
        if requires_confirmation:
            return await self.create_pending_action(
                user_phone, intent, extracted_data
            )
        
        # Execute workflow directly
        handler = self.workflow_handlers[intent]
        result = await handler(extracted_data, user_phone)
        
        # Store conversation context for proactive actions
        self.store_context(user_phone, intent, extracted_data, result)
        
        return result
    
    async def create_pending_action(
        self, 
        user_phone: str, 
        action_type: str, 
        action_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a pending action waiting for user confirmation"""
        
        # Generate confirmation message in Hinglish
        confirmation_msg = self.generate_confirmation_message(action_type, action_data)
        
        pending_action = PendingAction(
            user_phone=user_phone,
            action_type=action_type,
            action_data=json.dumps(action_data),
            confirmation_message=confirmation_msg,
            status='pending',
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24)
        )
        
        self.db.add(pending_action)
        self.db.commit()
        
        return {
            'success': True,
            'requires_confirmation': True,
            'pending_action_id': pending_action.id,
            'confirmation_message': confirmation_msg,
            'message': f"{confirmation_msg}\n\nReply 'Yes' to confirm or 'No' to cancel."
        }
    
    async def confirm_action(self, action_id: int, confirmed: bool) -> Dict[str, Any]:
        """Process user confirmation for pending action"""
        
        pending_action = self.db.query(PendingAction).filter(
            PendingAction.id == action_id,
            PendingAction.status == 'pending'
        ).first()
        
        if not pending_action:
            return {
                'success': False,
                'message': "Action not found or already processed."
            }
        
        if not confirmed:
            pending_action.status = 'rejected'
            self.db.commit()
            return {
                'success': True,
                'message': "Theek hai, action cancel kar diya. 👍"
            }
        
        # Execute the confirmed action
        action_data = json.loads(pending_action.action_data)
        handler = self.workflow_handlers[pending_action.action_type]
        result = await handler(action_data, pending_action.user_phone)
        
        pending_action.status = 'confirmed'
        self.db.commit()
        
        return result
    
    async def handle_create_invoice(
        self, 
        data: Dict[str, Any], 
        user_phone: str
    ) -> Dict[str, Any]:
        """Create and send invoice workflow"""
        
        try:
            # Get or create user
            user = self.get_or_create_user(data.get('customer_name'), user_phone)
            
            # Generate invoice
            invoice_data = await invoice_service.generate_invoice(
                user_id=user.id,
                items=data.get('items', []),
                customer_data=data
            )
            
            # Send via WhatsApp
            if invoice_data.get('pdf_path'):
                await notification_service.send_invoice_whatsapp(
                    user_phone, 
                    invoice_data['pdf_path'],
                    invoice_data['invoice_number']
                )
            
            return {
                'success': True,
                'action_taken': 'invoice_created',
                'invoice_number': invoice_data['invoice_number'],
                'message': f"✅ Invoice #{invoice_data['invoice_number']} bhej diya! Total: ₹{invoice_data['total']}"
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f"Invoice create nahi ho paya: {str(e)}"
            }
    
    async def handle_send_reminder(
        self, 
        data: Dict[str, Any], 
        user_phone: str
    ) -> Dict[str, Any]:
        """Send payment reminder workflow"""
        
        try:
            customer_name = data.get('customer_name')
            
            # Find pending invoices for this customer
            user = self.db.query(User).filter(
                User.name.ilike(f"%{customer_name}%")
            ).first()
            
            if not user:
                return {
                    'success': False,
                    'message': f"{customer_name} ka record nahi mila."
                }
            
            pending_invoices = self.db.query(Invoice).filter(
                Invoice.user_id == user.id,
                Invoice.status == 'pending'
            ).all()
            
            if not pending_invoices:
                return {
                    'success': True,
                    'message': f"{customer_name} ka koi pending payment nahi hai! 🎉"
                }
            
            # Send reminder via WhatsApp
            total_due = sum(inv.total_price for inv in pending_invoices)
            reminder_msg = await notification_service.send_payment_reminder(
                user.mobile_number,
                pending_invoices,
                total_due
            )
            
            return {
                'success': True,
                'action_taken': 'reminder_sent',
                'message': f"✅ {customer_name} ko payment reminder bhej diya! Due: ₹{total_due}"
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f"Reminder send nahi ho paya: {str(e)}"
            }
    
    async def handle_update_inventory(
        self, 
        data: Dict[str, Any], 
        user_phone: str
    ) -> Dict[str, Any]:
        """Update inventory stock workflow"""
        
        try:
            product_name = data.get('product')
            quantity = data.get('quantity', 0)
            
            # Find or create inventory item
            item = self.db.query(Inventory).filter(
                Inventory.product_name.ilike(f"%{product_name}%")
            ).first()
            
            if not item:
                # Create new item
                item = Inventory(
                    product_name=product_name,
                    available_quantity=quantity,
                    unit_price=data.get('unit_price', 0.0),
                    gst_rate=data.get('gst_rate', 18.0),
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                self.db.add(item)
                message = f"✅ Naya item add kiya: {product_name} - {quantity} units"
            else:
                # Update existing item
                item.available_quantity += quantity
                item.updated_at = datetime.now()
                message = f"✅ Stock update ho gaya! {product_name}: {item.available_quantity} units available"
            
            self.db.commit()
            
            # Check if stock is low and schedule reminder
            if item.available_quantity < 10:
                await self.schedule_low_stock_alert(item)
            
            return {
                'success': True,
                'action_taken': 'inventory_updated',
                'message': message
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f"Inventory update nahi ho paya: {str(e)}"
            }
    
    async def handle_record_payment(
        self, 
        data: Dict[str, Any], 
        user_phone: str
    ) -> Dict[str, Any]:
        """Record payment received workflow"""
        
        try:
            customer_name = data.get('customer_name')
            amount = data.get('amount', 0)
            payment_method = data.get('payment_method', 'UPI')
            
            user = self.db.query(User).filter(
                User.name.ilike(f"%{customer_name}%")
            ).first()
            
            if not user:
                return {
                    'success': False,
                    'message': f"{customer_name} ka record nahi mila."
                }
            
            # Create payment record
            payment = Payment(
                user_id=user.id,
                amount=amount,
                payment_method=payment_method,
                upi_transaction_id=data.get('transaction_id'),
                status='completed',
                created_at=datetime.now()
            )
            self.db.add(payment)
            
            # Update invoice status if linked
            if data.get('invoice_id'):
                invoice = self.db.query(Invoice).filter(
                    Invoice.id == data['invoice_id']
                ).first()
                if invoice:
                    invoice.status = 'paid'
            
            self.db.commit()
            
            return {
                'success': True,
                'action_taken': 'payment_recorded',
                'message': f"✅ Payment record kar liya! {customer_name}: ₹{amount} via {payment_method}"
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f"Payment record nahi ho paya: {str(e)}"
            }
    
    async def handle_check_inventory(
        self, 
        data: Dict[str, Any], 
        user_phone: str
    ) -> Dict[str, Any]:
        """Check inventory status workflow"""
        
        try:
            product_name = data.get('product')
            
            if product_name:
                # Check specific product
                item = self.db.query(Inventory).filter(
                    Inventory.product_name.ilike(f"%{product_name}%")
                ).first()
                
                if not item:
                    return {
                        'success': True,
                        'message': f"{product_name} stock mein nahi hai."
                    }
                
                return {
                    'success': True,
                    'message': f"📦 {item.product_name}: {item.available_quantity} units available"
                }
            else:
                # Get all inventory
                items = self.db.query(Inventory).all()
                
                if not items:
                    return {
                        'success': True,
                        'message': "Inventory khali hai."
                    }
                
                inventory_list = "\n".join([
                    f"• {item.product_name}: {item.available_quantity} units"
                    for item in items[:10]  # Limit to 10 items
                ])
                
                return {
                    'success': True,
                    'message': f"📦 Current Inventory:\n{inventory_list}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f"Inventory check nahi ho paya: {str(e)}"
            }
    
    async def handle_query_status(
        self, 
        data: Dict[str, Any], 
        user_phone: str
    ) -> Dict[str, Any]:
        """Query payment/invoice status workflow"""
        
        try:
            # Get all pending invoices
            pending_invoices = self.db.query(Invoice).filter(
                Invoice.status == 'pending'
            ).all()
            
            if not pending_invoices:
                return {
                    'success': True,
                    'message': "🎉 Sab payments clear hain! Koi pending nahi."
                }
            
            # Group by customer
            customer_dues = {}
            for invoice in pending_invoices:
                customer_name = invoice.user.name
                if customer_name not in customer_dues:
                    customer_dues[customer_name] = 0
                customer_dues[customer_name] += invoice.total_price
            
            status_text = "💰 Pending Payments:\n"
            for customer, amount in customer_dues.items():
                status_text += f"• {customer}: ₹{amount}\n"
            
            total_pending = sum(customer_dues.values())
            status_text += f"\nTotal Pending: ₹{total_pending}"
            
            return {
                'success': True,
                'message': status_text
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f"Status check nahi ho paya: {str(e)}"
            }
    
    def generate_confirmation_message(
        self, 
        action_type: str, 
        action_data: Dict[str, Any]
    ) -> str:
        """Generate human-friendly confirmation message in Hinglish"""
        
        templates = {
            'create_invoice': f"📄 Kya main {action_data.get('customer_name', 'customer')} ko ₹{action_data.get('amount', 0)} ka invoice bhej doon?",
            'send_reminder': f"🔔 Kya main {action_data.get('customer_name', 'customer')} ko payment reminder bhej doon?",
            'update_inventory': f"📦 Kya main {action_data.get('product', 'item')} ka stock {action_data.get('quantity', 0)} units update kar doon?",
            'record_payment': f"💰 Kya main {action_data.get('customer_name', 'customer')} ka ₹{action_data.get('amount', 0)} payment record kar loon?"
        }
        
        return templates.get(action_type, "Kya main yeh action kar doon?")
    
    def store_context(
        self, 
        user_phone: str, 
        intent: str, 
        data: Dict[str, Any], 
        result: Dict[str, Any]
    ):
        """Store conversation context for proactive follow-ups"""
        
        context = ConversationContext(
            user_phone=user_phone,
            context_type=intent,
            context_data=json.dumps({
                'input_data': data,
                'result': result,
                'timestamp': datetime.now().isoformat()
            }),
            last_interaction=datetime.now(),
            created_at=datetime.now()
        )
        
        self.db.add(context)
        self.db.commit()
    
    def get_or_create_user(self, name: str, phone: str) -> User:
        """Get existing user or create new one"""
        
        user = self.db.query(User).filter(
            User.mobile_number == phone
        ).first()
        
        if not user:
            user = User(
                name=name,
                mobile_number=phone,
                password='',  # WhatsApp users don't need passwords
                created_at=datetime.now()
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        
        return user
    
    async def schedule_low_stock_alert(self, item: Inventory):
        """Schedule proactive low stock alert"""
        
        # Find admin to notify
        from database.models import Admin
        admin = self.db.query(Admin).first()
        
        if admin:
            reminder = ProactiveReminder(
                user_id=admin.id,
                reminder_type='stock_low',
                message=f"⚠️ Low Stock Alert: {item.product_name} - only {item.available_quantity} units left!",
                scheduled_at=datetime.now(),
                status='scheduled'
            )
            self.db.add(reminder)
            self.db.commit()


class ProactiveAgent:
    """Proactive agent for scheduled reminders and follow-ups"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def check_overdue_payments(self):
        """Check for overdue payments and send reminders"""
        
        # Find invoices pending for > 30 days
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        overdue_invoices = self.db.query(Invoice).filter(
            Invoice.status == 'pending',
            Invoice.created_at < thirty_days_ago
        ).all()
        
        for invoice in overdue_invoices:
            # Create proactive reminder
            reminder = ProactiveReminder(
                user_id=invoice.user_id,
                reminder_type='payment_due',
                message=f"Namaste {invoice.user.name}! Invoice #{invoice.invoice_number} ka payment ₹{invoice.total_price} pending hai (30+ days). Kripya jaldi bhej dijiye.",
                scheduled_at=datetime.now(),
                status='scheduled'
            )
            self.db.add(reminder)
        
        self.db.commit()
        return len(overdue_invoices)
    
    async def send_scheduled_reminders(self):
        """Send all scheduled reminders"""
        
        reminders = self.db.query(ProactiveReminder).filter(
            ProactiveReminder.status == 'scheduled',
            ProactiveReminder.scheduled_at <= datetime.now()
        ).all()
        
        for reminder in reminders:
            user = self.db.query(User).filter(User.id == reminder.user_id).first()
            if user:
                await notification_service.send_whatsapp_message(
                    user.mobile_number,
                    reminder.message
                )
                
                reminder.status = 'sent'
                reminder.sent_at = datetime.now()
        
        self.db.commit()
        return len(reminders)
