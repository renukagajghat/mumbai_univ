from flask import Flask, request, jsonify
from mysql.connector import connect, Error
from datetime import datetime
import fitz  # PyMuPDF
import pytz
import re
import os
import csv

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
    csv_file_path = f"/home/vboxuser/renuka/mumbai_univ/2021/Dec/{filename}_student_info.csv"
    with open(csv_file_path, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        # Write header only if the file is new
        if os.stat(csv_file_path).st_size == 0:
            writer.writerow(["Seat No", "Name", "Reg No", "Year", "Result", "Degree", "File Name", "Created At"])
        for entry in student_info:
            writer.writerow([entry['Seat No'], entry['Name'], entry['Regn No'], year, entry['Result'], "Unknown", filename, created_at])



# Function to extract student info and complete text from the PDF
def extract_student_info(pdf_path):
    student_info = []
    regex = r"(\d{3})\s*\/?\s*([A-Z\s\.]+?)\s+(\d{2}[A-Z]\d{6})\s+.*?(\bF\b|\bP\b)"
    full_text = ""

    with fitz.open(pdf_path) as doc:
        for page_num, page in enumerate(doc):
            text = page.get_text("text")  # Extract text content from page
            full_text += text  # Append text to full_text
            lines = text.splitlines()  # Split text into lines

            for line in lines:
                line = re.sub(r'\s+', ' ', line.strip())  # Clean extra spaces
                regex_matches = re.finditer(regex, line)  # Use finditer to find all matches

                for regex_match in regex_matches:
                    seat_no = regex_match.group(1).strip()
                    full_name = regex_match.group(2).strip()
                    name = full_name.replace('/', '')
                    regn_no = regex_match.group(3).strip()
                    result = regex_match.group(4).strip()  # Extracting result (F or P)

                    # Append only if all values are captured
                    student_info.append({
                        'Seat No': seat_no,
                        'Name': name,
                        'Regn No': regn_no,
                        'Result': result,
                    })

    return student_info, full_text  # Return both student info and full text


@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    pdf_path = f"/home/vboxuser/renuka/mumbai_univ/2021/Dec/{file.filename}"  
    file.save(pdf_path)

    # Extract student info and full text from the PDF
    extracted_info, full_pdf_text = extract_student_info(pdf_path)

    # If no student info is found, return an appropriate message
    if not extracted_info:
        return jsonify({"message": "No student info found!"}), 404

    # Extract year from the full PDF text
    year = extract_year(full_pdf_text)

    # Extract degree after getting the full text
    start_word = "OFFICE"
    extracted_line = extract_line_starting_with(full_pdf_text, start_word)
    degree = extracted_line if extracted_line else "Unknown"

    created_at = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")

    # Database insertion
    conn = create_connection()
    if conn:
        cursor = conn.cursor()
        for entry in extracted_info:
            seat_no = entry['Seat No']
            name = entry['Name']
            reg_no = entry['Regn No']
            result = entry['Result']
            try:
                cursor.execute(
                    "INSERT INTO mumbai_university_student_details(seat_no, name, reg_no, year, result, degree, filename, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (seat_no, name, reg_no, year, result, degree, file.filename, created_at)
                )
            except Error as err:
                print(f"Error inserting {seat_no}: {err}")
                conn.rollback()
                return jsonify({'error': str(err)}), 500

        conn.commit()
        cursor.close()
        conn.close()

        # Save student info to CSV
        save_to_csv(extracted_info, year, file.filename, created_at)

        return jsonify({"message": "Student info inserted successfully", 'students': extracted_info, 'year': year}), 201
    else:
        return jsonify({"error": "Database connection failed"}), 500

if __name__ == '__main__':
    app.run(host='172.16.11.39', port=5001, debug=True)
