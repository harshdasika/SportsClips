import os
import json
import subprocess
from typing import List, Dict
from moviepy.video.io.VideoFileClip import VideoFileClip


def read_highlight_metadata(file_path: str) -> List[Dict]:
    """
    Read the highlight metadata JSON file.

    Args:
        file_path (str): Path to the highlight_metadata.json file.

    Returns:
        List[Dict]: A list of dictionaries containing start_time and highlight_file.
    """
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"Error: Metadata file not found at {file_path}")
        return []


def get_video_duration_ffprobe(video_file: str) -> float:
    """
    Get the duration of a video file using ffprobe.

    Args:
        video_file (str): Path to the video file.

    Returns:
        float: Duration of the video in seconds.
    """
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", video_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        duration_str = result.stdout.strip()
        if duration_str:
            return float(duration_str)
        else:
            print(f"ffprobe returned empty duration for {video_file}")
            return 0.0
    except Exception as e:
        print(f"Error getting duration for {video_file} using ffprobe: {e}")
        return 0.0


def take_snapshots(video_file: str, output_dir: str, duration: float, clip_index: int) -> List[str]:
    """
    Take snapshots from a video file every 1 second.

    Args:
        video_file (str): Path to the video file.
        output_dir (str): Directory to save the snapshots.
        duration (float): Duration of the video in seconds.
        clip_index (int): Index of the highlight clip (for unique filenames).

    Returns:
        List[str]: List of snapshot filenames.
    """
    os.makedirs(output_dir, exist_ok=True)
    snapshots = []
    for second in range(int(duration)):
        output_file = os.path.join(output_dir, f"highlight_{clip_index}_{second + 1}s.jpg")
        command = [
            "ffmpeg",
            "-i", video_file,
            "-ss", str(second),
            "-vframes", "1",
            output_file,
        ]
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Saved snapshot: {output_file}")
        snapshots.append(os.path.basename(output_file))
    return snapshots


def save_image_metadata(metadata: List[Dict], output_file: str) -> None:
    """
    Save the image metadata to a JSON file.

    Args:
        metadata (List[Dict]): List of dictionaries containing image metadata.
        output_file (str): Path to save the JSON file.
    """
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(metadata, f, indent=4)
    print(f"Image metadata saved to {output_file}")


if __name__ == "__main__":
    # File paths
    base_dir = os.path.abspath(os.path.dirname(__file__))  # Directory of the current script
    project_dir = os.path.join(base_dir, "../../")          # Project root directory

    highlight_metadata_file = os.path.join(project_dir, "app/data/json/highlight_metadata.json")
    images_dir = os.path.join(project_dir, "app/data/images/")
    output_metadata_file = os.path.join(project_dir, "app/data/json/image_metadata.json")

    # Read highlight metadata
    highlight_metadata = read_highlight_metadata(highlight_metadata_file)
    if not highlight_metadata:
        print("No highlight metadata to process.")
        exit(1)

    image_metadata = []

    # Process each highlight clip
    for clip_index, entry in enumerate(highlight_metadata, 1):
        start_time = entry["start_time"]
        highlight_file = os.path.join(project_dir, "app/data/highlights/", entry["highlight_file"])

        # Get video duration
        duration = get_video_duration_ffprobe(highlight_file)
        if duration == 0:
            print(f"Skipping {highlight_file} due to error in fetching duration.")
            continue

        # Take snapshots
        snapshots = take_snapshots(highlight_file, images_dir, duration, clip_index)

        # Add to image metadata
        clip_metadata = {"start_time": start_time}
        for i, snapshot in enumerate(snapshots, 1):
            clip_metadata[f"image_{i}"] = snapshot
        image_metadata.append(clip_metadata)

    # Save image metadata to JSON
    save_image_metadata(image_metadata, output_metadata_file)