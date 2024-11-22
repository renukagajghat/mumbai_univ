from flask import Flask, request, jsonify
from mysql.connector import connect, Error
from PIL import Image
from datetime import datetime
import pytesseract
import fitz
import pytz
import re
import os
import csv
import io

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

# Function to extract year from text
def extract_year(extracted_text):
    year_match = re.search(r'\b(20\d{2})\b', extracted_text)
    return year_match.group(0) if year_match else None

# Function to match starting word (OFFICE) from extracted_text
def extract_line_starting_with(extracted_text, start_word):
    lines = extracted_text.splitlines()
    for line in lines:
        if line.strip().startswith(start_word):
            return line.strip()
    return None     

# Function to save student info to CSV
def save_to_csv(student_info, year, filename, created_at):
    # Define CSV file path
    csv_file_path = f"/home/vboxuser/renuka/mumbai_univ/2021/Dec/{filename}_student_info.csv"
    
    # Open CSV file in append mode and handle encoding and newline issues
    try:
        with open(csv_file_path, mode='a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header only if the file is new or empty
            if os.stat(csv_file_path).st_size == 0:
                writer.writerow(["Seat No", "Name", "Year", "Result", "Degree", "File Name", "Created At"])
            
            # Write each student's information into the CSV file
            for entry in student_info:
                writer.writerow([
                    entry.get('Seat No'),
                    entry.get('Name'),
                    year,
                    entry.get('Result'),
                    entry.get('Degree', 'Unknown'),  # Use 'Unknown' if degree is missing
                    filename,
                    created_at
                ])
                
        print(f"Data successfully saved to CSV: {csv_file_path}")
    
    except Exception as e:
        print(f"Error saving data to CSV: {e}")

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

# Function to extract student info from the text
def extract_stud_info(extracted_text, degree):
    student_info = []
    student_line_regex = r"(\d{7,8})\s+([A-Za-z\s\/\-\.]+)"
    result_regex = r"\b(P|F|ABS|RLE)\b"  # Include additional result markers

    # Split lines and clean up
    lines = extracted_text.splitlines()
    relevant_lines = [line.strip() for line in lines if line.strip()]

    # print("PREVIEWING LINES:")
    for i, line in enumerate(relevant_lines[:20]):  # Preview first 20 lines
        print(f"{i + 1}: {line}")

    current_student = {}
    for line in relevant_lines:
        # Attempt to match seat number and name
        student_match = re.search(student_line_regex, line)
        if student_match:
            seat_no = student_match.group(1).strip()
            name = student_match.group(2).strip().replace('/', '')
            current_student = {
                'Seat No': seat_no,
                'Name': name,
                'Degree': degree
            }
            print(f"Matched Student: Seat No={seat_no}, Name={name}")

        # Attempt to match result for the current student
        elif current_student and re.search(result_regex, line):
            result_match = re.search(result_regex, line)
            if result_match:
                result = result_match.group(1)
                current_student['Result'] = result
                student_info.append(current_student)
                print(f"Matched Result for {current_student['Name']}: {result}")
                current_student = {}
        else:
            print(f"No match: {line}")

    if not student_info:
        print("No matches found. Please verify the regex or data format.")
    
    return student_info


# Endpoint to upload PDF
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
    year = re.search(r'\b(20\d{2})\b', extracted_text).group(0) if re.search(r'\b(20\d{2})\b', extracted_text) else None
    created_at = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")
    degree = extract_line_starting_with(extracted_text, 'OFFICE') or 'Unknown'
    
    stud_info = extract_stud_info(extracted_text, degree)
    
    conn = create_connection()
    if conn is None:
        return jsonify({"error": "Database connection failed"}), 500
    cursor = conn.cursor()

    for entry in stud_info:
        try:
            cursor.execute("INSERT INTO mumbai_university_student_details(seat_no, name, reg_no, year, result, degree, filename, created_at) VALUES(%s, %s, %s, %s, %s, %s, %s, %s) ",
                (entry['Seat No'], entry['Name'], '', year, entry['Result'], entry['Degree'], file.filename, created_at))
        except Error as err:
            print(f"Error inserting {entry['Seat No']}: {err}")
            conn.rollback()
            return jsonify({"error": str(err)})

    conn.commit()
    cursor.close()
    conn.close()

    save_to_csv(stud_info, year, file.filename, created_at)

    return jsonify({"Message": "Data Inserted Successfully", "students": stud_info, "year": year}), 201

if __name__ == '__main__':
    app.run(host='172.16.11.39', port=5001, debug=True)
