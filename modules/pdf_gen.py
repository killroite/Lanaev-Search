from fpdf import FPDF
import os
import uuid

def generate_pdf_report(query: str, data: dict) -> str:
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Arial", size=12)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="SWILL OSINT REPORT", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt=f"Target: {query}", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", size=12)
    for key, value in data.items():
        pdf.multi_cell(0, 10, txt=f"{key}: {value}")
        pdf.ln(2)
        
    filename = f"report_{uuid.uuid4().hex[:8]}.pdf"
    filepath = os.path.join("data", filename)
    pdf.output(filepath)
    
    return filepath
