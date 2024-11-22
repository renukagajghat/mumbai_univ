
from flask import Flask, request, jsonify
from mysql.connector import connect, Error
from PIL import Image
from datetime import datetime
import fitz  # PyMuPDF
import pytz
import pytesseract
import re
import io
import os
import csv

# Set the path to the Tesseract OCR executable
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Set up Flask app
app = Flask(__name__)

local_tz = pytz.timezone('Asia/Kolkata')

# Create MySQL database connection
def create_connection():
    try:
        conn = connect(
            host="172.16.11.39",
            user="root",
            password="Sa@R3nuka1",
            database="educational_schema"
        )
        print("Database connection successful")
        return conn
    except Error as e:
        print(f"Error connecting to MySQL DB: {e}")
        return None

# Function to extract text from the PDF
def extract_text_from_pdf(pdf_path):
    document = fitz.open(pdf_path)
    full_text = ""

    for page in document:
        text = page.get_text()
        if text:
            full_text += text
        else:
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes()))
            img = img.convert('L')  # Convert to grayscale
            img = img.point(lambda x: 0 if x < 128 else 255, '1')  # Binarize
            text = pytesseract.image_to_string(img, config='--psm 6')
            full_text += text

    return full_text

# Function to extract year from text
def extract_year(extracted_text):
    year_match = re.search(r'\b(20\d{2})\b', extracted_text)
    return year_match.group(0) if year_match else None


#function to match starting word
def extract_line_starting_with(extracted_text, start_word):
    lines = extracted_text.splitlines()
    for line in lines:
        if line.strip().startswith(start_word):
            return line.strip()
    return None


def clean_and_merge_text(extracted_text):
    """Clean and merge related lines to form complete student records."""
    # Clean the text (remove excessive whitespace and newlines)
    cleaned_text = re.sub(r'\s+', ' ', extracted_text).strip()

    # Split the text back into lines and merge lines that belong to the same record
    lines = cleaned_text.split('-----------------------------------------------------------------------------------------------------------------------------------')
    
    merged_lines = []
    for i in range(1, len(lines)):
        line = lines[i].strip()
        if line:  # Skip empty lines
            merged_lines.append(line)
    
    # Rebuild text with merged lines
    merged_text = " ".join(merged_lines)
    
    return merged_text

def extract_stud_info(extracted_text, degree):
    """Extract seat numbers, full names, and results from the extracted text."""
    student_info = []
    lines = extracted_text.splitlines()

    for line in lines:
        # Regex pattern to capture seat number and full name
        match = re.search(r"(\d{7})\s*/([A-Z\s]+)\s+(.*)", line.strip())
        if match:
            seat_no = match.group(1)  # Seat number
            full_name = match.group(2).strip()  # Full name
            
            # Check for valid names, e.g., ensuring it's not part of a header/footer
            if (len(full_name.split()) >= 2 and 
                all(keyword not in full_name for keyword in ["OFFICE", "REGISTER", "FOR", "THE", "NULL"])):
                
                # Extract results if available
                results = match.group(3).strip()
                result_pattern = r"(A|P|F)"
                result_match = re.search(result_pattern, results)
                result = result_match.group(0) if result_match else "N/A"
                
                student_info.append((seat_no, full_name, result, degree))

    return student_info

# Function to save data to CSV
def save_to_csv(student_info, year, filename, created_at):
    csv_file_path = f"/home/vboxuser/renuka/mumbai_univ/2018/Dec/{filename}_student_info.csv"
    os.makedirs(os.path.dirname(csv_file_path), exist_ok=True)

    try:
        with open(csv_file_path, mode='a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            if os.stat(csv_file_path).st_size == 0:
                writer.writerow(["Seat No", "Name", "Year", "Result", "Degree", "File Name", "created_at"])
            for seat_no, name, result, degree in student_info:
                writer.writerow([seat_no, name, year, result, degree, filename, created_at])
    except Exception as e:
        print(f"Error saving to CSV: {e}")

@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    pdf_path = f"\\home\\vboxuser\\renuka\\mumbai_univ\\2018\\Dec\\{file.filename}"
    file.save(pdf_path)

    extracted_text = extract_text_from_pdf(pdf_path)

    year = extract_year(extracted_text)

    created_at = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")

    start_word = 'OFFICE'
    extracted_line = extract_line_starting_with(extracted_text, start_word)
    degree = extracted_line if extracted_line else 'Unknown'
    print(f"extracted degree:{degree}")

    stud_info = extract_stud_info(extracted_text, degree)
    # print("Extracted Student Info:", stud_info)
    if stud_info:
        conn = create_connection()
        if conn:
            cursor = conn.cursor()

            for seat_no, name, result, degree in stud_info:
                try:
                    cursor.execute(
                        "INSERT INTO mumbai_university_student_details(seat_no, name, reg_no, year, result, degree, filename, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (seat_no, name, '', year, result, degree, file.filename, created_at)
                    )
                    print(f"Inserted: {seat_no}, {name}, {year}, {result}, {degree}, {file.filename}, {created_at}")  # Log successful insert
                except Error as err:
                    print(f"Error inserting {seat_no}: {err}")  # Log error
                    conn.rollback()
                    return jsonify({'error': str(err)}), 500

            conn.commit()
            cursor.close()
            conn.close()

            # Save student info to CSV
            save_to_csv(stud_info, year, file.filename, created_at)

            return jsonify({"message": "Data inserted successfully", 'students': stud_info, 'year': year}), 201
        else:
            return jsonify({"error": "Database connection failed"}), 500

if __name__ == '__main__':
    app.run(host = '172.16.11.39', port=5001, debug=True)










































































