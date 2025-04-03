from sqlalchemy import create_engine

def test_sqlalchemy_connection():
    try:
        engine = create_engine('postgresql://guest:admin6171@10.132.4.44:5432/tpsdb')
        connection = engine.connect()
        print("SQLAlchemy Connection successful!")
        connection.close()
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure the database URI is correct.")

test_sqlalchemy_connection()
