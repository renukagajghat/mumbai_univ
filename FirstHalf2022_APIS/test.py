import re


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
        if len(name.split()) >= 2 and all(keyword not in name.upper() for keyword in ["OFFICE", "REGISTER", "NULL"]):
            student_info.append({
                'Seat No': seat_no,
                'Name': name,
                'Degree': degree,
                'Result': result
            })

    return student_info


# Example usage
extracted_text = """                                     UNIVERSITY OF MUMBAI                                                       AUGUST 12, 2022
          OFFICE REGISTER FOR THE B.Arch.(SEM.-VI) CBSGS EXAMINATION-APRIL 2022                               PAGE :    1
                                CENTRE :   1 MUMBAI
 --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  SEAT   NAME OF CANDIDATE                        <-IN-EX--COURSE 1----------->   <---IN---COURSE 2--------->   <--TH-IN-COURSE 3----------->   <---TH-IN-COURSE 4---------->
                                                  <-TH-IN--COURSE 5----------->   <-TH-IN--COURSE 6--------->   <--IN-EX-COURSE 7----------->   <------IN-COURSE 8---------->
                                                  <----IN--COURSE 9----------->
                      COLLEGE                     <---Marks--> Grade Gr. Cr. CG=<---Marks--> Grade Gr. Cr. CG=<---Marks--> Grade Gr. Cr. CG=<---Marks--> Grade Gr. Cr. CG=C*G  SEM-VI
                                                                    Pts. Pts.C*G TH  IN  TOT      Pts. Pts.C*G                  Pts. Pts.C*G
            SGPI   RSLT
 --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 Sub.:1. ARCH.DESIGN STUDIO-6 (IN:100/50,EXT:100/50)(Cr.:8)   Sub.:2. ALLIED DESGN STUD.-6 (IN:100/50)         (Cr.:3)       Sub.:3. ARCH.BLDG.CONST.-6   (TH:50/20,Int:50/25)(Cr.:4)
 Sub.:4. TH.&DES.OF STRU.-6   (Th:50/20, Int:50/25) (Cr.:3)   Sub.:5. ARCH.BLDG.SERVICE-4  (Th:50/20,Int:50/25)(Cr.:3)       Sub.:6. HUMANITIES - 6       (Th:50/20,Int:50/25)(Cr.:3)
 Sub.:7. ARCH.REPRE.&DETAIL-6 (IN:100/50,EXT:100/50)(Cr.:6)   Sub.:8. COLLEGE PROJECTS-6   (IN:100/50)         (Cr.:3)       Sub.:9. ELECTIVE - 6         (IN:100/50)         (Cr.:3)
 --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

     5001 /ADONI AISHWARYA ANIRUDDHA KIRTI        63  80  143  A   9   8  72       --  79   --    O  10 3  30      34  26   60  C  7  4   28        31  25  
56   D  6  3  18
                    100 KRVI ARCHT.-JUHU          36  26  62   C   7   3  21       26  32    58   D  6  3  18      51  58  109  E  5  6   30        -- 069  
--   B  8  3  24
                                                  -- 085  --   O   10  3  30                                                                        GRAND TOTAL:  721   7.53    P
                                                  SGPI :- SEM-I :  8.36  SEM-II:  6.72  SEM-III: 8.58  SEM-IV:  8.22  SEM-V :  8.25                 CGPI:   
7.94

     5002  AGAWANE ADITYA SUNIL SUNEETA           71  60  131  B   8   8  64       --  80   --    O  10 3  30      31  32   63  C  7  4   28        24  36  
60   C  7  3  21
                    100 KRVI ARCHT.-JUHU          34  34  68   B   8   3  24       33  30    63   C  7  3  21      67  72  139  B  8  6   48        -- 069  
--   B  8  3  24
                                                  -- 086  --   O   10  3  30                                                                        GRAND TOTAL:  759   8.06    P
                                                  SGPI :- SEM-I :  8.28  SEM-II:  8.06  SEM-III: 9.17  SEM-IV:  8.64  SEM-V :  8.78                 CGPI:   
8.50

     5003 /AGGARWAL NAINIKA ANUPAM SAVITA         73  80  153  O   10  8  80       --  68   --    B  8  3  24      23  40   63  C  7  4   28        35  37  
72   A  9  3  27
                    100 KRVI ARCHT.-JUHU          30  35  65   B   8   3  24       34  30    64   C  7  3  21      69  75  144  A  9  6   54        -- 060  
--   C  7  3  21
                                                  -- 082  --   O   10  3  30                                                                        GRAND TOTAL:  771   8.58    P
                                                  SGPI :- SEM-I :  8.72  SEM-II:  8.08  SEM-III: 8.39  SEM-IV:  7.92  SEM-V :  8.94                 CGPI:   
8.44

     5004  AGRAWAL AMIT VINODKUMAR NEHA           65  62  127  C   7   8  56       --  58   --    D  6  3  18      31  27   58  D  6  4   24        27  29  
56   D  6  3  18
                    213 SIR J.J. ARCHT.- CST      30  35  65   B   8   3  24       24  33    57   D  6  3  18      60  70  130  B  8  6   48        -- 065  
--   B  8  3  24
                                                  -- 070  --   A   9   3  27                                                                        GRAND TOTAL:  686   7.14    P
                                                  SGPI :- SEM-I :  6.94  SEM-II:  7.22  SEM-III: 8.00  SEM-IV:  7.36  SEM-V :  7.56                 CGPI:   
7.37

     5005 /AGRAWAL GAURI KAILASH JYOTI             9F AA  --   --    --  --        --  60E  --    C  7  3  21      25  14F  39  --  --  -- --       26E 37E 
63   C  7  3  21
                    110 L.S.RAHEJA ARCH-BAND      24  13F 37   -- -- --   --       25  18F   43   --  ----   --    25F AA  --   --    --  --        -- 050E 
--   E  5  3  15
                                                  -- 033F --   --  --  -- --                                                                        GRAND TOTAL:  359           F
                                                  SGPI :- SEM-I :  6.67  SEM-II:  8.08  SEM-III: 7.08  SEM-IV:  7.61  SEM-V :  6.83                 CGPI:  ---

     5006 /ANSARI ZAHRA ASLAM FIROZ               51  63  114  D   6   8  48       --  55   --    D  6  3  18      26  31   57  D  6  4   24        29  27  
56   D  6  3  18
                    398 RIZVI ARCHT. -BANDRA      20  25  45   P   4   3  12       25  25    50   E  5  3  15      58  62  120  C  7  6   42        -- 060  
--   C  7  3  21
                                                  -- 058  --   D   6   3  18                                                                        GRAND TOTAL:  615   6.00    P
                                                  SGPI :- SEM-I :  7.94  SEM-II:  8.75  SEM-III: 8.69  SEM-IV:  8.36  SEM-V :  7.39                 CGPI:   
7.86

     5007 /AWARE ADITI GIRISH SAYALI              61  78  139  B   8   8  64       --  61   --    C  7  3  21      26  34   60  C  7  4   28        34  32  
66   B  8  3  24
                   1067 VPPMP - SION              26  34  60   C   7   3  21       29  38    67   B  8  3  24      62  57  119  D  6  6   36        -- 060  
--   C  7  3  21
                                                  -- 068  --   B   8   3  24                                                                        GRAND TOTAL:  700   7.31    P
                                                  SGPI :- SEM-I :  8.89  SEM-II:  8.33  SEM-III: 9.28  SEM-IV:  8.00  SEM-V :  7.14                 CGPI:   
8.16

     5008  AWASTHI CHIRAG ARUN ABHA               82  62  144  A   9   8  72       --  59   --    D  6  3  18      32  36   68  B  8  4   32        28  37  
65   B  8  3  24
                    110 L.S.RAHEJA ARCH-BAND      22  30  52   E   5   3  15       29  38    67   B  8  3  24      75  65  140  A  9  6   54        -- 085  
--   O  10 3  30
                                                  -- 065  --   B   8   3  24                                                                        GRAND TOTAL:  745   8.14    P
                                                  SGPI :- SEM-I :  7.50  SEM-II:  8.25  SEM-III: 8.94  SEM-IV:  9.44  SEM-V :  8.86                 CGPI:   
8.52
 --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 @:O.5042A; @:O.5043A; *:O.5045A; #:0.229; +:EXMP.CARRIED;/:FEMALE; AA:ABSENT; P:PASSES; F:FAIL;E:EXMP CAN BE CLAIMED; RR:RESERVED; ~:Dyslexia ; AA/ABS: ABSENT; NULL:NULL & VOID.;
 GPA:GRADE POINT AVERAGE=SUM OF CxG / SUM OF C; GRADE F:BELOW 50%; GRADE E:50% & ABOVE AND BELOW 55%; GRADE D:55% AND ABOVE AND BELOW 60%; GRADE C:60% & ABOVE AND BELOW 65%;
 GRADE B:65% & ABOVE AND BELOW 69%; GRADE A:70% & ABOVE AND BELOW 75%; GRADE O:75% & ABOVE; GRADE F:GRADE POINTS BELOW 5; GRADE E:GRADE POINTS 5 TO 5.99; GRADE D:GRADE POINTS 6 TO 6.99;
 GRADE C:GRADE POINTS 7 TO 7.99; GRADE B:GRADE POINTS 8 TO 8.99; GRADE A:GRADE POINTS 9 TO 9.99; GRADE O:GRADE POINTS 10; ADC:ADMISSION CANCELLED; RPV:PROVISIONAL; RCC:O.5050.
 C:CREDIT POINTS; G:GRADE POINTS; Int. Marks are provisional and subject to change as and when the learner passes the external (Th.) Exam. as per Ordinance 
R.8668.
 Course Grades:-Grade-O(Outstanding)= 10pt.,Grade-A(Excellent)= 9pt.,Grade-B(Very Good)= 8pt.,Grade-C(Good)= 7pt.,Grade-D(Fair)= 6pt.,Grade-E(Satisfactory)= 5pt., Grade-F(Fail)= 0pt.
 --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


                                   UNIVERSITY OF MUMBAI                                                       AUGUST 12, 2022
          OFFICE REGISTER FOR THE B.Arch.(SEM.-VI) CBSGS EXAMINATION-APRIL 2022                               PAGE :    2
                                CENTRE :   1 MUMBAI
 --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  SEAT   NAME OF CANDIDATE                        <-IN-EX--COURSE 1----------->   <---IN---COURSE 2--------->   <--TH-IN-COURSE 3----------->   <---TH-IN-COURSE 4---------->
                                                  <-TH-IN--COURSE 5----------->   <-TH-IN--COU-------------------------------------------------------------------------------------------------------------------------------------------
"""

# Extract student info
student_info = extract_stud_info(extracted_text, degree='B.Arch.')

# Print student information to the console
for student in student_info:
    print(student)
