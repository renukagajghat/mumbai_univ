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

#set the path to the tesseract OCR executable
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

#set up flask app
app = Flask(__name__)

#set local timezone
local_tz = pytz.timezone('Asia/Kolkata')

#set database connection

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

#function to extract text from the pdf
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
            img = img.convert('L') #convert grayscale
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

#function to extract stud info from text using regex
def extract_stud_info(extracted_text, degree):
    student_info = []

    # Pre-process text to normalize spaces and combine lines
    extracted_text = extracted_text.replace("\xa0", " ").replace("\t", " ").strip()
    lines = extracted_text.splitlines()
    
    # Regex to match the seat number and name from each line
    seat_and_name_pattern = re.compile(r"(\d{7})/([A-Za-z\s]+)")
    # Regex to match the result (P/F/AA/ABS) from subsequent lines
    result_pattern = re.compile(r"(\bP\b|\bF\b|\bAA\b|\bABS\b)")

    current_entry = {}
    for line_no, line in enumerate(lines, start=1):
        print(f"Processing line {line_no}: {line}")  # Debugging: Show each line

        # Match seat number and name
        seat_and_name_match = seat_and_name_pattern.search(line)
        if seat_and_name_match:
            print(f"Seat and Name Found: {seat_and_name_match.groups()}")  # Debugging
            current_entry['seat_no'] = seat_and_name_match.group(1).strip()
            current_entry['name'] = seat_and_name_match.group(2).strip()
            continue

        # Match result (look for P/F/AA/ABS)
        result_match = result_pattern.search(line)
        if result_match and 'seat_no' in current_entry:
            print(f"Result Found: {result_match.group(1)}")  # Debugging
            current_entry['result'] = result_match.group(1).strip()

            # Finalize the entry and reset
            student_info.append((
                current_entry['seat_no'],
                current_entry['name'],
                current_entry['result'],
                degree
            ))
            current_entry = {}  # Reset for the next student

    return student_info

# Function to save data to CSV
def save_to_csv(student_info, year, filename, created_at):
    csv_file_path = f"/home/vboxuser/renuka/mumbai_univ/2021/Dec/{filename}_student_info.csv"
    with open(csv_file_path, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        # Write header only if the file is new
        if os.stat(csv_file_path).st_size == 0:
            writer.writerow(["Seat No", "Name", "Year", "Result", "File Name", "Created At"])
        for seat_no, name, result, degree in student_info:
            writer.writerow([seat_no, name, year, result, degree, filename, created_at])  


@app.route('/upload', methods = ['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"error":"No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error":"No selected file"}), 400
    #set pdf path
    pdf_path = f"/home/vboxuser/renuka/mumbai_univ/2021/Dec/{file.filename}"  
    file.save(pdf_path)

    extracted_text = extract_text_from_pdf(pdf_path)

    year = extract_year(extracted_text)
    
    created_at = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")

    start_word = 'OFFICE'
    extracted_line = extract_line_starting_with(extracted_text, start_word)
    degree = extracted_line if extracted_line else 'Unknown'
    print(degree)

    stud_info = extract_stud_info(extracted_text, degree)
    print("Extracted student info:", stud_info)

    conn = create_connection()
    if conn is None:
        return jsonify({"error":"database connection failed"}), 500
    cursor = conn.cursor()

    for seat_no, name, result, degree in stud_info:
        try:

            cursor.execute("INSERT INTO mumbai_university_student_details(seat_no, name, reg_no, year, result, degree, filename, created_at)  VALUES(%s, %s, %s, %s, %s, %s, %s, %s)",
                (seat_no, name, '', year, result, degree, file.filename, created_at)
            )
            print(f"Inserted: {seat_no}, {name}, {year}, {result}, {degree}, {file.filename}, {created_at}")  # Log successful insert


        except Error as err:
            print(f"error inserting {seat_no}: {err}")
            conn.rollback()
            return jsonify({"error":str(err)})
    
    conn.commit()
    cursor.close()
    conn.close()
    
    #save student info to csv
    save_to_csv(stud_info, year, file.filename, created_at)

    return jsonify({"Message":"Data Inserted Successfully", "students":stud_info, "year":year}), 201

if __name__ == '__main__':
    app.run(host = "172.16.11.39", port = 5001, debug=True)


