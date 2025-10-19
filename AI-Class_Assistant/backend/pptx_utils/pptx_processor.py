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


def convert_pptx_to_images(pptx_path, output_dir=None, presentation_id=None):
    """
    Convert PPTX to individual PNG images using LibreOffice.
    Each slide becomes a separate image file.
    
    Args:
        pptx_path: Path to the PPTX file
        output_dir: Base directory for output (default: ./slides)
        presentation_id: ID to create subdirectory for this presentation
    
    ret:
        dict: {
            "image_dir": path to directory containing images,
            "slide_count": number of slides,
            "images": list of image filenames
        }
    """
    if not os.path.exists(pptx_path):
        raise FileNotFoundError(f"PPTX file not found: {pptx_path}")
    
    if output_dir is None:
        output_dir = "./slides"
    
    # organizing by folder (got tired of deleting 1 by 1)
    if presentation_id:
        image_dir = os.path.join(output_dir, f"presentation_{presentation_id}_images")
    else:
        base_name = Path(pptx_path).stem
        image_dir = os.path.join(output_dir, f"{base_name}_images")
    
    os.makedirs(image_dir, exist_ok=True)
    
    # Check if images already exist
    existing_images = sorted([f for f in os.listdir(image_dir) if f.endswith('.png')])
    if existing_images:
        print(f"Images already exist in: {image_dir}")
        return {
            "image_dir": image_dir,
            "slide_count": len(existing_images),
            "images": existing_images
        }
    
    try:
        # LibreOffice converts PPTX to PDF first, then we convert PDF to images
        # Alternative: Use --convert-to png directly (creates one image per slide) only if it fails, cz idk if it will work on deploy
        # first convert to PDF in a temp location
        temp_pdf = os.path.join(image_dir, "temp_presentation.pdf")
        
        subprocess.run([
            "libreoffice",
            "--headless",
            "--convert-to", "pdf",
            "--outdir", image_dir,
            pptx_path
        ], check=True, capture_output=True, text=True)
        
        pdf_files=[f for f in os.listdir(image_dir) if f.endswith('.pdf')]
        if not pdf_files:
            raise Exception("Failed to generate PDF from PPTX")
        pdf_path = os.path.join(image_dir, pdf_files[0])
        
        # Convert PDF to images using pdftoppm (part of poppler-utils) or ImageMagick
        # Using pdftoppm for better quality and performance
        try:
            # pdftoppm -png generates slide-1.png, slide-2.png, etc.
            subprocess.run([
                "pdftoppm",
                "-png",
                "-r", "150",  # 150 DPI, this is the quality, will adjust it, but 150 is good enough for now
                pdf_path,
                os.path.join(image_dir, "slide")
            ], check=True, capture_output=True, text=True)
        except FileNotFoundError:
            # fallback to ImageMagick (praying it wont happen xd)
            print("pdftoppm not found, using ImageMagick convert")
            subprocess.run([
                "convert",
                "-density","150",
                pdf_path,
                os.path.join(image_dir, "slide-%d.png")
            ], check=True, capture_output=True, text=True)
        
        # Clean up temporary PDF
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        
        # Get list of generated images
        image_files = sorted([f for f in os.listdir(image_dir) if f.endswith('.png')])
        
        if not image_files:
            raise Exception("No images were generated")
        
        # rename images (slide-1.png, slide-2.png, etc.)
        # pdftoppm creates slide-1.png, slide-2.png automatically, but ImageMagick might use slide-0.png, this will prb add some weird edge cases that will break
        renamed_images = []
        for idx, img_file in enumerate(image_files, start=1):
            old_path = os.path.join(image_dir, img_file)
            new_name = f"slide-{idx}.png"
            new_path = os.path.join(image_dir, new_name)
            
            if old_path != new_path:
                os.rename(old_path, new_path)
            renamed_images.append(new_name)
        
        print(f"Successfully converted {len(renamed_images)} slides to images in: {image_dir}")
        
        return {
            "image_dir": image_dir,
            "slide_count": len(renamed_images),
            "images": renamed_images
        }
    
    except subprocess.CalledProcessError as e:
        raise Exception(f"Error converting PPTX to images: {e.stderr}")
    except Exception as e:
        raise Exception(f"Error converting PPTX to images: {str(e)}")
