from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime
import logging
from flask_cors import CORS

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

def fetch_detailed_patient_data(date_param=None):
    """
    Execute a detailed SQL query and map its results to dictionaries,
    including fields such as Age, Sex, Fixation, and Plan.
    The date_param should be in YYYY-MM-DD format; if not provided,
    it uses the current date.
    """
    try:
        # Use today's date by default, and convert date_param if provided
        if date_param:
            try:
                query_date = datetime.strptime(date_param, '%Y-%m-%d').date()
            except ValueError:
                logger.error(f"Invalid date format: {date_param}")
                query_date = datetime.now().date()
        else:
            query_date = datetime.now().date()

        logger.info(f"Executing detailed query for date: {query_date}")

        sql_query = """
            SELECT DISTINCT
                pat.last_name AS "L_Name",
                pat.first_name AS "F_Name",
                pat.id AS "MRN",
                pat.birth_date AS "DoB",
                To_char(age(CURRENT_DATE, pat.birth_date),'YY') AS "Age",
                pat.examinations_count - 1 AS "#Pre",
                CASE pat.gender WHEN '1' THEN 'M' ELSE 'F' END AS "Sex",
                exa.date AS "ExamDate",
                exa.diagnosis_name AS "Diagnosis",
                CASE
                    WHEN tre.state IS NULL THEN 'Waiting'
                    WHEN tre.state = 2 THEN 'Treatment'
                    WHEN tre.state = 5 THEN 'Planning'
                    WHEN tre.state = 3 THEN 'MRI'
                    ELSE 'Other'
                END AS "State",
                tre.name AS "Plan",
                tre.treatment_number as "Tx#",
                CASE fra.frame_type 
                    WHEN '2' THEN 'Frame' 
                    WHEN '4' THEN 'Mask' 
                    ELSE 'unknow' 
                END AS "Fixition",
                ( SELECT count(targets.root_uid) 
                  FROM targets 
                  WHERE exa.uid = targets.root_uid) AS "#Tar",
                ( SELECT count(shots.root_uid) 
                  FROM shots 
                  WHERE shots.root_uid = exa.uid AND tar.uid = sho.parent_uid) AS "#sho",
                sho.gamma AS "G",
                ( SELECT count(shots.root_uid) 
                  FROM shots 
                  WHERE (shots.c_sector_1 = 4 OR shots.c_sector_2 = 4 OR shots.c_sector_3 = 4 OR 
                         shots.c_sector_4 = 4 OR shots.c_sector_5 = 4 OR shots.c_sector_6 = 4 OR 
                         shots.c_sector_7 = 4 OR shots.c_sector_8 = 4) 
                    AND shots.root_uid = exa.uid) AS "#4mm", 
                ( SELECT count(shots.root_uid) 
                  FROM shots 
                  WHERE (shots.c_sector_1 = 8 OR shots.c_sector_2 = 8 OR shots.c_sector_3 = 8 OR 
                         shots.c_sector_4 = 8 OR shots.c_sector_5 = 8 OR shots.c_sector_6 = 8 OR 
                         shots.c_sector_7 = 8 OR shots.c_sector_8 = 8) 
                    AND shots.root_uid = exa.uid) AS "#8mm", 
                ( SELECT count(shots.root_uid) 
                  FROM shots 
                  WHERE (shots.c_sector_1 = 16 OR shots.c_sector_2 = 16 OR shots.c_sector_3 = 16 OR 
                         shots.c_sector_4 = 16 OR shots.c_sector_5 = 16 OR shots.c_sector_6 = 16 OR 
                         shots.c_sector_7 = 16 OR shots.c_sector_8 = 16) 
                    AND shots.root_uid = exa.uid) AS "#16mm", 
                ( SELECT round(sum(shots.shot_time)::NUMERIC,0) 
                  FROM shots 
                  WHERE shots.root_uid = exa.uid) AS "T(min)",
                exa.operator_name,
                exa.comment
            FROM patients as pat
                LEFT JOIN examinations AS exa ON pat.uid = exa.parent_uid
                LEFT JOIN volumes AS vol ON exa.uid = vol.root_uid
                LEFT JOIN treatment_plans AS tre ON exa.uid = tre.root_uid
                LEFT JOIN frames AS fra on exa.uid = fra.parent_uid
                LEFT JOIN targets AS tar ON exa.uid = tar.root_uid AND tre.uid = tar.parent_uid
                LEFT JOIN target_dose_optimization_settings as dos ON exa.uid = dos.root_uid
                LEFT JOIN latest_dose_optimization_settings AS lat ON exa.uid = lat.root_uid
                LEFT JOIN risk_volume_dose_optimization_settings AS ris ON exa.uid = ris.root_uid
                LEFT JOIN shots AS sho ON exa.uid = sho.root_uid AND tar.uid = sho.parent_uid
                LEFT JOIN segmented_skulls AS seg ON exa.uid = seg.ROOT_UID
            WHERE exa.date = :query_date
            GROUP BY 
                pat.last_name, pat.first_name, pat.id, pat.birth_date, pat.examinations_count, pat.gender,
                exa.date, exa.diagnosis_name, exa.uid,
                tre.state, tre.name, tre.export_id, tre.treatment_number,
                tar.uid, tar.name, tar.prescription_dose, tar.prescription_isodose,
                sho.parent_uid, sho.gamma, sho.x, sho.shot_time,
                fra.frame_type,
                tar.name, tar.prescription_dose, tar.prescription_isodose,
                sho.gamma
            ORDER BY pat.last_name
        """

        with db.engine.connect() as connection:
            result = connection.execute(text(sql_query), {"query_date": query_date})
            patients = []
            for row in result:
                mapping = row._mapping  # Use the _mapping attribute to access keys safely
                patient = {
                    "Patient_Name": f"{mapping['L_Name']}, {mapping['F_Name']}",
                    "MRN": mapping["MRN"],
                    "DoB": mapping["DoB"].isoformat() if mapping["DoB"] else "N/A",
                    "Age": mapping["Age"],
                    "Sex": mapping["Sex"],
                    # Use the "State" column as the patient's status
                    "Status": mapping["State"],
                    "Diagnosis": mapping["Diagnosis"] if mapping["Diagnosis"] else "N/A",
                    "Exam_Date": mapping["ExamDate"].isoformat() if mapping["ExamDate"] else "N/A",
                    "Plan": mapping["Plan"] if mapping["Plan"] else "N/A",
                    "Fixation": mapping["Fixition"] if mapping["Fixition"] else "N/A",
                    # For columns with special characters, use get() on the _mapping object
                    "Targets": mapping.get("#Tar", "N/A"),
                    "Shots": mapping.get("#sho", "N/A"),
                    "Gamma": mapping["G"] if mapping["G"] is not None else "N/A",
                    # Placeholders for values not available directly from the query
                    "Start_Time": None,
                    "End_Time": None,
                    "Dose": "N/A"
                }
                patients.append(patient)

            logger.info(f"Fetched {len(patients)} patients for date {query_date}")
            return patients

    except Exception as e:
        logger.error("Error fetching detailed patient data: " + str(e), exc_info=True)
        return []



@app.route('/patients')
def get_patients():
    date_param = request.args.get('date')
    # Use the detailed fetch function here
    patients = fetch_detailed_patient_data(date_param)
    return jsonify(patients)


@app.route('/check-dates')
def check_dates():
    try:
        with db.engine.connect() as connection:
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


@app.route('/update-patient-status', methods=['POST'])
def update_patient_status():
    try:
        data = request.json
        # Convert the patient MRN to a string (if it isn't already)
        patient_id = str(data.get('mrn'))
        new_status = data.get('status')
        
        # Map status text to numeric values according to your schema
        status_map = {
            'Waiting': None,
            'Treatment': 2,
            'Planning': 5,
            'MRI': 3,
            'Other': 0
        }
        
        if new_status not in status_map:
            return jsonify({"success": False, "message": "Invalid status"}), 400
            
        db_status = status_map[new_status]
        
        # Use an explicit cast in the WHERE clause to force pat.id to text.
        find_query = text("""
            SELECT tre.uid
            FROM patients pat
            JOIN examinations exa ON pat.uid = exa.parent_uid
            JOIN treatment_plans tre ON exa.uid = tre.root_uid
            WHERE cast(pat.id as varchar) = :mrn
            LIMIT 1
        """)
        
        update_query = text("""
            UPDATE treatment_plans
            SET state = :state
            WHERE uid = :uid
        """)
        
        # Use a transaction block so that the update is automatically committed.
        with db.engine.begin() as connection:
            result = connection.execute(find_query, {"mrn": patient_id}).fetchone()
            if result:
                treatment_uid = result[0]
                connection.execute(update_query, {"state": db_status, "uid": treatment_uid})
            else:
                return jsonify({"success": False, "message": "Patient or treatment plan not found"}), 404
                
        return jsonify({"success": True, "message": f"Patient status updated to {new_status}"})
                
    except Exception as e:
        logger.error(f"Error updating patient status: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/debug-tables')
def debug_tables():
    try:
        with db.engine.connect() as connection:
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
    

def grant_update_privileges():
    try:
        # Use a transaction block to execute the GRANT command.
        with db.engine.begin() as connection:
            connection.execute(text("GRANT UPDATE ON TABLE treatment_plans TO guest"))
        logger.info("Update privileges granted on treatment_plans to guest")
    except Exception as e:
        logger.error("Error granting update privileges: " + str(e), exc_info=True)

if __name__ == '__main__':
    # Optionally, call the function once on startup if your user has the privileges
    grant_update_privileges()
    try:
        with db.engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            logger.info("Database connection successful")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
    
    app.run(host='0.0.0.0', port=5000, debug=True)

