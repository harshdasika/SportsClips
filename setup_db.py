# setup_db.py
import psycopg2
from sqlalchemy import inspect

from app.config import settings
from app.database import Base, engine
from app.models.video import Video  # Explicitly import all models


def create_database():
    # Parse connection details from DATABASE_URL
    parts = settings.DATABASE_URL.split("/")
    db_url = "/".join(parts[:-1])  # Everything except database name

    try:
        # Connect to default postgres database
        conn = psycopg2.connect(f"{db_url}/postgres")
        conn.autocommit = True
        cursor = conn.cursor()

        # Create database
        cursor.execute("CREATE DATABASE videos")
        print("✓ Created videos database")

    except psycopg2.Error as e:
        if "already exists" in str(e):
            print("✓ Videos database already exists")
        else:
            print(f"✗ Database creation failed: {e}")
    finally:
        cursor.close()
        conn.close()


def create_tables():
    try:
        # Use Inspector to check existing tables
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        print("Existing tables before creation:", existing_tables)

        # Create tables
        Base.metadata.create_all(bind=engine)
        print("✓ Created database tables")

        # Verify tables after creation
        existing_tables = inspector.get_table_names()
        print("Existing tables after creation:", existing_tables)
    except Exception as e:
        print(f"✗ Table creation failed: {e}")


if __name__ == "__main__":
    create_database()
    create_tables()
