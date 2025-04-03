from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime, date
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
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://guest:admin6171@10.132.4.44:5432/tpsdb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = True
app.secret_key = 'supersecretkey'

db = SQLAlchemy(app)

def fetch_patient_data(date_param=None):
    try:
        # Use today's date by default
        query_date = datetime.now().date()
        if date_param:
            try:
                query_date = datetime.strptime(date_param, '%Y-%m-%d').date()
            except ValueError:
                logger.error(f"Invalid date format: {date_param}")
                query_date = datetime.now().date()

        logger.info(f"Executing query for date: {query_date}")

        # Simplified query with only existing columns
        query_str = """
            SELECT 
                pat.last_name || ' ' || pat.first_name AS patient_name,
                pat.id AS mrn,
                CASE
                    WHEN tre.state IS NULL THEN 'Waiting'
                    WHEN tre.state = 2 THEN 'Treatment'
                    WHEN tre.state = 5 THEN 'Planning'
                    WHEN tre.state = 3 THEN 'MRI'
                    ELSE 'Other'
                END AS status,
                exa.diagnosis_name AS diagnosis,
                exa.date AS exam_date
            FROM patients pat
            JOIN examinations exa ON pat.uid = exa.parent_uid
            LEFT JOIN treatment_plans tre ON exa.uid = tre.root_uid
            WHERE exa.date = :query_date
            ORDER BY 
                pat.last_name,
                pat.first_name
            LIMIT 50
        """

        with db.engine.connect() as connection:
            result = connection.execute(text(query_str), {"query_date": query_date})
            patients = []
            
            for row in result:
                patient = {
                    "Patient_Name": row.patient_name,
                    "MRN": row.mrn,
                    "Status": row.status,
                    "Diagnosis": row.diagnosis if row.diagnosis else "N/A",
                    "Exam_Date": row.exam_date.isoformat(),
                    # These fields are not available in the database
                    "Start_Time": None,
                    "End_Time": None,
                    "Age": "N/A",
                    "Sex": "N/A",
                    "Plan": "N/A",
                    "Fixation": "N/A",
                    "Dose": "N/A",
                    "Targets": "N/A",
                    "Shots": "N/A",
                    "Gamma": "N/A"
                }
                patients.append(patient)

            logger.info(f"Fetched {len(patients)} patients for date {query_date}")
            return patients

    except Exception as e:
        logger.error(f"Error fetching patient data: {str(e)}", exc_info=True)
        return []

@app.route('/patients')
def get_patients():
    date_param = request.args.get('date')
    patients = fetch_patient_data(date_param)
    return jsonify(patients)

@app.route('/check-dates')
def check_dates():
    try:
        with db.engine.connect() as connection:
            # Get available examination dates
            exam_dates_query = text("""
                SELECT DISTINCT date 
                FROM examinations 
                ORDER BY date DESC 
                LIMIT 10
            """)
            exam_dates_result = connection.execute(exam_dates_query)
            exam_dates = [row.date for row in exam_dates_result]
            
            return jsonify({
                "available_exam_dates": [d.isoformat() for d in exam_dates],
                "current_date": datetime.now().date().isoformat()
            })
    except Exception as e:
        logger.error(f"Error checking dates: {e}")
        return jsonify({"error": str(e)})

@app.route('/')
def dashboard():
    return render_template('index.html')


@app.route('/debug-columns')
def debug_columns():
    try:
        with db.engine.connect() as connection:
            # Get columns for all relevant tables
            query = text("""
                SELECT 
                    table_name, 
                    column_name,
                    data_type
                FROM 
                    information_schema.columns
                WHERE 
                    table_name IN ('patients', 'examinations', 'treatment_plans')
                ORDER BY 
                    table_name, 
                    ordinal_position
            """)
            results = connection.execute(query)
            
            return jsonify({
                "columns": [
                    {"table": row.table_name, "column": row.column_name, "type": row.data_type}
                    for row in results
                ]
            })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/debug-tables')
def debug_tables():
    try:
        with db.engine.connect() as connection:
            # Get all tables and their columns that might contain time information
            query = text("""
                SELECT 
                    t.table_name, 
                    c.column_name,
                    c.data_type
                FROM 
                    information_schema.tables t
                JOIN 
                    information_schema.columns c 
                    ON t.table_name = c.table_name
                WHERE 
                    t.table_schema = 'public'
                    AND c.column_name LIKE '%time%'
                ORDER BY 
                    t.table_name, 
                    c.column_name
            """)
            results = connection.execute(query)
            
            return jsonify({
                "time_columns": [
                    {"table": row.table_name, "column": row.column_name, "type": row.data_type}
                    for row in results
                ]
            })
    except Exception as e:
        return jsonify({"error": str(e)})
    
@app.route('/debug-joins')
def debug_joins():
    try:
        with db.engine.connect() as connection:
            # Check examination-patient relationships
            exam_patient_query = text("""
                SELECT 
                    e.date,
                    COUNT(DISTINCT e.uid) as exam_count,
                    COUNT(DISTINCT p.uid) as patient_count,
                    COUNT(DISTINCT CASE WHEN p.uid IS NOT NULL THEN e.uid END) as matched_count
                FROM examinations e
                LEFT JOIN patients p ON e.parent_uid = p.uid
                GROUP BY e.date
                ORDER BY e.date DESC
                LIMIT 10
            """)
            
            join_stats = connection.execute(exam_patient_query).fetchall()
            
            # Check treatment plan relationships
            treatment_plan_query = text("""
                SELECT 
                    COUNT(*) as total_plans,
                    COUNT(DISTINCT root_uid) as distinct_exams,
                    COUNT(DISTINCT CASE WHEN root_uid IN (SELECT uid FROM examinations) THEN root_uid END) as matched_exams
                FROM treatment_plans
            """)
            
            plan_stats = connection.execute(treatment_plan_query).fetchone()
            
            return jsonify({
                "examination_patient_stats": [
                    {
                        "date": row.date.isoformat(),
                        "exam_count": row.exam_count,
                        "patient_count": row.patient_count,
                        "matched_count": row.matched_count
                    } for row in join_stats
                ],
                "treatment_plan_stats": {
                    "total_plans": plan_stats.total_plans,
                    "distinct_exams": plan_stats.distinct_exams,
                    "matched_exams": plan_stats.matched_exams
                }
            })
            
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    # Verify database connection
    try:
        with db.engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            logger.info("Database connection successful")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)