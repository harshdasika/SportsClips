import hashlib
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

from app.core.extractAudio import extract_audio, extract_video_without_audio
from app.core.storage import S3Storage
from app.database import SessionLocal
from app.models.video import Video
from app.schemas.video import VideoStatus
from utils import calculate_file_signature

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upload_video(file_path: str) -> str:
    """
    Upload raw video to S3, split audio/video in parallel, upload extracted files,
    and save paths to DB. Returns video ID.
    """
    s3 = S3Storage()
    db = SessionLocal()

    # Calculate file signature
    file_signature = calculate_file_signature(file_path)

    # Check for duplicates
    existing_video = (
        db.query(Video).filter(Video.file_signature == file_signature).first()
    )
    if existing_video:
        logger.info(f"Duplicate video detected. Existing video ID: {existing_video.id}")
        return existing_video.id

    # Generate video ID and paths
    video_id = str(uuid.uuid4())
    raw_video_name = os.path.basename(file_path)
    raw_video_local = f"local_storage/{raw_video_name}"
    split_audio_local = f"local_storage/{video_id}_split_audio.m4a"
    split_video_local = f"local_storage/{video_id}_split_video.mp4"

    # Ensure local_storage directory exists
    os.makedirs("local_storage", exist_ok=True)

    # Copy video to local_storage
    os.system(f"cp '{file_path}' '{raw_video_local}'")

    def upload_raw():
        """Upload raw video to S3."""
        logger.info("Uploading raw video to S3...")
        return s3.upload_raw_video(raw_video_local, video_id)

    def process_audio():
        """Extract audio and upload to S3."""
        logger.info("Extracting audio...")
        extract_audio(raw_video_local, split_audio_local)
        logger.info("Uploading audio to S3...")
        return s3.upload_split_audio(split_audio_local, video_id)

    def process_video():
        """Extract video without audio and upload to S3."""
        logger.info("Extracting video without audio...")
        extract_video_without_audio(raw_video_local, split_video_local)
        logger.info("Uploading video to S3...")
        return s3.upload_split_video(split_video_local, video_id)

    # Run tasks in parallel
    with ThreadPoolExecutor() as executor:
        futures = {
            "raw": executor.submit(upload_raw),
            "audio": executor.submit(process_audio),
            "video": executor.submit(process_video),
        }

        # Collect results
        results = {key: future.result() for key, future in futures.items()}

    # Save video entry to database
    try:
        video = Video(
            id=video_id,
            raw_url=results["raw"],
            status=VideoStatus.PENDING,
            file_signature=file_signature,
            highlights=[],
        )
        db.add(video)
        db.commit()

        logger.info(f"Upload complete for video ID: {video_id}")
        return video_id

    except Exception as e:
        logger.error(f"Error saving video to database: {e}")
        raise


def check_status(video_id: str) -> dict:
    """Check video processing status."""
    db = SessionLocal()
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise ValueError(f"Video {video_id} not found")

    return {
        "id": video.id,
        "status": video.status,
        "highlights_count": len(video.highlights) if video.highlights else 0,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Video Highlight Generator")
    parser.add_argument(
        "action", choices=["upload", "extract", "shortlist", "create", "status"]
    )
    parser.add_argument(
        "--id", help="Video ID for extraction, shortlisting, creation, or status check"
    )
    parser.add_argument(
        "--file", help="Path to video file for upload (required for 'upload')"
    )

    args = parser.parse_args()

    try:
        if args.action == "upload":
            if not args.file:
                raise ValueError("--file required for upload")
            video_id = upload_video(args.file)
            print(f"Uploaded video ID: {video_id}")

        elif args.action == "shortlist":
            if not args.id:
                raise ValueError("--id required for shortlisting highlights")
            print(f"Shortlisted highlights for video ID: {args.id}")

        elif args.action == "create":
            if not args.id:
                raise ValueError("--id required for highlight creation")
            print(f"Highlight reel created for video ID: {args.id}")

        elif args.action == "status":
            if not args.id:
                raise ValueError("--id required for status check")
            status = check_status(args.id)
            print(f"Status for video ID {args.id}: {status}")

    except Exception as e:
        logger.error(f"Error: {e}")
        exit(1)
