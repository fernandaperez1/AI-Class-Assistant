# Slides Directory

This directory stores the converted PDF files from PowerPoint presentations. NEED TO DELETE THE PDFS WHEN A CLASS GETS DELETED

## Structure

Each presentation gets converted to a PDF file:
```
slides/
  ├── class_1_presentation.pdf
  ├── class_2_presentation.pdf
  └── class_3_presentation.pdf
```

## How It Works

1. When a PPTX file is uploaded, it's saved to the `uploads/` directory
2. When the presentation is accessed, the backend:
   - Converts the PPTX to PDF using LibreOffice
   - Saves the PDF to this directory
   - Caches the PDF for subsequent requests
3. The frontend displays the PDF directly in an iframe

## Notes

- PDFs are generated on-demand when the presentation is first accessed
- Cached PDFs are reused for faster loading on subsequent visits (cz libreoffice is slow af)
- The directory is served by the Flask backend at `/api/presentations/<id>/pdf/<filename>`
- My original idea was rendering images, but it took up waaay too much space, this worked better xd
