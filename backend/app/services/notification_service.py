"""
Notification Service for WhatsApp, SMS, and proactive alerts
"""

from typing import Dict, Any, List, Optional
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import os

from config import settings

class NotificationService:
    """Unified notification service for WhatsApp, SMS"""
    
    def __init__(self):
        self.twilio_client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )
        self.whatsapp_from = "whatsapp:+14155238886"  # Twilio WhatsApp sandbox
        self.sms_from = settings.TWILIO_PHONE_NUMBER if hasattr(settings, 'TWILIO_PHONE_NUMBER') else None
    
    async def send_whatsapp_message(
        self,
        to_number: str,
        message: str,
        media_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send WhatsApp message"""
        
        try:
            # Format phone number for WhatsApp
            if not to_number.startswith('whatsapp:'):
                to_number = f"whatsapp:+91{to_number.replace('+91', '').replace(' ', '')}"
            
            message_data = {
                'from_': self.whatsapp_from,
                'to': to_number,
                'body': message
            }
            
            if media_url:
                message_data['media_url'] = [media_url]
            
            result = self.twilio_client.messages.create(**message_data)
            
            return {
                'success': True,
                'message_sid': result.sid,
                'status': result.status
            }
            
        except Exception as e:
            print(f"❌ WhatsApp Send Error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def send_invoice_whatsapp(
        self,
        to_number: str,
        pdf_path: str,
        invoice_number: str
    ) -> Dict[str, Any]:
        """Send invoice PDF via WhatsApp"""
        
        # In production, upload PDF to cloud storage and get public URL
        # For now, send message with invoice details
        
        message = f"""
📄 *Invoice Generated!*

Invoice #: {invoice_number}

आपका invoice तैयार है। PDF email में भेज दिया गया है।

Payment करने के लिए QR code scan करें या UPI से भेजें:
UPI ID: bharatbiz@paytm

धन्यवाद! 🙏
"""
        
        return await self.send_whatsapp_message(to_number, message)
    
    async def send_payment_reminder(
        self,
        to_number: str,
        invoices: List[Any],
        total_due: float
    ) -> Dict[str, Any]:
        """Send payment reminder via WhatsApp"""
        
        invoice_details = "\n".join([
            f"• Invoice #{inv.invoice_number}: ₹{inv.total_price}"
            for inv in invoices[:5]  # Limit to 5 invoices
        ])
        
        message = f"""
🔔 *Payment Reminder*

Namaste! आपके कुछ pending payments हैं:

{invoice_details}

*Total Due: ₹{total_due}*

कृपया जल्द से जल्द payment भेज दें।

💳 Payment Options:
• UPI: bharatbiz@paytm
• Scan QR code from invoice

किसी भी सवाल के लिए reply करें।

धन्यवाद! 🙏
"""
        
        return await self.send_whatsapp_message(to_number, message)
    
    async def send_low_stock_alert(
        self,
        to_number: str,
        product_name: str,
        current_quantity: int
    ) -> Dict[str, Any]:
        """Send low stock alert"""
        
        message = f"""
⚠️ *Low Stock Alert*

Product: {product_name}
Current Stock: {current_quantity} units

कृपया जल्द reorder करें!

Stock update करने के लिए message करें:
"Add 50 {product_name}"
"""
        
        return await self.send_whatsapp_message(to_number, message)
    
    async def send_confirmation_request(
        self,
        to_number: str,
        action_description: str,
        confirmation_id: int
    ) -> Dict[str, Any]:
        """Send human-in-the-loop confirmation request"""
        
        message = f"""
🤖 *Bharat Biz-Agent*

{action_description}

Reply:
• *Yes* to confirm
• *No* to cancel

(Confirmation ID: {confirmation_id})
"""
        
        return await self.send_whatsapp_message(to_number, message)
    
    async def send_action_completed(
        self,
        to_number: str,
        action_description: str,
        result_summary: str
    ) -> Dict[str, Any]:
        """Send action completion notification"""
        
        message = f"""
✅ *Action Completed*

{action_description}

{result_summary}

Anything else I can help with? Just message!
"""
        
        return await self.send_whatsapp_message(to_number, message)
    
    async def send_welcome_message(self, to_number: str, name: str) -> Dict[str, Any]:
        """Send welcome message to new users"""
        
        message = f"""
🙏 Namaste {name}!

Welcome to *Bharat Biz-Agent* - आपका AI business assistant!

मैं आपकी मदद कर सकता हूँ:
• 📄 Invoices बनाने में
• 💰 Payment reminders भेजने में
• 📦 Inventory manage करने में
• 📊 Business status देखने में

Examples:
• "Rahul ko 500 rupees ka bill bhej do"
• "Kitna stock bacha hai?"
• "Pending payments dikha do"

Just message me in Hindi, English, or Hinglish!

Let's grow your business together! 🚀
"""
        
        return await self.send_whatsapp_message(to_number, message)
    
    def create_whatsapp_response(self, message_text: str) -> str:
        """Create WhatsApp TwiML response"""
        
        resp = MessagingResponse()
        resp.message(message_text)
        return str(resp)


# Singleton instance
notification_service = NotificationService()
