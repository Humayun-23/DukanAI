"""
Proactive Agent Scheduler
Runs background tasks for payment reminders, low stock alerts, and follow-ups
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session

from database.db import SessionLocal
from database.models import Invoice, Inventory, ProactiveReminder, User
from services.notification_service import notification_service
from services.payment_service import ReminderService

class ProactiveScheduler:
    """Autonomous scheduling for proactive business actions"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.setup_jobs()
    
    def setup_jobs(self):
        """Setup all scheduled jobs"""
        
        # Daily payment reminder check (9 AM IST)
        self.scheduler.add_job(
            self.check_payment_reminders,
            CronTrigger(hour=9, minute=0, timezone='Asia/Kolkata'),
            id='daily_payment_reminders',
            name='Daily Payment Reminders',
            replace_existing=True
        )
        
        # Weekly overdue payment chase (Monday 10 AM IST)
        self.scheduler.add_job(
            self.chase_overdue_payments,
            CronTrigger(day_of_week='mon', hour=10, minute=0, timezone='Asia/Kolkata'),
            id='weekly_payment_chase',
            name='Weekly Overdue Payment Chase',
            replace_existing=True
        )
        
        # Low stock check (Every 6 hours)
        self.scheduler.add_job(
            self.check_low_stock,
            IntervalTrigger(hours=6),
            id='low_stock_check',
            name='Low Stock Alert Check',
            replace_existing=True
        )
        
        # Process pending reminders (Every 15 minutes)
        self.scheduler.add_job(
            self.process_pending_reminders,
            IntervalTrigger(minutes=15),
            id='process_reminders',
            name='Process Pending Reminders',
            replace_existing=True
        )
        
        # Monthly business summary (1st of month, 9 AM IST)
        self.scheduler.add_job(
            self.send_monthly_summary,
            CronTrigger(day=1, hour=9, minute=0, timezone='Asia/Kolkata'),
            id='monthly_summary',
            name='Monthly Business Summary',
            replace_existing=True
        )
    
    async def check_payment_reminders(self):
        """Check for payments due and send reminders"""
        
        print(f"🔔 [{datetime.now()}] Running payment reminder check...")
        
        db = SessionLocal()
        try:
            reminder_service = ReminderService(db)
            
            # Get customers needing reminders (15+ days overdue)
            customers = reminder_service.get_customers_for_reminder(days_threshold=15)
            
            reminders_sent = 0
            
            for customer in customers:
                message = reminder_service.generate_reminder_message(
                    customer['customer_name'],
                    customer['invoice_number'],
                    customer['amount'],
                    customer['days_overdue'],
                    tone=customer['tone']
                )
                
                # Send via WhatsApp
                result = await notification_service.send_whatsapp_message(
                    customer['customer_phone'],
                    message
                )
                
                if result['success']:
                    reminders_sent += 1
            
            print(f"✅ Sent {reminders_sent} payment reminders")
            
        except Exception as e:
            print(f"❌ Payment reminder error: {e}")
        finally:
            db.close()
    
    async def chase_overdue_payments(self):
        """Send firm reminders for payments overdue > 30 days"""
        
        print(f"🔔 [{datetime.now()}] Chasing overdue payments (30+ days)...")
        
        db = SessionLocal()
        try:
            reminder_service = ReminderService(db)
            
            # Get seriously overdue customers (30+ days)
            customers = reminder_service.get_customers_for_reminder(days_threshold=30)
            
            chased = 0
            
            for customer in customers:
                message = reminder_service.generate_reminder_message(
                    customer['customer_name'],
                    customer['invoice_number'],
                    customer['amount'],
                    customer['days_overdue'],
                    tone='firm'
                )
                
                result = await notification_service.send_whatsapp_message(
                    customer['customer_phone'],
                    message
                )
                
                if result['success']:
                    chased += 1
            
            print(f"✅ Chased {chased} overdue payments")
            
        except Exception as e:
            print(f"❌ Payment chase error: {e}")
        finally:
            db.close()
    
    async def check_low_stock(self):
        """Check inventory and alert for low stock"""
        
        print(f"📦 [{datetime.now()}] Checking inventory levels...")
        
        db = SessionLocal()
        try:
            # Find items with low stock (< 10 units)
            low_stock_items = db.query(Inventory).filter(
                Inventory.available_quantity < 10
            ).all()
            
            if not low_stock_items:
                print("✅ All stock levels are good")
                return
            
            # Get admin to notify
            from database.models import Admin
            admin = db.query(Admin).first()
            
            if not admin:
                print("⚠️ No admin found to notify")
                return
            
            # Send consolidated alert
            stock_list = "\n".join([
                f"• {item.product_name}: {item.available_quantity} units"
                for item in low_stock_items
            ])
            
            message = f"""
⚠️ *Low Stock Alert*

Following items need restocking:

{stock_list}

Please reorder soon!
"""
            
            await notification_service.send_whatsapp_message(
                admin.mobile_number,
                message
            )
            
            print(f"✅ Sent low stock alert for {len(low_stock_items)} items")
            
        except Exception as e:
            print(f"❌ Low stock check error: {e}")
        finally:
            db.close()
    
    async def process_pending_reminders(self):
        """Process scheduled proactive reminders"""
        
        db = SessionLocal()
        try:
            # Get reminders scheduled for now
            reminders = db.query(ProactiveReminder).filter(
                ProactiveReminder.status == 'scheduled',
                ProactiveReminder.scheduled_at <= datetime.now()
            ).all()
            
            if not reminders:
                return
            
            sent = 0
            
            for reminder in reminders:
                user = db.query(User).filter(User.id == reminder.user_id).first()
                
                if not user:
                    reminder.status = 'failed'
                    continue
                
                # Send reminder
                result = await notification_service.send_whatsapp_message(
                    user.mobile_number,
                    reminder.message
                )
                
                if result['success']:
                    reminder.status = 'sent'
                    reminder.sent_at = datetime.now()
                    sent += 1
                else:
                    reminder.status = 'failed'
            
            db.commit()
            
            if sent > 0:
                print(f"✅ Sent {sent} proactive reminders")
            
        except Exception as e:
            print(f"❌ Reminder processing error: {e}")
        finally:
            db.close()
    
    async def send_monthly_summary(self):
        """Send monthly business summary to admin"""
        
        print(f"📊 [{datetime.now()}] Generating monthly business summary...")
        
        db = SessionLocal()
        try:
            from database.models import Admin
            from services.payment_service import PaymentService
            
            admin = db.query(Admin).first()
            
            if not admin:
                print("⚠️ No admin found")
                return
            
            # Get payment summary
            payment_service = PaymentService(db)
            summary = payment_service.get_payment_summary()
            
            # Get month name
            last_month = (datetime.now().replace(day=1) - timedelta(days=1))
            month_name = last_month.strftime('%B %Y')
            
            message = f"""
📊 *Monthly Business Summary*
{month_name}

💰 *Revenue*
Total Invoices: {summary['total_invoices']}
Total Revenue: ₹{summary['total_revenue']}

💵 *Collections*
Paid: ₹{summary['total_paid']} ({summary['paid_invoices']} invoices)
Pending: ₹{summary['total_pending']} ({summary['pending_invoices']} invoices)

📈 *Collection Rate*
{summary['collection_rate']}%

Keep up the great work! 🚀

Need detailed report? Reply "detailed report"
"""
            
            await notification_service.send_whatsapp_message(
                admin.mobile_number,
                message
            )
            
            print(f"✅ Sent monthly summary to admin")
            
        except Exception as e:
            print(f"❌ Monthly summary error: {e}")
        finally:
            db.close()
    
    def start(self):
        """Start the scheduler"""
        
        print("🚀 Starting Proactive Agent Scheduler...")
        self.scheduler.start()
        print("✅ Scheduler started successfully")
        
        # Print all scheduled jobs
        jobs = self.scheduler.get_jobs()
        print(f"\n📅 Scheduled Jobs ({len(jobs)}):")
        for job in jobs:
            print(f"  • {job.name} - Next run: {job.next_run_time}")
    
    def stop(self):
        """Stop the scheduler"""
        
        print("🛑 Stopping scheduler...")
        self.scheduler.shutdown()
        print("✅ Scheduler stopped")


# Singleton instance
proactive_scheduler = ProactiveScheduler()
