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
            host = '172.16.11.39',
            user = 'root',
            password = 'Sa@R3nuka1',
            database = 'educational_schema'
        )
        print("Dtabase connection successful")
        return conn
    except Error as err:
        print({"error connecting to MYSQL db", err})
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

# Function to extract student info using regex
def extract_stud_info(extracted_text, degree):
    regex = r'(\d{3})\s+(?:\s*/\s*)?([A-Z\s]+)\s+([0-9A-Z]+)\s+1\s+MUMBAI'

    matches = re.findall(regex, extracted_text)
    print(f"Matches found: {matches}")  # Debug print to see matched results

    student_info = []
    for match in matches:
        seat_no = match[0].strip()
        full_name = match[1].strip()
        reg_no = match[2].strip()

        if seat_no == '601':
            result = 'D'  # or whatever default result you want to use
        else:
            result=''    

        # Check if the name is valid and not just keywords
        if len(full_name.split()) >= 2:
            student_info.append((seat_no, full_name, reg_no, result, degree))

    return student_info


# Function to save data to CSV
def save_to_csv(student_info, year, filename, created_at):
    csv_file_path = f"/home/vboxuser/renuka/mumbai_univ/2017/{filename}_student_info.csv"
    with open(csv_file_path, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        # Write header only if the file is new
        if os.stat(csv_file_path).st_size == 0:
            writer.writerow(["Seat No", "Name", "Reg No", "Year", "Result", "Degree", "File Name", "Created At"])
        for seat_no, name, reg_no, result, degree in student_info:
            writer.writerow([seat_no, name, reg_no, year, result, degree, filename, created_at])


@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    pdf_path = f"\\home\\vboxuser\\renuka\\mumbai_univ\\2017\\{file.filename}"
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

            for seat_no, name, reg_no, result, degree in stud_info:
                try:
                    cursor.execute(
                        "INSERT INTO mumbai_university_student_details(seat_no, name, reg_no, year, result, degree, filename, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (seat_no, name, reg_no, year, result, degree, file.filename, created_at)
                    )
                    print(f"Inserted: {seat_no}, {name}, {year}, {result}, {degree}, {file.filename}")
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
    app.run(host='172.16.11.39', port= 5001, debug=True)
