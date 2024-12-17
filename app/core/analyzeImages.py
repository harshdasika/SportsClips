import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


def read_highlight_metadata(file_path: str) -> List[Dict]:
    """
    Read the highlight metadata JSON file.
    """
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Error: Metadata file not found at {file_path}")
        return []


def get_video_duration_ffprobe(video_file: str) -> float:
    """
    Get the duration of a video file using ffprobe.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_file,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,  # Add timeout
        )
        duration_str = result.stdout.strip()
        return float(duration_str) if duration_str else 0.0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError) as e:
        logging.error(f"Error getting duration for {video_file}: {e}")
        return 0.0


def take_snapshots_efficient(
    video_file: str,
    output_dir: str,
    duration: float,
    clip_index: int,
    interval: float = 1.0,
) -> List[str]:
    """
    Take snapshots from a video file at specified intervals using a single FFmpeg process.

    Args:
        video_file: Path to the video file
        output_dir: Directory to save the snapshots
        duration: Duration of the video in seconds
        clip_index: Index of the highlight clip
        interval: Time interval between frames (default: 1.0 second)
    """
    os.makedirs(output_dir, exist_ok=True)
    output_pattern = os.path.join(output_dir, f"highlight_{clip_index}_%d.jpg")

    # Calculate frame rate based on interval
    fps = f"1/{interval}"

    command = [
        "ffmpeg",
        "-i",
        video_file,
        "-vf",
        f"fps={fps}",  # Set output frame rate
        "-frame_pts",
        "1",  # Add presentation timestamp
        "-vsync",
        "0",  # Prevent frame dropping
        "-q:v",
        "2",  # High quality (2-31, lower is better)
        output_pattern,
    ]

    try:
        # Run FFmpeg with timeout
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=max(30, duration * 2),  # Adaptive timeout based on duration
        )

        if process.returncode != 0:
            logging.error(f"FFmpeg error: {process.stderr.decode()}")
            return []

        # Get list of generated files
        snapshots = []
        frame_num = 1
        while True:
            filename = f"highlight_{clip_index}_{frame_num}.jpg"
            if not os.path.exists(os.path.join(output_dir, filename)):
                break
            snapshots.append(filename)
            frame_num += 1

        logging.info(f"Generated {len(snapshots)} snapshots for clip {clip_index}")
        return snapshots

    except subprocess.TimeoutExpired:
        logging.error(f"Timeout while processing {video_file}")
        return []
    except Exception as e:
        logging.error(f"Error processing {video_file}: {e}")
        return []


def extract_frames(highlight_metadata_file: str) -> bool:
    """
    Extract frames from highlight clips and generate corresponding metadata.
    """
    try:
        # Setup paths
        base_dir = Path(__file__).parent
        project_dir = base_dir.parent.parent
        images_dir = project_dir / "app/data/images"
        output_metadata_file = project_dir / "app/data/json/image_metadata.json"

        # Ensure directories exist
        images_dir.mkdir(parents=True, exist_ok=True)
        output_metadata_file.parent.mkdir(parents=True, exist_ok=True)

        # Read highlight metadata
        highlight_metadata = read_highlight_metadata(highlight_metadata_file)
        if not highlight_metadata:
            logging.warning("No highlight metadata to process.")
            return False

        image_metadata = {}

        # Process each highlight clip
        for clip_index, entry in enumerate(highlight_metadata, 1):
            start_time = entry["start_time"]
            highlight_file = (
                project_dir / "app/data/highlights" / entry["highlight_file"]
            )

            if not highlight_file.exists():
                logging.error(f"Highlight file not found: {highlight_file}")
                continue

            # Get video duration
            duration = get_video_duration_ffprobe(str(highlight_file))
            if duration == 0:
                logging.error(f"Invalid duration for {highlight_file}")
                continue

            # Take snapshots using efficient method
            snapshots = take_snapshots_efficient(
                str(highlight_file), str(images_dir), duration, clip_index
            )

            if snapshots:
                image_metadata[str(start_time)] = snapshots

        # Save metadata
        with output_metadata_file.open("w") as f:
            json.dump(image_metadata, f, indent=4)

        logging.info(f"Image metadata saved to {output_metadata_file}")
        return True

    except Exception as e:
        logging.error(f"Error in extract_frames: {e}")
        return False


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    extract_frames("path/to/your/highlight_metadata.json")
