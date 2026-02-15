"""
Invoice Generation Service with PDF creation and GST calculations
Tailored for Indian business requirements
"""

import os
from datetime import datetime
from typing import Dict, Any, List
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
import qrcode
from sqlalchemy.orm import Session

from database.models import Invoice, Inventory, User

class InvoiceService:
    """Generate professional invoices with GST compliance"""
    
    def __init__(self, db: Session):
        self.db = db
        self.invoice_dir = "invoices"
        os.makedirs(self.invoice_dir, exist_ok=True)
    
    async def generate_invoice(
        self,
        user_id: int,
        items: List[Dict[str, Any]],
        customer_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate complete invoice with PDF and QR code
        
        Args:
            user_id: Customer user ID
            items: List of items [{name, quantity, unit_price, gst_rate}]
            customer_data: Additional customer information
        
        Returns:
            Invoice data with PDF path and invoice number
        """
        
        # Generate unique invoice number
        invoice_number = self.generate_invoice_number()
        
        # Calculate totals
        calculations = self.calculate_invoice_totals(items)
        
        # Create invoice record in database
        invoice = Invoice(
            invoice_number=invoice_number,
            user_id=user_id,
            product_name=", ".join([item['name'] for item in items]),
            quantity=sum([item['quantity'] for item in items]),
            unit_price=calculations['subtotal'] / sum([item['quantity'] for item in items]),
            subtotal=calculations['subtotal'],
            gst_amount=calculations['total_gst'],
            total_price=calculations['grand_total'],
            status='pending',
            created_at=datetime.now()
        )
        
        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)
        
        # Generate PDF
        pdf_path = await self.create_invoice_pdf(
            invoice, items, calculations, customer_data
        )
        
        # Generate payment QR code
        qr_path = await self.generate_payment_qr(
            invoice_number, calculations['grand_total']
        )
        
        # Update invoice with file paths
        invoice.invoice_pdf_path = pdf_path
        invoice.payment_qr_code = qr_path
        self.db.commit()
        
        return {
            'invoice_id': invoice.id,
            'invoice_number': invoice_number,
            'subtotal': calculations['subtotal'],
            'gst': calculations['total_gst'],
            'total': calculations['grand_total'],
            'pdf_path': pdf_path,
            'qr_code_path': qr_path
        }
    
    def generate_invoice_number(self) -> str:
        """Generate unique invoice number in format: INV-YYYYMM-XXXX"""
        date_prefix = datetime.now().strftime("INV-%Y%m")
        
        # Get last invoice number for this month
        last_invoice = self.db.query(Invoice).filter(
            Invoice.invoice_number.like(f"{date_prefix}%")
        ).order_by(Invoice.id.desc()).first()
        
        if last_invoice:
            last_num = int(last_invoice.invoice_number.split('-')[-1])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f"{date_prefix}-{new_num:04d}"
    
    def calculate_invoice_totals(self, items: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate subtotal, GST, and grand total"""
        
        subtotal = 0
        total_gst = 0
        
        for item in items:
            item_subtotal = item['quantity'] * item['unit_price']
            item_gst = item_subtotal * (item.get('gst_rate', 18) / 100)
            
            item['item_subtotal'] = item_subtotal
            item['item_gst'] = item_gst
            item['item_total'] = item_subtotal + item_gst
            
            subtotal += item_subtotal
            total_gst += item_gst
        
        return {
            'subtotal': round(subtotal, 2),
            'total_gst': round(total_gst, 2),
            'grand_total': round(subtotal + total_gst, 2)
        }
    
    async def create_invoice_pdf(
        self,
        invoice: Invoice,
        items: List[Dict[str, Any]],
        calculations: Dict[str, float],
        customer_data: Dict[str, Any]
    ) -> str:
        """Create professional PDF invoice"""
        
        filename = f"{self.invoice_dir}/{invoice.invoice_number}.pdf"
        doc = SimpleDocTemplate(filename, pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a73e8'),
            alignment=TA_CENTER,
            spaceAfter=30
        )
        
        # Title
        story.append(Paragraph("TAX INVOICE / कर चालान", title_style))
        story.append(Spacer(1, 0.3*inch))
        
        # Business details (header)
        business_data = [
            ["Bharat Biz", ""],
            ["GST: 27XXXXX1234X1Z5", f"Invoice #: {invoice.invoice_number}"],
            ["Contact: +91-XXXXXXXXXX", f"Date: {invoice.created_at.strftime('%d-%m-%Y')}"],
        ]
        
        business_table = Table(business_data, colWidths=[3.5*inch, 3*inch])
        business_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        story.append(business_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Customer details
        user = invoice.user
        story.append(Paragraph(f"<b>Bill To / बिल प्राप्तकर्ता:</b>", styles['Normal']))
        story.append(Paragraph(f"{user.name}", styles['Normal']))
        story.append(Paragraph(f"Phone: {user.mobile_number}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Items table
        table_data = [
            ['Item\nआइटम', 'Qty\nमात्रा', 'Price\nमूल्य', 'GST %', 'GST Amt\nजीएसटी', 'Total\nकुल']
        ]
        
        for item in items:
            table_data.append([
                item['name'],
                str(item['quantity']),
                f"₹{item['unit_price']:.2f}",
                f"{item.get('gst_rate', 18)}%",
                f"₹{item['item_gst']:.2f}",
                f"₹{item['item_total']:.2f}"
            ])
        
        # Add totals
        table_data.append(['', '', '', '', 'Subtotal:', f"₹{calculations['subtotal']:.2f}"])
        table_data.append(['', '', '', '', 'Total GST:', f"₹{calculations['total_gst']:.2f}"])
        table_data.append(['', '', '', '', 'Grand Total:', f"₹{calculations['grand_total']:.2f}"])
        
        items_table = Table(table_data, colWidths=[2*inch, 0.6*inch, 1*inch, 0.7*inch, 0.9*inch, 1.2*inch])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a73e8')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -4), colors.beige),
            ('GRID', (0, 0), (-1, -4), 1, colors.black),
            ('FONTNAME', (0, -3), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8f5e9')),
            ('FONTSIZE', (0, -1), (-1, -1), 12),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 0.5*inch))
        
        # Payment instructions
        story.append(Paragraph("<b>Payment Instructions / भुगतान निर्देश:</b>", styles['Normal']))
        story.append(Paragraph("• UPI: bharatbiz@paytm", styles['Normal']))
        story.append(Paragraph("• Scan QR code below for instant payment", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Footer
        story.append(Paragraph(
            "<i>Thank you for your business! / आपके व्यापार के लिए धन्यवाद!</i>",
            ParagraphStyle('Footer', parent=styles['Normal'], alignment=TA_CENTER, textColor=colors.grey)
        ))
        
        # Build PDF
        doc.build(story)
        
        return filename
    
    async def generate_payment_qr(self, invoice_number: str, amount: float) -> str:
        """Generate UPI payment QR code"""
        
        # UPI payment string format
        upi_string = f"upi://pay?pa=bharatbiz@paytm&pn=BharatBiz&am={amount}&cu=INR&tn=Invoice-{invoice_number}"
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(upi_string)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save QR code
        qr_filename = f"{self.invoice_dir}/qr_{invoice_number}.png"
        img.save(qr_filename)
        
        return qr_filename
    
    def get_gst_rate_by_category(self, product_name: str) -> float:
        """
        Determine GST rate based on product category
        Following Indian GST slabs
        """
        
        # Essential goods (5%)
        essential_keywords = ['rice', 'wheat', 'flour', 'atta', 'dal', 'milk', 'sugar']
        
        # Standard goods (12%)
        standard_keywords = ['oil', 'ghee', 'butter', 'spices']
        
        # Regular goods (18%)
        # This is the default
        
        # Luxury goods (28%)
        luxury_keywords = ['chocolate', 'imported']
        
        product_lower = product_name.lower()
        
        if any(keyword in product_lower for keyword in essential_keywords):
            return 5.0
        elif any(keyword in product_lower for keyword in standard_keywords):
            return 12.0
        elif any(keyword in product_lower for keyword in luxury_keywords):
            return 28.0
        else:
            return 18.0  # Default standard rate


# Helper function to calculate GST breakdown
def get_gst_breakdown(amount: float, gst_rate: float) -> Dict[str, float]:
    """
    Calculate GST breakdown (CGST + SGST for intra-state)
    """
    
    gst_amount = amount * (gst_rate / 100)
    cgst = gst_amount / 2
    sgst = gst_amount / 2
    
    return {
        'base_amount': round(amount, 2),
        'gst_rate': gst_rate,
        'cgst': round(cgst, 2),
        'sgst': round(sgst, 2),
        'total_gst': round(gst_amount, 2),
        'total_amount': round(amount + gst_amount, 2)
    }
