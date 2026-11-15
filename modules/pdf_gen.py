from fpdf import FPDF
import os
import uuid

def generate_pdf_report(query: str, data: dict) -> str:
    pdf = FPDF()
    pdf.add_page()
    
    # Пытаемся найти системный шрифт с поддержкой кириллицы
    # На Linux-серверах Render (Ubuntu) обычно есть DejaVuSans
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
    ]
    
    font_added = False
    for path in font_paths:
        if os.path.exists(path):
            pdf.add_font("CustomFont", "", path, uni=True)
            pdf.set_font("CustomFont", size=12)
            font_added = True
            break
            
    if not font_added:
        # Если шрифты не найдены, ставим стандартный (будет с кракозябрами)
        pdf.set_font("Arial", size=12)
    
    font_name = "CustomFont" if font_added else "Arial"
    
    # Заголовок
    pdf.set_font(font_name, 'B', 16)
    pdf.cell(200, 10, txt="SWILL OSINT REPORT", ln=True, align='C')
    pdf.ln(10)
    
    # Данные запроса
    pdf.set_font(font_name, 'B', 14)
    pdf.cell(200, 10, txt=f"Target: {query}", ln=True)
    pdf.ln(5)
    
    # Вывод данных
    pdf.set_font(font_name, size=12)
    for key, value in data.items():
        pdf.multi_cell(0, 10, txt=f"{key}: {value}")
        pdf.ln(2)
        
    # Сохраняем файл
    filename = f"report_{uuid.uuid4().hex[:8]}.pdf"
    filepath = os.path.join("data", filename)
    pdf.output(filepath)
    
    return filepath
