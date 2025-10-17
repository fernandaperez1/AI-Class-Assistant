import os
import subprocess
from pathlib import Path
from pptx import Presentation


def extract_text_from_pptx(pptx_path):
    """
    Extract text content from each slide in a PPTX file.
    Returns:
        list: A list of strings, where each string contains all text from one slide (will use it for the query, idk how much text I will include tho)
    """
    if not os.path.exists(pptx_path):
        raise FileNotFoundError(f"PPTX file not found: {pptx_path}")
    
    try:
        prs = Presentation(pptx_path)
        slides_text = []
        for slide_num, slide in enumerate(prs.slides, start=1):
            slide_text = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    slide_text.append(shape.text.strip())
            
            # Join all text from the slide
            full_slide_text = "\n".join(slide_text)
            slides_text.append(full_slide_text)
        
        return slides_text
    
    except Exception as e:
        raise Exception(f"Error extracting text from PPTX: {str(e)}")


def convert_pptx_to_pdf(pptx_path, output_dir=None):
    """
    Convert PPTX to PDF using LibreOffice.
    Returns:str: Path to generated PDF file
    """
    if not os.path.exists(pptx_path):
        raise FileNotFoundError(f"PPTX file not found: {pptx_path}")
    
    if output_dir is None:
        output_dir = "./slides"
    
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        base_name = Path(pptx_path).stem
        pdf_path = os.path.join(output_dir, f"{base_name}.pdf")
        
        if os.path.exists(pdf_path):
            print(f"PDF already exists: {pdf_path}")
            return pdf_path
        
        # libreoffice conversion to pdf, this shit might break in deploy
        result = subprocess.run([
            "libreoffice",
            "--headless",
            "--convert-to", "pdf",
            "--outdir", output_dir,
            pptx_path
        ], check=True, capture_output=True, text=True)
        
        if not os.path.exists(pdf_path):
            raise Exception("Failed to convert PPTX to PDF")
        
        print(f"Successfully converted to PDF: {pdf_path}")
        return pdf_path
    
    except subprocess.CalledProcessError as e:
        raise Exception(f"Error converting PPTX to PDF: {e.stderr}")
    except Exception as e:
        raise Exception(f"Error converting PPTX to PDF: {str(e)}")


def get_slide_count(pptx_path):
    """
    Get the number of slides in a PPTX file (will use it later for the ai gen slides)
    """
    if not os.path.exists(pptx_path):
        raise FileNotFoundError(f"PPTX file not found: {pptx_path}")
    
    try:
        prs = Presentation(pptx_path)
        return len(prs.slides)
    except Exception as e:
        raise Exception(f"Error reading PPTX: {str(e)}")
