from fastapi import APIRouter, Request, Form, Depends
from twilio.twiml.messaging_response import MessagingResponse
from sqlalchemy.orm import Session
import json
import re

from services import gemini, twilio
from services.workflow_engine import WorkflowEngine, ProactiveAgent
from services.notification_service import notification_service
from database import db
from database.models import ConversationContext, PendingAction

router = APIRouter()

@router.post("/whatsapp")
async def whatsapp_webhook(request: Request, db_session: Session = Depends(db.get_db)):
    """
    Main WhatsApp webhook for Bharat Biz-Agent
    Handles multilingual conversational input and autonomous workflow execution
    """
    
    form_data = await request.form()
    
    # Extract data from WhatsApp message
    media_url = form_data.get('MediaUrl0')
    body = form_data.get('Body', '').strip()
    from_number = form_data.get('From', '').replace('whatsapp:', '')
    
    # Initialize workflow engine
    workflow_engine = WorkflowEngine(db_session)
    
    # Check if this is a confirmation response (Yes/No)
    if body.lower() in ['yes', 'y', 'haan', 'ha', 'ok', 'confirm']:
        return await handle_confirmation(from_number, True, db_session)
    elif body.lower() in ['no', 'n', 'nahi', 'cancel']:
        return await handle_confirmation(from_number, False, db_session)
    
    # Get user context for proactive intelligence
    user_context = get_user_context(from_number, db_session)
    
    ai_response = {}
    
    # PERCEPTION LAYER: Process audio or text input
    if media_url:
        # Voice input - download and transcribe
        local_file = twilio.download_audio(media_url)
        if local_file:
            ai_response = gemini.analyze_input(local_file, is_audio=True, user_context=user_context)
    else:
        # Text input - process with Hinglish NLP
        ai_response = gemini.analyze_input(body, is_audio=False, user_context=user_context)
    
    # Extract key information
    intent = ai_response.get('intent', 'general_chat')
    reply_text = ai_response.get('reply', 'Samajh nahi aaya, phir se bolo?')
    action_required = ai_response.get('action_required', False)
    requires_confirmation = ai_response.get('requires_confirmation', False)
    extracted_data = ai_response.get('extracted_data', {})
    
    # ACTION LAYER: Execute workflows if action is required
    if action_required and intent != 'general_chat':
        try:
            workflow_result = await workflow_engine.execute_workflow(
                intent=intent,
                extracted_data=extracted_data,
                user_phone=from_number,
                requires_confirmation=requires_confirmation
            )
            
            if workflow_result['success']:
                reply_text = workflow_result['message']
                
                # If action requires confirmation, send follow-up
                if workflow_result.get('requires_confirmation'):
                    reply_text = workflow_result['confirmation_message']
            else:
                reply_text = workflow_result.get('message', 'Action failed. Please try again.')
                
        except Exception as e:
            print(f"❌ Workflow Error: {e}")
            reply_text = f"{reply_text}\n\n(Workflow execution mein issue aaya. Admin ko notify kar diya hai.)"
    
    # Add contextual suggestions
    if intent == 'general_chat':
        reply_text += "\n\nKya aap chahte hain:\n• Invoice create karoon?\n• Pending payments check karoon?\n• Stock status dekh loon?"
    
    # RESPONSE LAYER: Send WhatsApp response
    resp = MessagingResponse()
    resp.message(reply_text)
    
    return str(resp)


async def handle_confirmation(
    from_number: str, 
    confirmed: bool, 
    db_session: Session
) -> str:
    """Handle user confirmation for pending actions"""
    
    # Find most recent pending action for this user
    pending_action = db_session.query(PendingAction).filter(
        PendingAction.user_phone == from_number,
        PendingAction.status == 'pending'
    ).order_by(PendingAction.created_at.desc()).first()
    
    if not pending_action:
        resp = MessagingResponse()
        resp.message("Koi pending action nahi hai. Kya aap kuch aur karna chahte hain?")
        return str(resp)
    
    # Execute or cancel the action
    workflow_engine = WorkflowEngine(db_session)
    result = await workflow_engine.confirm_action(pending_action.id, confirmed)
    
    resp = MessagingResponse()
    resp.message(result['message'])
    return str(resp)


def get_user_context(phone: str, db_session: Session) -> dict:
    """Retrieve user's conversation context for proactive intelligence"""
    
    recent_contexts = db_session.query(ConversationContext).filter(
        ConversationContext.user_phone == phone
    ).order_by(ConversationContext.last_interaction.desc()).limit(5).all()
    
    if not recent_contexts:
        return {}
    
    context = {
        'recent_interactions': [],
        'frequent_actions': {}
    }
    
    for ctx in recent_contexts:
        try:
            context_data = json.loads(ctx.context_data)
            context['recent_interactions'].append({
                'type': ctx.context_type,
                'timestamp': ctx.last_interaction.isoformat(),
                'data': context_data
            })
        except:
            pass
    
    return context


@router.post("/whatsapp/status")
async def whatsapp_status_callback(request: Request):
    """Handle WhatsApp message status callbacks"""
    
    form_data = await request.form()
    
    message_sid = form_data.get('MessageSid')
    message_status = form_data.get('MessageStatus')
    
    print(f"📊 Message {message_sid} status: {message_status}")
    
    # Log status for monitoring
    # In production, update message delivery status in database
    
    return {"status": "ok"}


@router.get("/test-welcome")
async def test_welcome_message(phone: str):
    """Test endpoint to send welcome message"""
    
    result = await notification_service.send_welcome_message(phone, "Test User")
    return result