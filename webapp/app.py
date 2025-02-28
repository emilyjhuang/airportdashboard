from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import pandas as pd
import schedule
import time
import threading

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:password@localhost/hospital_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'supersecretkey'
db = SQLAlchemy(app)

def fetch_patient_data():
    query = text("""
        SELECT DISTINCT 
            pat.last_name AS "L_Name", pat.first_name AS "F_Name", pat.id AS "MRN", 
            pat.birth_date AS "DoB", 
            TO_CHAR(AGE(CURRENT_DATE, pat.birth_date),'YY') AS "Age",
            pat.examinations_count - 1 AS "#Pre",
            CASE pat.gender WHEN '1' THEN 'M' ELSE 'F' END AS "Sex",
            exa.date AS "ExamDate", exa.diagnosis_name AS "Diag",
            CASE WHEN tre.state IS NULL THEN '(Null)' 
                 WHEN tre.state = 2 THEN 'Going' 
                 WHEN tre.state = 5 THEN '!' 
                 ELSE 'Other' END AS "State",
            tre.name AS "Plan",
            tre.treatment_number AS "Tx#",
            CASE fra.frame_type WHEN '2' THEN 'Frame' WHEN '4' THEN 'Mask' ELSE 'Unknown' END AS "Fixation",
            tar.prescription_dose AS "D(Gy)", tar.prescription_isodose AS "D(%)",
            (SELECT COUNT(targets.root_uid) FROM targets WHERE exa.uid = targets.root_uid) AS "#Tar",
            (SELECT COUNT(shots.root_uid) FROM shots WHERE exa.uid = shots.root_uid AND tar.uid = sho.parent_uid) AS "#Shot",
            sho.gamma AS "G",
            exa.status AS "Status",
            tre.start_time AS "Start_Time",
            tre.end_time AS "End_Time",
            EXTRACT(EPOCH FROM (tre.end_time - tre.start_time)) / 60 AS "Time_Diff"
        FROM patients AS pat
        LEFT JOIN examinations AS exa ON pat.uid = exa.parent_uid
        LEFT JOIN treatment_plans AS tre ON exa.uid = tre.root_uid
        LEFT JOIN frames AS fra ON exa.uid = fra.parent_uid
        LEFT JOIN targets AS tar ON exa.uid = tar.root_uid AND tre.uid = tar.parent_uid
        LEFT JOIN shots AS sho ON exa.uid = sho.root_uid AND tar.uid = sho.parent_uid
        WHERE exa.date = CURRENT_DATE
        ORDER BY pat.last_name
    """)
    
    result = db.session.execute(query)
    patients = [dict(row) for row in result]
    return patients

@app.route('/patients')
def get_patients():
    patients = fetch_patient_data()
    return jsonify(patients)

def auto_update():
    schedule.every().day.at("00:00").do(fetch_patient_data)
    while True:
        schedule.run_pending()
        time.sleep(60)

threading.Thread(target=auto_update, daemon=True).start()

@app.route('/')
def dashboard():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
