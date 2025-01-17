from flask import Flask, request, jsonify
from mysql.connector import connect, Error
from datetime import datetime
from PIL import Image
import fitz  # PyMuPDF
import pytz #for local timezone
import pytesseract
import re
import io
import os
import csv

# Set the path to the Tesseract OCR executable
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Set up Flask app
app = Flask(__name__)

#set local timezone
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
            img = img.convert('L')
            img = img.point(lambda x: 0 if x < 128 else 255, '1')
            text = pytesseract.image_to_string(img, config='--psm 6')
            full_text += text

    return full_text

# Function to extract year from text
def extract_year(extracted_text):
    year_match = re.search(r'\b(20\d{2})\b', extracted_text)
    return year_match.group(0) if year_match else None


#function to match starting word(OFFICE) from extracted_text
def extract_line_starting_with(extracted_text, start_word):
    lines = extracted_text.splitlines()
    for line in lines:
        if line.strip().startswith(start_word):
            return line.strip()
    return None    

# Function to extract student info using regex
def extract_stud_info(extracted_text, degree):
    """Extract seat numbers, full names, and overall results from the extracted text."""
    # Refined regex to capture seat number, full name, result, and cgpa
    regex = r"(\d{2,5})\s+\/([A-Za-z\s]+)\s+.*?(P|F|AA)\s+.*?\s+(\d+\.\d{2})"

    # Extracting matches
    matches = re.findall(regex, extracted_text, re.DOTALL | re.MULTILINE)

    student_info = []
    for match in matches:
        seat_no = match[0].strip() if match[0].strip() else None
        name = match[1].strip() if match[1].strip() else None
        result = match[2] if match[2].strip() else None
        cgpa = match[3] if match[3].strip() else None

        # Exclude entries that may not be valid student names
        if (len(name.split()) >= 2 and 
            all(keyword not in name for keyword in ["OFFICE", "REGISTER", "FOR", "THE", "NULL"])):
            student_info.append((seat_no, name, result, cgpa, degree))

    return student_info

# Function to save data to CSV
def save_to_csv(student_info, year, filename, created_at):
    csv_file_path = f"/home/vboxuser/renuka/mumbai_univ/2018/Dec/{filename}_student_info.csv"
    os.makedirs(os.path.dirname(csv_file_path), exist_ok=True)

    try:
        with open(csv_file_path, mode='a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            if os.stat(csv_file_path).st_size == 0:
                writer.writerow(["Seat No", "Name", "Year", "Result", "CGPA", "Degree", "File Name", "Created At"])  # Added CGPA to header
            for seat_no, name, result, cgpa, degree in student_info:  # Unpacked to include cgpa
                writer.writerow([seat_no, name, year, result, cgpa, degree, filename, created_at])  # Include CGPA
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
    print(extracted_text)

    year = extract_year(extracted_text)

    start_word = "OFFICE"
    extracted_line = extract_line_starting_with(extracted_text, start_word)

    degree = extracted_line if extracted_line else "Unknown"
    print(f"Extracted Degree: {degree}")

    created_at = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")

    stud_info = extract_stud_info(extracted_text, degree)
    print("Extracted Student Info:", stud_info)

    if stud_info:
        conn = create_connection()
        if conn:
            cursor = conn.cursor()

            for seat_no, name, result, cgpa, degree in stud_info:  # Unpacked to include cgpa
                try:
                    cursor.execute(
                        "INSERT INTO mumbai_university_student_details(seat_no, name, reg_no, year, result, cgpa, degree, filename, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (seat_no, name, '', year, result, cgpa, degree, file.filename, created_at)
                    )
                    print(f"Inserted: {seat_no}, {name}, {year}, {result}, {cgpa}, {degree}, {file.filename}, {created_at}")
                except Error as err:
                    print(f"Error inserting {seat_no}: {err}")
                    conn.rollback()
                    cursor.close()
                    conn.close()
                    return jsonify({'error': str(err)}), 500

            conn.commit()
            cursor.close()
            conn.close()

            save_to_csv(stud_info, year, file.filename, created_at)

            return jsonify({"message": "Data inserted successfully", 'students': stud_info, 'year': year}), 201
        else:
            return jsonify({"error": "Database connection failed"}), 500
    else:
        return jsonify({"message": "No student data found!"})

if __name__ == '__main__':
    app.run(host = '172.16.11.39', port=5001, debug=True)
