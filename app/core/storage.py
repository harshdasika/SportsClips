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

    # General-purpose file upload
    def upload_file(self, file_path: str, s3_key: str) -> str:
        try:
            self.s3.upload_file(file_path, self.bucket, s3_key)
            return f"s3://{self.bucket}/{s3_key}"
        except Exception as e:
            print(f"Upload failed for {file_path}: {e}")
            raise

    # General-purpose file download
    def download_file(self, s3_key: str, destination: str):
        try:
            self.s3.download_file(self.bucket, s3_key, destination)
        except Exception as e:
            print(f"Download failed for {s3_key}: {e}")
            raise

    # Raw video functions
    def upload_raw_video(self, file_path: str, video_id: str) -> str:
        key = f"raw/{video_id}.mp4"
        return self.upload_file(file_path, key)

    def download_raw_video(self, video_id: str, destination: str):
        key = f"raw/{video_id}.mp4"
        self.download_file(key, destination)

    # Split audio/video functions
    def upload_split_audio(self, file_path: str, video_id: str) -> str:
        key = f"split/{video_id}/split_audio.mp3"
        return self.upload_file(file_path, key)

    def download_split_audio(self, video_id: str, destination: str):
        key = f"split/{video_id}/split_audio.mp3"
        self.download_file(key, destination)

    # Highlights (final highlight reel) functions
    def upload_highlights(self, file_path: str, video_id: str) -> str:
        key = f"highlights/{video_id}.mp4"
        return self.upload_file(file_path, key)

    def download_highlights(self, video_id: str, destination: str):
        key = f"highlights/{video_id}.mp4"
        self.download_file(key, destination)

    # Metadata functions (e.g., JSON with timestamps/categories/probabilities)
    def upload_highlights_metadata(self, file_path: str, video_id: str) -> str:
        key = f"split/{video_id}/highlights.json"
        return self.upload_file(file_path, key)

    def download_highlights_metadata(self, video_id: str, destination: str):
        key = f"split/{video_id}/highlights.json"
        self.download_file(key, destination)
