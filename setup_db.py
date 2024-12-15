# setup_db.py
import psycopg2

from app.config import settings


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


if __name__ == "__main__":
    create_database()
