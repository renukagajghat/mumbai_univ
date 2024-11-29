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

# Set the path to the tesseract OCR executable
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Set up Flask app
app = Flask(__name__)

# Set local timezone
local_tz = pytz.timezone('Asia/Kolkata')

# Set database connection
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
            img = img.point(lambda x: 0 if x < 128 else 255, '1')
            text = pytesseract.image_to_string(img, config='--psm 6')
            full_text += text
    return full_text

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

# Function to extract student info from text using regex
def extract_stud_info(extracted_text, degree):
    student_info = []
    
    # First regex: Capture seat no, name, reg no (excluding result)
    student_regex = r"(\d{7})(?:\s*/\s*)?([A-Z\s]{2,})\s+([A-Z0-9]+)\s+(\d{3})"
    
    # Second regex: Capture result ('P' or 'F')
    result_regex = r"\s*(P|F)\s*"

    # Split text into lines
    lines = extracted_text.splitlines()

    for i, line in enumerate(lines):
        # Clean up extra spaces in each line
        line = re.sub(r'\s+', ' ', line.strip())
        
        # Debug: Print the current line to see what we're working with
        print(f"Processing line: {line}")
        
        # Find student info (without result)
        student_match = re.search(student_regex, line)
        
        if student_match:
            # Debug: Print the match groups for student info
            print(f"Student match found: {student_match.groups()}")
            
            # Extract student data
            seat_no = student_match.group(1).strip()
            full_name = student_match.group(2).strip()
            name = full_name.replace('/', '')  # Remove slashes from names
            regn_no = student_match.group(3).strip()
            result = None
            
            # Now, look for the result in the following lines
            result_match = re.search(result_regex, line)
            if result_match:
                result = result_match.group(1).strip()

            # If the result is not found on the current line, check the next line
            if not result:
                if i + 1 < len(lines):  # Safely get the next line
                    next_line = lines[i + 1]
                    result_match = re.search(result_regex, next_line)
                    if result_match:
                        result = result_match.group(1).strip()

            # If result is still None, we assign 'Unknown'
            if result is None:
                result = 'Unknown'
            
            # Append the student info to the list
            student_info.append({
                'Seat No': seat_no,
                'Name': name,
                'Regn No': regn_no,
                'Result': result,
                'Degree': degree,
            })

    return student_info




# Function to save data to CSV
def save_to_csv(student_info, year, filename, created_at):
    csv_file_path = f"/home/vboxuser/renuka/mumbai_univ/2021/Dec/{filename}_student_info.csv"
    with open(csv_file_path, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        # Write header only if the file is new
        if os.stat(csv_file_path).st_size == 0:
            writer.writerow(["Seat No", "Name", "Reg No", "Year", "Result", "File Name", "Created At"])
        for seat_no, name, reg_no, result, degree in student_info:
            writer.writerow([seat_no, name, reg_no, year, result, degree, filename, created_at])  

@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    # Set PDF path
    pdf_path = f"/home/vboxuser/renuka/mumbai_univ/2021/Dec/{file.filename}"  
    file.save(pdf_path)

    extracted_text = extract_text_from_pdf(pdf_path)
    print("Extracted Text:\n", extracted_text)

    year = extract_year(extracted_text)
    
    created_at = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")

    start_word = 'OFFICE'
    extracted_line = extract_line_starting_with(extracted_text, start_word)
    degree = extracted_line if extracted_line else 'Unknown'
    print("Degree:", degree)

    stud_info = extract_stud_info(extracted_text, degree)
    print("Extracted student info:", stud_info)

    conn = create_connection()
    if conn is None:
        return jsonify({"error": "Database connection failed"}), 500
    cursor = conn.cursor()

    for student in stud_info:
        seat_no = student['Seat No']
        name = student['Name']
        reg_no = student['Regn No']
        result = student['Result']
        degree = student['Degree']
        
        try:
            cursor.execute("INSERT INTO mumbai_university_student_details(seat_no, name, reg_no, year, result, degree, filename, created_at) VALUES(%s, %s, %s, %s, %s, %s, %s, %s)",
                (seat_no, name, reg_no, year, result, degree, file.filename, created_at))
            print(f"Inserted: {seat_no}, {name}, {reg_no}, {year}, {result}, {degree}, {file.filename}, {created_at}")

        except Error as err:
            print(f"Error inserting {seat_no}: {err}")
            conn.rollback()
            return jsonify({"error": str(err)})

    conn.commit()
    cursor.close()
    conn.close()
    
    # Save student info to CSV
    save_to_csv(stud_info, year, file.filename, created_at)

    return jsonify({"Message": "Data Inserted Successfully", "students": stud_info, "year": year}), 201


if __name__ == '__main__':
    app.run(host = "172.16.11.39", port = 5001, debug=True)
