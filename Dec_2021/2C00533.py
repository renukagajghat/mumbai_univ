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
                writer.writerow(["Seat No", "Name", "Reg No", "Year", "Result", "Degree", "File Name", "Created At"])
            
            # Write each student's information into the CSV file
            for entry in student_info:
                writer.writerow([entry['Seat No'], entry['Name'], entry['Reg No'], year, entry['Result'], entry['Degree'], filename, created_at])
                
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


# Function to extract student info from the text including Reg No.
def extract_stud_info(extracted_text, degree):
    student_info = []
    student_line_regex = r"(\d{3,7})\s*\/?\s*([A-Za-z\s\/\-\.\'\,\&\(\)]+)"
    result_regex = r"\b(P|F)\b"
    REGN_regex = r"(\d{16})"  # Regex to capture Reg No.

    # Unwanted phrases to exclude or clean
    exclude_phrases = ["OFFICE REGISTER FOR THE"]
    clean_phrases = ["OFFICE REGISTER FOR THE"]

    lines = extracted_text.splitlines()
    relevant_lines = [line.strip() for line in lines if line.strip()]

    current_student = {}
    for i, line in enumerate(relevant_lines):
        # Skip lines containing unwanted phrases
        if any(phrase in line for phrase in exclude_phrases):
            continue

        # Match seat number and name
        student_match = re.search(student_line_regex, line)
        if student_match:
            seat_no = student_match.group(1).strip()
            full_name = student_match.group(2).strip().replace('/', ' ')

            # Exclude entries that may not be valid student names
            if (len(full_name.split()) >= 2 and 
                all(keyword not in full_name for keyword in ["OFFICE", "REGISTER", "FOR", "THE", "NULL"])):

                current_student = {
                    'Seat No': seat_no,
                    'Name': full_name,
                    'Degree': degree
                }

        # Clean the degree field only if it exists
        if 'Degree' in current_student:
            for phrase in clean_phrases:
                current_student['Degree'] = current_student['Degree'].replace(phrase, "").strip()

        # Match Reg No.
        REGN_match = re.search(REGN_regex, line)
        if REGN_match and current_student:
            reg_no = REGN_match.group(1)
            current_student['Reg No'] = reg_no

        # Match result
        result_match = re.search(result_regex, line)
        if result_match and current_student:
            result = result_match.group(1)
            current_student['Result'] = result
            # Append valid student info to the list
            student_info.append({
                'Seat No': current_student['Seat No'],
                'Name': current_student['Name'],
                'Result': current_student['Result'],
                'Degree': current_student['Degree'],
                'Reg No': current_student.get('Reg No', 'N/A')  # Add Reg No if available
            })
            current_student = {}

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
    print("Extracted Text:\n", extracted_text[:20000])
    year = re.search(r'\b(20\d{2})\b', extracted_text).group(0) if re.search(r'\b(20\d{2})\b', extracted_text) else None
    created_at = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")
    degree = extract_line_starting_with(extracted_text, 'OFFICE') or 'Unknown'
    
    stud_info = extract_stud_info(extracted_text, degree)
    
    if not stud_info:
        return jsonify({"error": "No student data extracted"}), 400

    conn = create_connection()
    if conn is None:
        return jsonify({"error": "Database connection failed"}), 500
    cursor = conn.cursor()

    for entry in stud_info:
        try:
            cursor.execute("INSERT INTO mumbai_university_student_details(seat_no, name, reg_no, year, result, degree, filename, created_at) VALUES(%s, %s, %s, %s, %s, %s, %s, %s)",
                (entry['Seat No'], entry['Name'], entry['Reg No'], year, entry['Result'], entry['Degree'], file.filename, created_at))
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
