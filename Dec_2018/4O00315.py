from flask import Flask, request, jsonify
from mysql.connector import connect, Error
from datetime import datetime
from PIL import Image
import re
import os
import csv
import fitz
import pytz


#setup flask app
app = Flask(__name__)

#setup local timezone
local_tz = pytz.timezone('Asia/Kolkata')

#create mysql database connection

def create_connection():
    try:
        conn = connect(
        host = '172.16.11.39',
        user = 'root',
        password = 'Sa@R3nuka1',
        database = 'educational_schema'
        )
        print("Database connection successful...")
        return conn    
    except error as e:
        print(f"Error connecting to MySql DB:{e}")
        return None
    
#function to extract year
def extract_year(extracted_text):
    year_match = re.search(r'\b(20\d{2})\b', extracted_text)
    return year_match.group(0) if year_match else None

#function to match starting word (OFFICE) from extracted text
def extract_line_starting_with(extracted_text, start_word):
    lines = extracted_text.splitlines()
    for line in lines:
        if line.strip().startswith(start_word):
            return line.strip()  
    return None   

#function to save student_info to csv

def save_to_csv(student_info, year, filename, created_at):
    csv_file_path = f"/home/vboxuser/renuka/mumbai_univ/2018/Dec/{filename}_student_info.csv"
    with open(csv_file_path, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        #write header only if the file is new
        if os.stat(csv_file_path).st_size == 0:
            writer.writerow(["Seat No", "Name", "Regn No.", "Year", "Result", "Degree", "File Name", "Created At"])
        for entry in student_info:
            writer.writerow([entry['Seat No'], entry['Name'], entry['Regn No'], year, entry['Result'], 'Unknown', filename, created_at])    


#function to extract student info and full text  from the PDF
# function to extract student info and full text from the PDF
def extract_student_info(pdf_path):
    student_info = []
    # Adjust the regex to match the format of the data in your PDF
    regex = r"(\d{3})\s+([A-Z\s]+?)\s+(\d{2}[A-Z]\d{6})\s+.*?(\bF\b|\bP\b)"
    full_text = ""

    with fitz.open(pdf_path) as doc:
        for page_num, page in enumerate(doc):
            text = page.get_text("text")  # extract text content from the page
            full_text += text  # append text to full_text
            lines = text.splitlines()  # split text into lines

            for line in lines:
                line = re.sub(r'\s+', ' ', line.strip())  # clean extra spaces
                regex_match = re.search(regex, line)

                if regex_match:
                    seat_no = regex_match.group(1).strip()
                    full_name = regex_match.group(2).strip()
                    name = full_name.replace('/', '')
                    reg_no = regex_match.group(3).strip()
                    result = regex_match.group(4).strip()  # extracting result F or P

                    student_info.append(
                        {
                            'Seat No': seat_no,
                            'Name': name,
                            'Regn No': reg_no,
                            'Result': result,
                        }
                    )
    return student_info, full_text

# Ensure the full regex matches the actual spacing and structure in the PDF



@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"error":"No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error":"No Selected file"}), 400
    
    pdf_path = f"\\home\\vboxuser\\renuka\\mumbai_univ\\2018\\Dec\\{file.filename}"
    file.save(pdf_path)

    #extract full text and student info from the extracted text without degree
    extracted_text, full_pdf_text = extract_student_info(pdf_path)
    print({f"extracted text:{extracted_text}"})
    print({f"full pdf text:{full_pdf_text}"})


    #if no student found
    if not extracted_text:
        return jsonify({"message":"No student info found!"}), 404
    
    #extract year from the full pdf text
    year = extract_year(full_pdf_text)

    #extract degree after getting the full text
    start_word = 'OFFICE'
    extracted_line = extract_line_starting_with(full_pdf_text, start_word)

    degree = extracted_line if extracted_line else 'Unknown'
    print({f"extracted degree: {degree}"})

    created_at = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")

    #database insertion

    conn = create_connection()
    if conn:
        cursor = conn.cursor()
        for entry in extracted_text:
            seat_no = entry['Seat No']
            name = entry['Name']
            reg_no = entry['Regn No']
            result = entry['Result']
            try:
                cursor.execute(
                    "INSERT INTO mumbai_university_student_details(seat_no, name, reg_no, year, result, degree, filename, created_at) VALUES(%s, %s, %s, %s, %s, %s, %s, %s)",
                    (seat_no, name, reg_no, year, result, degree, file.filename, created_at)
                )
                print(f"Inserted: {seat_no}, {name}, {year}, {result}, {degree}, {file.filename}, {created_at}")
            except Error as err:
                print(f"error inserting {seat_no}: {err}")
                conn.rollback()
                return jsonify({'error':str(err)}), 500    
            
        conn.commit()
        cursor.close()
        conn.close()

        #save student info to csv
        save_to_csv(extracted_text, year, file.filename, created_at)

        return jsonify({"message":"student data inserted successfully", 'students':extracted_text, 'year':year}), 201
    else:
        return jsonify({"error":"Database Connection failed"}), 500

if __name__ == '__main__':
    app.run(debug=True, port = 5001, host='172.16.11.39')