import json
import re
from typing import Dict, Any, List, Optional
import google.generativeai as genai
from langdetect import detect
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate
from config import settings

# Configure Gemini once
genai.configure(api_key=settings.GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

class HinglishNLPProcessor:
    """Enhanced NLP for Hinglish, Hindi, and code-mixed inputs"""
    
    def __init__(self):
        self.hinglish_patterns = {
            'payment': ['payment', 'paisa', 'paise', 'rupay', 'rupaye', 'pay', 'bhej', 'send', 'de do'],
            'invoice': ['bill', 'invoice', 'receipt', 'rakam', 'hisab', 'khata'],
            'reminder': ['yaad', 'reminder', 'pending', 'baaki', 'baki', 'chase'],
            'inventory': ['stock', 'maal', 'saman', 'item', 'product', 'cheez'],
            'quantity': ['kitna', 'how much', 'quantity', 'qty', 'number'],
            'tomorrow': ['kal', 'tomorrow'],
            'today': ['aaj', 'today'],
            'yesterday': ['kal', 'yesterday']
        }
    
    def detect_language_mix(self, text: str) -> Dict[str, Any]:
        """Detect if text is Hindi, English, or Hinglish"""
        try:
            lang = detect(text.lower())
            has_hindi = bool(re.search(r'[\u0900-\u097F]', text))
            has_english = bool(re.search(r'[a-zA-Z]', text))
            
            return {
                'primary_lang': lang,
                'is_hinglish': has_hindi and has_english,
                'is_hindi': has_hindi and not has_english,
                'is_english': has_english and not has_hindi
            }
        except:
            return {'primary_lang': 'unknown', 'is_hinglish': False, 'is_hindi': False, 'is_english': True}
    
    def normalize_hinglish(self, text: str) -> str:
        """Normalize common Hinglish variations"""
        # Common replacements
        replacements = {
            r'\bbhej\s*d[eo]\b': 'send',
            r'\bde\s*d[eo]\b': 'give',
            r'\bkar\s*d[eo]\b': 'do',
            r'\bpaisa|paise\b': 'rupees',
            r'\brupay|rupaye\b': 'rupees',
            r'\bkal\b': 'tomorrow',
            r'\baaj\b': 'today',
            r'\bmaal\b': 'stock',
            r'\bsaman\b': 'items',
        }
        
        normalized = text.lower()
        for pattern, replacement in replacements.items():
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        
        return normalized

def analyze_input(user_input: str, is_audio: bool = False, user_context: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Advanced AI-powered input analysis for Bharat Biz-Agent
    Supports: Hindi, English, Hinglish, Voice inputs
    """
    
    nlp = HinglishNLPProcessor()
    
    system_prompt = """
    You are the "Bharat Biz-Agent" - An autonomous AI assistant for Indian businesses.
    
    CRITICAL CAPABILITIES:
    1. Process Hindi, English, and Hinglish (code-mixed) inputs fluently
    2. Understand Indian business contexts: GST, UPI payments, informal credit cycles
    3. Extract structured data from conversational inputs
    4. Identify actionable intents and execute workflows
    
    SUPPORTED INTENTS:
    - "create_invoice": Generate bills/invoices (e.g., "Rahul ko 500 rupees ka bill bhej do")
    - "send_reminder": Payment chase reminders (e.g., "Rahul hasn't paid for 30 days")
    - "check_inventory": Stock queries (e.g., "Kitna stock bacha hai?")
    - "update_inventory": Stock updates (e.g., "10 kg aata add karo")
    - "record_payment": Record payment receipt (e.g., "Amit ne 1000 pay kiya")
    - "query_status": Check pending payments/bills
    - "general_chat": Casual conversation
    
    RESPONSE FORMAT (JSON ONLY):
    {
      "intent": "<intent_name>",
      "confidence": 0.0-1.0,
      "language_detected": "hindi|english|hinglish",
      "reply": "Natural Hinglish response (friendly, short)",
      "action_required": true/false,
      "extracted_data": {
        "customer_name": null,
        "amount": null,
        "product": null,
        "quantity": null,
        "date": null,
        "payment_method": null
      },
      "requires_confirmation": true/false,
      "confirmation_message": "Human-friendly confirmation prompt in Hinglish"
    }
    
    BUSINESS LOGIC RULES:
    - GST: Always calculate GST if product involves (standard: 18%, essential goods: 5-12%)
    - UPI: Prefer UPI as payment method for India
    - Amounts: Support both words (panchaso = 500) and numbers
    - Names: Indian names should be recognized (Rahul, Priya, Amit, etc.)
    - Credit Terms: Understand "30 days", "next week", "kal" for payment timelines
    
    RESPONSE TONE:
    - Friendly and conversational in Hinglish
    - Use "aapka" (formal) for first interaction, "tumhara" (informal) for repeat users
    - Add confirmatory phrases: "Bilkul!", "Done!", "Pakka!"
    
    USER CONTEXT (if available):
    {context}
    
    Now analyze this input and respond in JSON:
    """
    
    try:
        response = None
        context_str = json.dumps(user_context) if user_context else "{}"
        full_prompt = system_prompt.replace("{context}", context_str)
        
        if is_audio:
            # Upload the audio file to Gemini
            myfile = genai.upload_file("temp.mp3")
            response = model.generate_content([full_prompt, myfile])
        else:
            # Process text input with language analysis
            lang_info = nlp.detect_language_mix(user_input)
            normalized_input = nlp.normalize_hinglish(user_input)
            
            full_input = f"""
            Input Text: {user_input}
            Normalized: {normalized_input}
            Language Mix: {lang_info}
            """
            response = model.generate_content([full_prompt, full_input])
            
        # Clean and parse JSON output
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean_text)
        
        # Add language detection metadata
        if not is_audio:
            result['language_analysis'] = lang_info
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON Parse Error: {e}")
        print(f"Raw Response: {response.text if response else 'No response'}")
        return {
            "intent": "general_chat",
            "confidence": 0.3,
            "language_detected": "unknown",
            "reply": "Maaf kijiye, thoda confuse ho gaya. Kya aap phir se bol sakte hain?",
            "action_required": False,
            "requires_confirmation": False
        }
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return {
            "intent": "error",
            "confidence": 0.0,
            "language_detected": "unknown", 
            "reply": "Sorry yaar, server busy hai. Thodi der mein try karo.",
            "action_required": False,
            "requires_confirmation": False
        }

def generate_invoice_content(customer_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate invoice details with GST calculations"""
    
    system_prompt = """
    You are an invoice content generator for Indian businesses.
    
    Given customer transaction data, generate detailed invoice content including:
    - Proper item descriptions
    - GST calculations (use appropriate GST slabs)
    - Total amount breakdown
    - Professional invoice text in Hinglish
    
    Return JSON format:
    {
      "items": [{"name": "", "quantity": 0, "unit_price": 0, "gst_rate": 0, "gst_amount": 0, "total": 0}],
      "subtotal": 0,
      "total_gst": 0,
      "grand_total": 0,
      "invoice_text": "Bilingual professional text"
    }
    """
    
    try:
        response = model.generate_content([
            system_prompt,
            f"Customer Data: {json.dumps(customer_data)}"
        ])
        
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
        
    except Exception as e:
        print(f"❌ Invoice Generation Error: {e}")
        return {
            "items": [],
            "subtotal": 0,
            "total_gst": 0,
            "grand_total": 0,
            "invoice_text": "Error generating invoice"
        }