# test_setup.py
from app.config import settings
from app.core.storage import S3Storage
from app.database import Base, engine


def test_setup():
    # Test database
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created")

    # Test S3
    storage = S3Storage()
    try:
        buckets = storage.s3.list_buckets()
        print("✓ S3 connection successful")
    except Exception as e:
        print(f"✗ S3 connection failed: {e}")


if __name__ == "__main__":
    test_setup()
