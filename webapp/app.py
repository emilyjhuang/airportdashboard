from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime
import schedule
import time
import threading
from flask_cors import CORS
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Database connection configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://guest:elekta@10.132.4.44:5432/tpsdb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = True
app.secret_key = 'supersecretkey'

db = SQLAlchemy(app)

def fetch_patient_data():
    try:
        # Use current date dynamically
        current_date = datetime.now().date()
        
        query = text("""
            SELECT DISTINCT
                pat.last_name || ' ' || pat.first_name AS "Patient_Name",
                pat.id AS "MRN",
                CASE
                    WHEN tre.state IS NULL THEN 'Waiting'
                    WHEN tre.state = 2 THEN 'Treatment'
                    WHEN tre.state = 5 THEN 'Planning'
                    WHEN tre.state = 3 THEN 'MRI'
                    ELSE 'Other'
                END AS "Status",
                tre.start_time AS "Start_Time",
                tre.end_time AS "End_Time",
                exa.diagnosis_name AS "Diagnosis",
                pat.age AS "Age",
                pat.sex AS "Sex",
                tre.plan_name AS "Plan",
                tre.fixation_type AS "Fixation",
                tre.prescribed_dose AS "Dose",
                tre.target_count AS "Targets",
                tre.shot_count AS "Shots",
                tre.gamma_index AS "Gamma"
            FROM patients AS pat
            LEFT JOIN examinations AS exa ON pat.uid = exa.parent_uid
            LEFT JOIN treatment_plans AS tre ON exa.uid = tre.root_uid
            WHERE exa.date = CURRENT_DATE
            ORDER BY tre.start_time NULLS LAST, pat.last_name, pat.first_name
        """)
        
        with db.engine.connect() as connection:
            result = connection.execute(query)
            patients = [dict(row) for row in result]
            
            # Convert datetime objects to strings for JSON serialization
            for patient in patients:
                if patient["Start_Time"]:
                    patient["Start_Time"] = patient["Start_Time"].isoformat()
                if patient["End_Time"]:
                    patient["End_Time"] = patient["End_Time"].isoformat()
        
        logger.info(f"Fetched {len(patients)} patients for {current_date}")
        return patients
    except Exception as e:
        logger.error(f"Error fetching patient data: {e}")
        return []

@app.route('/patients')
def get_patients():
    patients = fetch_patient_data()
    return jsonify(patients)

@app.route('/')
def dashboard():
    return render_template('index.html')

def auto_update():
    # Fetch data periodically
    schedule.every(15).minutes.do(fetch_patient_data)
    while True:
        schedule.run_pending()
        time.sleep(60)

@app.route('/test-connection')
def test_connection():
    connection_status = {
        "database_connection": False,
        "tables_accessible": False,
        "sample_data": None,
        "error": None
    }
    
    try:
        # Test basic connection
        with db.engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            connection_status["database_connection"] = True
            
            # Check if we can access the tables
            tables_query = text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                LIMIT 5
            """)
            tables_result = connection.execute(tables_query)
            tables = [row[0] for row in tables_result]
            connection_status["tables_accessible"] = True
            connection_status["available_tables"] = tables
            
            # Try to get one patient without date restriction
            sample_query = text("""
                SELECT 
                    pat.last_name || ' ' || pat.first_name AS patient_name,
                    pat.id AS mrn,
                    exa.date AS exam_date
                FROM patients AS pat
                LEFT JOIN examinations AS exa ON pat.uid = exa.parent_uid
                LIMIT 1
            """)
            
            sample_result = connection.execute(sample_query)
            sample_data = [dict(row) for row in sample_result]
            
            if sample_data:
                connection_status["sample_data"] = sample_data
                
                # Try with date restriction to see if today has records
                today_query = text("""
                    SELECT COUNT(*) 
                    FROM examinations 
                    WHERE date = CURRENT_DATE
                """)
                today_result = connection.execute(today_query)
                today_count = today_result.scalar()
                
                connection_status["today_records_count"] = today_count
                connection_status["current_date"] = datetime.now().date().isoformat()
            
    except Exception as e:
        connection_status["error"] = str(e)
    
    return jsonify(connection_status)

if __name__ == '__main__':
    # Verify database connection
    try:
        with db.engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            logger.info("Database connection successful")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
    
    # Start the background thread for auto-update
    threading.Thread(target=auto_update, daemon=True).start()
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)