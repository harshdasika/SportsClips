# main.py
import logging
import uuid
from pathlib import Path

from app.core.storage import S3Storage

# from app.core.audio import AudioExcitementDetector
from app.database import SessionLocal
from app.models.video import Video
from app.schemas.video import VideoStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upload_video(file_path: str) -> str:
    """
    Upload video to S3 and create DB entry
    Returns video_id
    """
    s3 = S3Storage()
    db = SessionLocal()
    video_id = str(uuid.uuid4())

    try:
        logger.info(f"Uploading video {video_id}")
        s3_url = s3.upload_video(file_path, video_id)

        video = Video(id=video_id, raw_url=s3_url, status=VideoStatus.PENDING)
        db.add(video)
        db.commit()

        logger.info(f"Upload complete: {video_id}")
        return video_id

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise


# def process_video(video_id: str):
#     """
#     Process already uploaded video
#     """
#     s3 = S3Storage()
#     db = SessionLocal()
#     audio_detector = AudioExcitementDetector()

#     try:
#         # Get video from DB
#         video = db.query(Video).filter(Video.id == video_id).first()
#         if not video:
#             raise ValueError(f"Video {video_id} not found")

#         # Update status
#         video.status = VideoStatus.PROCESSING
#         db.commit()

#         # Download from S3 to temp file
#         temp_path = f"/tmp/{video_id}.mp4"
#         logger.info(f"Downloading video to {temp_path}")
#         s3.download_video(video_id, temp_path)

#         # Process audio
#         logger.info("Analyzing audio...")
#         exciting_moments = audio_detector.detect_excitement(temp_path)

#         # Update video with results
#         video.highlights = [
#             {"start_time": start, "end_time": end, "excitement_score": score}
#             for start, end, score in exciting_moments
#         ]
#         video.status = VideoStatus.COMPLETED
#         db.commit()

#         logger.info(f"Processing complete: found {len(exciting_moments)} highlights")

#     except Exception as e:
#         logger.error(f"Processing failed: {e}")
#         video.status = VideoStatus.FAILED
#         db.commit()
#         raise
#     finally:
#         # Cleanup
#         if Path(temp_path).exists():
#             Path(temp_path).unlink()


def check_status(video_id: str) -> dict:
    """
    Check video processing status
    """
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
    parser.add_argument("action", choices=["upload", "process", "status"])
    parser.add_argument("--file", help="Path to video file for upload")
    parser.add_argument("--video-id", help="Video ID for processing or status check")

    args = parser.parse_args()

    try:
        if args.action == "upload":
            if not args.file:
                raise ValueError("--file required for upload")
            video_id = upload_video(args.file)
            print(f"Uploaded video ID: {video_id}")

        # elif args.action == "process":
        #     if not args.video_id:
        #         raise ValueError("--video-id required for processing")
        #     process_video(args.video_id)
        #     print("Processing complete")

        elif args.action == "status":
            if not args.video_id:
                raise ValueError("--video-id required for status check")
            status = check_status(args.video_id)
            print(f"Status: {status}")

    except Exception as e:
        logger.error(f"Error: {e}")
        exit(1)
