from flask import Flask, request, jsonify
from mysql.connector import connect, Error
from datetime import datetime
import pytz
import fitz  # PyMuPDF
import pytesseract
import re
import io
import os
import csv
from PIL import Image

# Set the path to the Tesseract OCR executable
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Set up Flask app
app = Flask(__name__)

# Set the timezone to your local timezone
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

# Function to extract a line starting with a specific word
def extract_line_starting_with(extracted_text, start_word):
    lines = extracted_text.splitlines()
    for line in lines:
        if line.strip().startswith(start_word):
            return line.strip()
    return None

# Function to extract student information
def extract_stud_info(extracted_text, degree):
    student_info = []
    student_line_regex = r"(\d{8})\s+([A-Za-z]+(?:\s+[A-Za-z]+)+)"
    result_regex = r"\b(P|F)\b"

    lines = extracted_text.splitlines()
    relevant_lines = [line.strip() for line in lines if line.strip()]

    current_student = {}
    for line in relevant_lines:
        student_match = re.search(student_line_regex, line)
        if student_match:
            seat_no = student_match.group(1)
            name = student_match.group(2)
            current_student = {
                'Seat No': seat_no,
                'Name': name,
                'Degree': degree
            }
        elif current_student and re.search(result_regex, line):
            result_match = re.search(result_regex, line)
            if result_match:
                result = result_match.group(1)
                current_student['Result'] = result
                student_info.append(current_student)
                current_student = {}

    return student_info

# Function to save data to CSV
def save_to_csv(student_info, year, filename, created_at):
    csv_file_path = f"/home/vboxuser/renuka/mumbai_univ/2021/Dec/{filename}_student_info.csv"
    os.makedirs(os.path.dirname(csv_file_path), exist_ok=True)

    try:
        with open(csv_file_path, mode='a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            if os.stat(csv_file_path).st_size == 0:
                writer.writerow(["Seat No", "Name", "Year", "Result", "Degree", "File Name", "Created At"])
            for student in student_info:
                writer.writerow([
                    student['Seat No'], 
                    student['Name'], 
                    year, 
                    student.get('Result', 'N/A'), 
                    student['Degree'], 
                    filename, 
                    created_at
                ])
    except Exception as e:
        print(f"Error saving to CSV: {e}")

@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    pdf_path = f"/home/vboxuser/renuka/mumbai_univ/2021/Dec/{file.filename}"  
    file.save(pdf_path)

    extracted_text = extract_text_from_pdf(pdf_path)
    year = extract_year(extracted_text)

    start_word = "OFFICE"
    degree = extract_line_starting_with(extracted_text, start_word) or "Unknown"

    created_at = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")
    stud_info = extract_stud_info(extracted_text, degree)

    if stud_info:
        conn = create_connection()
        if conn:
            try:
                cursor = conn.cursor()
                for student in stud_info:
                    cursor.execute(
                        "INSERT INTO mumbai_university_student_details(seat_no, name, reg_no, year, result, degree, filename, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (
                            student['Seat No'], 
                            student['Name'], 
                            '', 
                            year, 
                            student.get('Result', 'N/A'), 
                            student['Degree'], 
                            file.filename, 
                            created_at
                        )
                    )
                conn.commit()
            except Error as e:
                conn.rollback()
                print(f"Database error: {e}")
                return jsonify({'error': str(e)}), 500
            finally:
                cursor.close()
                conn.close()

            save_to_csv(stud_info, year, file.filename, created_at)
            return jsonify({"message": "Data inserted successfully", 'students': stud_info, 'year': year}), 201
        else:
            return jsonify({"error": "Database connection failed"}), 500
    else:
        return jsonify({"message": "No student data found!"})

if __name__ == '__main__':
    app.run(host='172.16.11.39', port=5001, debug=True)
