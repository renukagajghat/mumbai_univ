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

# Set the path to the Tesseract OCR executable
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Set up Flask app
app = Flask(__name__)

# Set local timezone
local_tz = pytz.timezone('Asia/Kolkata')

# Set database connection
def create_connection():
    try:
        conn = connect(
            host="172.16.11.39",
            user="root",
            password="Sa@R3nuka1",
            database="educational_schema"
        )
        print("Database Connection Successful")
        return conn
    except Error as err:
        print(f"Error connecting to MySQL db: {err}")   
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
            img = img.convert('L')  # Convert grayscale
            img = img.point(lambda x: 0 if x < 128 else 255, '1')
            text = pytesseract.image_to_string(img, config='--psm 6')
            full_text += text
    return full_text

# Function to extract year from text
def extract_year(extracted_text):
    year_match = re.search(r'\b(20\d{2})\b', extracted_text)
    return year_match.group(0) if year_match else None

# Function to match starting word(OFFICE) from extracted_text
def extract_line_starting_with(extracted_text, start_word):
    lines = extracted_text.splitlines()
    for line in lines:
        if line.strip().startswith(start_word):
            return line.strip()
    return None    

# Function to clean up names
def clean_name(name):
    # Remove unwanted characters like slashes and extra spaces
    name = re.sub(r'[^A-Za-z\s]', '', name)  # Keep only alphabetic characters and spaces
    name = re.sub(r'\s+', ' ', name).strip()  # Replace multiple spaces with a single space
    
    # Stop at the first keyword indicating a college or unnecessary part
    stop_keywords = ["LA", "VES", "D", "CHEMBU", "KLE", "U", "ASH"]
    name_parts = name.split()
    filtered_name = []
    for part in name_parts:
        if part in stop_keywords:
            break
        filtered_name.append(part)
    return " ".join(filtered_name)

def extract_stud_info(extracted_text, degree):
    student_info = []
    extracted_text = extracted_text.replace("\xa0", " ").replace("\t", " ").strip()
    lines = extracted_text.splitlines()

    seat_no_pattern = re.compile(r"\b(\d{7})\b")  # Matches a 7-digit seat number
    name_pattern = re.compile(r"[A-Za-z\s/]+")    # Matches alphabetic names with spaces
    result_pattern = re.compile(r"(Successful|Unsuccessful)", re.IGNORECASE)

    result = None
    current_student = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check if the line contains result
        result_match = result_pattern.search(line)
        if result_match:
            result_text = result_match.group(1).capitalize()
            result = "F" if result_text == "Successful" else "P"

        # Extract seat number and name
        seat_no_match = seat_no_pattern.search(line)
        if seat_no_match:
            if current_student:
                current_student = (*current_student[:2], result, current_student[3])
                student_info.append(current_student)
                result = None

            seat_no = seat_no_match.group(1)
            cleaned_line = re.sub(seat_no_pattern, "", line)
            cleaned_line = result_pattern.sub("", cleaned_line).strip()
            name_match = name_pattern.search(cleaned_line)
            full_name = clean_name(name_match.group(0)) if name_match else " "
            first_four_words = " ".join(full_name.split()[:4])
            current_student = (int(seat_no), first_four_words, None, degree)

    if current_student:
        if seat_no not in ("2022", "2023", "5042"):
            current_student = (*current_student[:2], result, current_student[3])
            student_info.append(current_student)

    student_info.sort(key=lambda x: x[0])
    return student_info

            # # Append student info to the list
            # if seat_no not in ("2022", "2023", "5042"):
            #     student_info.append((
            #         int(seat_no),  # Convert seat number to an integer for sorting
            #         first_four_words,
            #         result,
            #         degree
            #     ))

    # Sort the student info by seat number (numerically)
    student_info.sort(key=lambda x: x[0])

    return student_info


# Function to save data to CSV
def save_to_csv(student_info, year, filename, created_at):
    csv_file_path = f"/home/vboxuser/renuka/mumbai_univ/FirstHalf2022/{filename}_student_info.csv"
    with open(csv_file_path, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        # Write header only if the file is new
        if os.stat(csv_file_path).st_size == 0:
            writer.writerow(["Seat No", "Name", "Year", "Result", "File Name", "Created At"])
        for seat_no, name, result, degree in student_info:
            writer.writerow([seat_no, name, year, result, degree, filename, created_at])  

@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Set pdf path
    pdf_path = f"/home/vboxuser/renuka/mumbai_univ/FirstHalf2022/{file.filename}"  
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
        return jsonify({"error": "Database connection failed"}), 500
    cursor = conn.cursor()

    for seat_no, name, result, degree in stud_info:
        try:
            cursor.execute("INSERT INTO mumbai_university_student_details(seat_no, name, reg_no, year, result, degree, filename, created_at)  VALUES(%s, %s, %s, %s, %s, %s, %s, %s)",
                (seat_no, name, '', year, result, degree, file.filename, created_at)
            )
            print(f"Inserted: {seat_no}, {name}, {year}, {result}, {degree}, {file.filename}, {created_at}")

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
    app.run(host = '172.16.11.39', port = 5001, debug=True)






