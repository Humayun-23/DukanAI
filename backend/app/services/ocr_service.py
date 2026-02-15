"""
OCR Service for Handwritten Bill Processing
Extract structured data from photos of handwritten bills
"""

import pytesseract
from PIL import Image
import re
from typing import Dict, Any, List, Optional
import google.generativeai as genai
from config import settings

genai.configure(api_key=settings.GOOGLE_API_KEY)
vision_model = genai.GenerativeModel('gemini-1.5-flash')


class OCRService:
    """Process handwritten bills and extract structured data"""
    
    def __init__(self):
        # Configure Tesseract (if needed)
        # pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
        pass
    
    async def process_bill_image(self, image_path: str) -> Dict[str, Any]:
        """
        Process bill image and extract structured data
        
        Args:
            image_path: Path to bill image
            
        Returns:
            Structured bill data with items and amounts
        """
        
        try:
            # Try Gemini Vision first (better accuracy for handwritten text)
            gemini_result = await self.process_with_gemini_vision(image_path)
            
            if gemini_result['success']:
                return gemini_result
            
            # Fallback to Tesseract OCR
            tesseract_result = await self.process_with_tesseract(image_path)
            return tesseract_result
            
        except Exception as e:
            return {
                'success': False,
                'error': f'OCR processing failed: {str(e)}'
            }
    
    async def process_with_gemini_vision(self, image_path: str) -> Dict[str, Any]:
        """Use Gemini Vision API for handwritten bill recognition"""
        
        try:
            # Upload image to Gemini
            image_file = genai.upload_file(image_path)
            
            prompt = """
            You are an expert at reading handwritten bills from Indian shops.
            
            Analyze this bill image and extract:
            1. Shop name (if visible)
            2. Date (if visible)
            3. List of items with quantities and prices
            4. Total amount
            5. Any payment information
            
            Output JSON format:
            {
              "shop_name": "string or null",
              "date": "DD-MM-YYYY or null",
              "items": [
                {
                  "name": "item name",
                  "quantity": "qty with unit (e.g., 2 kg)",
                  "unit_price": float,
                  "total": float
                }
              ],
              "subtotal": float,
              "total": float,
              "payment_method": "Cash/UPI/null",
              "notes": "any additional info"
            }
            
            Handle:
            - Hindi/English mixed text
            - Poor handwriting
            - Abbreviations (kg, pcs, doz)
            - Currency symbols (₹, Rs)
            """
            
            response = vision_model.generate_content([prompt, image_file])
            
            # Parse JSON response
            import json
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            bill_data = json.loads(clean_text)
            
            return {
                'success': True,
                'method': 'gemini_vision',
                'data': bill_data,
                'raw_text': None
            }
            
        except Exception as e:
            print(f"Gemini Vision error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def process_with_tesseract(self, image_path: str) -> Dict[str, Any]:
        """Fallback OCR using Tesseract"""
        
        try:
            # Open and preprocess image
            image = Image.open(image_path)
            
            # Convert to grayscale
            image = image.convert('L')
            
            # OCR with Hindi + English
            extracted_text = pytesseract.image_to_string(
                image,
                lang='eng+hin',  # English + Hindi
                config='--psm 6'  # Assume uniform block of text
            )
            
            # Parse extracted text
            bill_data = self.parse_bill_text(extracted_text)
            
            return {
                'success': True,
                'method': 'tesseract',
                'data': bill_data,
                'raw_text': extracted_text
            }
            
        except Exception as e:
            print(f"Tesseract error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def parse_bill_text(self, text: str) -> Dict[str, Any]:
        """Parse raw OCR text into structured data"""
        
        lines = text.split('\n')
        items = []
        total = 0.0
        
        # Pattern matching for common bill formats
        item_pattern = r'(.+?)\s+(\d+\.?\d*)\s*(?:kg|pcs|doz|nos|ltr|gm)?\s+(\d+\.?\d*)'
        total_pattern = r'(?:total|grand total|amt|amount)[:\s]*(?:Rs\.?|₹)?\s*(\d+\.?\d*)'
        
        for line in lines:
            line = line.strip()
            
            # Try to match item line
            item_match = re.search(item_pattern, line, re.IGNORECASE)
            if item_match:
                item_name = item_match.group(1).strip()
                quantity = float(item_match.group(2))
                price = float(item_match.group(3))
                
                items.append({
                    'name': item_name,
                    'quantity': quantity,
                    'unit_price': price / quantity if quantity > 0 else price,
                    'total': price
                })
            
            # Try to match total line
            total_match = re.search(total_pattern, line, re.IGNORECASE)
            if total_match:
                total = float(total_match.group(1))
        
        # If total not found, calculate from items
        if total == 0 and items:
            total = sum(item['total'] for item in items)
        
        return {
            'shop_name': None,
            'date': None,
            'items': items,
            'subtotal': total,
            'total': total,
            'payment_method': None,
            'notes': 'Extracted via OCR'
        }
    
    async def create_digital_invoice_from_ocr(
        self,
        ocr_result: Dict[str, Any],
        customer_id: int,
        db
    ) -> Dict[str, Any]:
        """Convert OCR result to digital invoice"""
        
        if not ocr_result['success']:
            return {
                'success': False,
                'error': 'OCR failed'
            }
        
        bill_data = ocr_result['data']
        
        # Use invoice service to create proper invoice
        from services.invoice_service import InvoiceService
        
        invoice_service = InvoiceService(db)
        
        # Prepare items for invoice generation
        items = []
        for item in bill_data.get('items', []):
            items.append({
                'name': item['name'],
                'quantity': item.get('quantity', 1),
                'unit_price': item.get('unit_price', item.get('total', 0)),
                'gst_rate': 18.0  # Default GST rate
            })
        
        # Generate invoice
        invoice = await invoice_service.generate_invoice(
            user_id=customer_id,
            items=items,
            customer_data={
                'source': 'ocr',
                'original_shop': bill_data.get('shop_name'),
                'original_date': bill_data.get('date')
            }
        )
        
        return {
            'success': True,
            'invoice': invoice,
            'ocr_method': ocr_result['method']
        }


class SmartBillParser:
    """Intelligent bill parsing with AI assistance"""
    
    @staticmethod
    async def parse_ambiguous_bill(text: str) -> Dict[str, Any]:
        """Use AI to parse unclear or ambiguous bills"""
        
        prompt = f"""
        Parse this unclear bill text into structured JSON:
        
        {text}
        
        Extract:
        - Items (be intelligent about abbreviations)
        - Quantities (handle "doz", "pcs", "kg", "1/2 kg", etc.)
        - Prices (₹, Rs, or just numbers)
        - Total
        
        Common abbreviations:
        - AAT = Aata (Flour)
        - DAL = Dal (Lentils)
        - TEL = Tel (Oil)
        - CHI = Chini (Sugar)
        
        Output JSON only.
        """
        
        try:
            response = vision_model.generate_content(prompt)
            import json
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            return {'error': str(e)}
