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
    """Extract seat numbers, full names, and results from the extracted text."""
    student_info = []
    
    # Split the extracted text into lines
    lines = extracted_text.splitlines()

    for line in lines:
        stripped_line = line.strip()
        
        match = re.search(r'(\d{3})\s*\/?\s*([A-Za-z\s]+)\s+.*?\s+([PFA])', stripped_line)
        if match:
            seat_no = match.group(1)  # Seat number
            full_name = match.group(2).strip()  # Full name
            result = match.group(3).strip()  # Result (P or F)

            # Append to student_info if the name is valid
            if len(full_name.split()) >= 2 and all(keyword not in full_name for keyword in ["OFFICE", "REGISTER", "FOR", "THE", "NULL"]):
                student_info.append((seat_no, full_name, result, degree))

    return student_info


# Function to save data to CSV
def save_to_csv(student_info, year, filename, created_at):
    csv_file_path = f"/home/vboxuser/renuka/mumbai_univ/2019/Aug/{filename}_student_info.csv"
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
    pdf_path = f"/home/vboxuser/renuka/mumbai_univ/2019/Aug/{file.filename}"  
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
    app.run(host='172.16.11.39', port=5001, debug=True)


