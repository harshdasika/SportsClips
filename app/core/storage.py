import boto3
from botocore.config import Config

from ..config import settings


class S3Storage:
    def __init__(self):
        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY.get_secret_value(),
            aws_secret_access_key=settings.AWS_SECRET_KEY.get_secret_value(),
            region_name=settings.AWS_REGION,
            config=Config(signature_version="s3v4"),
        )
        self.bucket = settings.S3_BUCKET

    def upload_video(self, file_path: str, video_id: str) -> str:
        key = f"raw/{video_id}.mp4"
        try:
            self.s3.upload_file(file_path, self.bucket, key)
            return f"s3://{self.bucket}/{key}"
        except Exception as e:
            print(f"Upload failed: {e}")
            raise

    def download_video(self, video_id: str, destination: str):
        key = f"raw/{video_id}.mp4"
        try:
            self.s3.download_file(self.bucket, key, destination)
        except Exception as e:
            print(f"Download failed: {e}")
            raise

    def upload_highlights(self, file_path: str, video_id: str) -> str:
        key = f"highlights/{video_id}.mp4"
        try:
            self.s3.upload_file(file_path, self.bucket, key)
            return f"s3://{self.bucket}/{key}"
        except Exception as e:
            print(f"Highlights upload failed: {e}")
            raise

    def download_highlights(self, video_id: str, destination: str):
        key = f"highlights/{video_id}.mp4"
        try:
            self.s3.download_file(self.bucket, key, destination)
        except Exception as e:
            print(f"Highlights download failed: {e}")
            raise
