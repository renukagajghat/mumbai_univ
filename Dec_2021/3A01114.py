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
            host = "172.16.11.39",
            user = "root",
            password = "Sa@R3nuka1",
            database = "educational_schema"
        
        )
        print("Database Connection Successfull")
        return conn

    except Error as err:
        print(f"Error to connecting MySQL db: {err}")   
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

    # Regex to capture seat number and name
    student_line_regex = r"(\d{4})\s+([A-Za-z\s\/\-\.]+)"
    # Regex to capture the result (P or F) in any format
    result_regex = r"\b(P|F)\b"

    lines = extracted_text.splitlines()
    current_student = {}

    for i, line in enumerate(lines):
        line = line.strip()

        # Match the student details line (seat no, name)
        student_match = re.search(student_line_regex, line)
        if student_match:
            if current_student:  # Save the previous student before overwriting
                if 'Result' not in current_student:
                    current_student['Result'] = ''  # No result found for this student
                student_info.append(current_student)

            seat_no = student_match.group(1).strip()
            full_name = student_match.group(2).strip()
            name = full_name.replace('/', '')

            if len(name.split()) >= 2 and all(
                keyword not in full_name for keyword in ["OFFICE", "REGISTER", "FOR", "THE", "NULL"]
            ):
                current_student = {
                    'Seat No': seat_no,
                    'Name': name,
                    'Degree': degree
                }
                print(f"Student details found: Seat No={seat_no}, Name={name}")

        # Match result in the current or subsequent lines
        if current_student and re.search(result_regex, line):
            result_match = re.search(result_regex, line)
            if result_match:
                current_student['Result'] = result_match.group(1).strip()
                print(f"Result found for {current_student['Name']}: {current_student['Result']}")

    # Append the last student if not added
    if current_student:
        if 'Result' not in current_student:
            current_student['Result'] = ''  # No result found for this student
        student_info.append(current_student)

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
    app.run(host='172.16.11.39', port=5002, debug=True)
