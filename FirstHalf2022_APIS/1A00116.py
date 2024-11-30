from flask import Flask, request, jsonify
from mysql.connector import connect, Error
from datetime import datetime
import pytz
from PIL import Image
import fitz  # PyMuPDF
import pytesseract
import re
import io
import os
import csv

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
            img = img.convert('L')
            img = img.point(lambda x: 0 if x < 128 else 255, '1')
            text = pytesseract.image_to_string(img, config='--psm 6')
            full_text += text

    return full_text

# Function to extract year from text
def extract_year(extracted_text):
    year_match = re.search(r'\b(20\d{2})\b', extracted_text)
    return year_match.group(0) if year_match else None

# Function to match starting word (OFFICE) from the extracted text
def extract_line_starting_with(extracted_text, start_word):
    lines = extracted_text.splitlines()
    for line in lines:
        if line.strip().startswith(start_word):
            return line.strip()
    return None

# Updated function to extract student info using regex

def extract_stud_info(extracted_text, degree):
    # Ensure the extracted text is a string
    if not isinstance(extracted_text, str):
        extracted_text = str(extracted_text)
    
    # Print out a snippet of the text to debug
    print("Extracted Text Snippet:")
    print(extracted_text[:1000])  # print first 1000 characters for inspection

    # Regex to capture seat number and name
    regex_name = r"(\d{4})\s*/?\s*([A-Za-z\s\.]+(?:[A-Za-z\s]+)*)"
    
    # Find all matches based on the regex
    matches = re.findall(regex_name, extracted_text)

    # Debugging: print the matches to check if they are correct
    print(f"Matches found: {len(matches)}")
    print("Matches:")
    for match in matches:
        print(match)

    # Extract information for valid students (with result if available)
    student_info = []
    for match in matches:
        seat_no = match[0].strip()
        full_name = match[1].strip().replace('/', '')  # Clean names
        name_p = full_name.replace("P", '')
        name = name_p.replace("F", '')

        # Default to 'N/A' if no result is found
        result = 'N/A'

        # Refined regex to capture the result, which might appear near 'GRAND TOTAL' or similar
        result_match = re.search(
            rf"{re.escape(seat_no)}.*?GRAND TOTAL:.*?(P|F|FAIL|ABSENT|EXMP)",
            extracted_text,
            re.IGNORECASE | re.DOTALL
        )
        
        # If a result match is found, capture it
        if result_match:
            result = result_match.group(1).strip().upper()
            if result in {"FAIL", "ABSENT"}:
                result = "F"  # Standardize 'FAIL' or 'ABSENT' to 'F'
            elif result == "EXMP":
                result = "P"  # Standardize 'EXMP' (example claimed) to 'P'

        # Ensure valid names (at least two parts to the name)
        if len(name.split()) >= 2 and all(keyword not in name.upper() for keyword in ["OFFICE", "REGISTER", "NULL"]) and seat_no not in ("5050", "8668"):
            student_info.append({
                'Seat No': seat_no,
                'Name': name,
                'Degree': degree,
                'Result': result
            })

    return student_info


# Function to save data to CSV
def save_to_csv(student_info, year, filename, created_at):
    csv_file_path = f"/home/vboxuser/renuka/mumbai_univ/FirstHalf2022/{filename}_student_info.csv"
    try:
        with open(csv_file_path, mode='a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            if os.stat(csv_file_path).st_size == 0:
                writer.writerow(["Seat No", "Name", "Year", "Result", "Degree", "File Name", "Created At"])
            for student in student_info:
                writer.writerow([student['Seat No'], student['Name'], year, student['Result'], student['Degree'], filename, created_at])
    except Exception as e:
        print(f"Error saving to CSV: {e}")

@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    pdf_path = f"/home/vboxuser/renuka/mumbai_univ/FirstHalf2022/{file.filename}"  
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
    if stud_info:
        conn = create_connection()
        if conn:
            cursor = conn.cursor()

            for student in stud_info:
                try:
                    cursor.execute(
                        "INSERT INTO mumbai_university_student_details(seat_no, name, reg_no, year, result, degree, filename, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (student['Seat No'], student['Name'], '', year, student['Result'], degree, file.filename, created_at)
                    )
                    print(f"Inserted: {student['Seat No']}, {student['Name']}, {year}, {student['Result']}, {file.filename}, {created_at}")
                except Error as err:
                    print(f"Error inserting {student['Seat No']}: {err}")
                    conn.rollback()
                    return jsonify({'error': str(err)}), 500

            conn.commit()
            cursor.close()
            conn.close()

            save_to_csv(stud_info, year, file.filename, created_at)

            return jsonify({
                "message": "Data inserted successfully",
                "students": [{"seat_no": student['Seat No'], "name": student['Name'], "result": student['Result'], "degree": student['Degree']} for student in stud_info],
                "year": year
            }), 201
        else:
            return jsonify({"error": "Database connection failed"}), 500
    else:
        return jsonify({"message": "No student data found!"})

if __name__ == '__main__':
    app.run(host = '172.16.11.39', port = 5001, debug=True)
