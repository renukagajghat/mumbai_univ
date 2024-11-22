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

#function to extract year from text
def extract_year(extracted_text):
    year_match = re.search(r'\b(20\d{2}\b)', extracted_text)  
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
    """Extract student seat number, name, and final result from the text."""
    student_info = []
    
    # Split the extracted text into lines
    lines = extracted_text.splitlines()

    # Regular expression pattern
    pattern = r'^\s*(\d{4}(?:\/[A-Z]+)?)\s+([A-Z\s]+)\s+.+?\s+(\bP\b|\bF\b|\bAA\b|\bABS\b)\s*$'

    for line in lines:
        stripped_line = line.strip()

        # Check if the line contains potential student information
        if stripped_line:
            # Debugging: Print out the line for inspection
            # print("Processing Line:", stripped_line)

            # Use regex to match the pattern
            match = re.match(pattern, stripped_line)
            
            if match:
                seat_no = match.group(1).split('/')[0].strip() #get only the part before /
                suffix_name = match.group(1).split('/')[1] if '/' in match.group(1) else '' #get the suffix if it is exist
                full_name = match.group(2).strip()
                result = match.group(3).strip()

                #now, combine the suffix with the full name (without the leading /)
                if suffix_name:
                    full_name = f"{suffix_name} {full_name}"

                    # Append to student_info
                    student_info.append((seat_no, full_name, result, degree))
                else:
                    student_info.append((seat_no, full_name, result, degree))


    # Debugging: Print raw student info found
    print("Student Info Found:", student_info)
    
    return student_info
   

# Function to save data to CSV
def save_to_csv(student_info, year, filename, created_at):
    csv_file_path = f"/home/vboxuser/renuka/mumbai_univ/2018/Aug/{filename}_student_info.csv"
    os.makedirs(os.path.dirname(csv_file_path), exist_ok=True)

    try:
        with open(csv_file_path, mode='a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            if os.stat(csv_file_path).st_size == 0:
                writer.writerow(["Seat No", "Name", "Year", "Result", "Degree", "File Name", "Created At"]) 
            for seat_no, name, result, degree in student_info:  
                writer.writerow([seat_no, name, year, result, degree, filename, created_at]) 
    except Exception as e:
        print(f"Error saving to CSV: {e}")


@app.route('/upload', methods = ['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"error":"No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error":"No selected file"}), 400
    #set pdf path
    pdf_path = f"/home/vboxuser/renuka/mumbai_univ/2018/Aug/{file.filename}"
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


