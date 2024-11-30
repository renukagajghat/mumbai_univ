import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io

# Set the path to the Tesseract OCR executable
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file."""
    document = fitz.open(pdf_path)
    full_text = ""

    # Loop through each page in the PDF
    for page in document:
        text = page.get_text()

        if text:
            full_text += text
        else:
            # Use OCR if there's no text
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes()))
            img = img.convert('L')  # Convert to grayscale
            img = img.point(lambda x: 0 if x < 128 else 255, '1')  # Binarize
            text = pytesseract.image_to_string(img, config='--psm 6')
            full_text += text

    return full_text

# Path to your PDF file
pdf_path = 'C:/mumbai_university/FirstHalf2022/1A00116.pdf'

# Extract text from the PDF
text = extract_text_from_pdf(pdf_path)

# Print the entire extracted text for debugging
print("Extracted Text:\n", text[:10000])
