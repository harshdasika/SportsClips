import os
import json
import subprocess
from typing import List


def read_highlight_analysis(file_path: str) -> List[dict]:
    """
    Reads the highlight analysis JSON file and returns the sequences.

    Args:
        file_path (str): Path to the highlight_analysis.json file.

    Returns:
        List[dict]: A list of sequence dictionaries.
    """
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        return data.get("sequences", [])
    except FileNotFoundError:
        print(f"Error: JSON file not found at {file_path}")
        return []


def get_highlight_files(sequences: List[dict], highlights_dir: str) -> List[str]:
    """
    Filters the highlights based on highlight_probability and maps them to their files.

    Args:
        sequences (List[dict]): List of sequences from the JSON.
        highlights_dir (str): Path to the folder containing highlight video files.

    Returns:
        List[str]: A list of file paths for highlights with probability >= 0.5.
    """
    highlight_files = []
    for sequence in sequences:
        try:
            highlight_probability = float(sequence.get("highlight_probability", 0))
            highlight_num = sequence.get("highlight_num")
            if highlight_probability >= 0.5:
                file_name = f"highlight_{highlight_num}.mp4"
                file_path = os.path.join(highlights_dir, file_name)
                if os.path.exists(file_path):
                    highlight_files.append(file_path)
                else:
                    print(f"Warning: Highlight file {file_path} does not exist.")
        except (ValueError, TypeError) as e:
            print(f"Error processing sequence: {sequence}. Error: {e}")
    return highlight_files


def stitch_highlights(highlight_files: List[str], output_file: str) -> None:
    """
    Stitches together highlight videos into a single file.

    Args:
        highlight_files (List[str]): List of file paths to stitch together.
        output_file (str): Path to save the final highlight reel.
    """
    if not highlight_files:
        print("No highlight files to stitch.")
        return

    try:
        # Create a temporary file listing all input files for ffmpeg
        list_file = "highlights_list.txt"
        with open(list_file, "w") as f:
            for file in highlight_files:
                f.write(f"file '{file}'\n")

        # Run ffmpeg to concatenate the videos
        command = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            output_file
        ]
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Highlight reel created at {output_file}")

        # Clean up the temporary file
        os.remove(list_file)
    except Exception as e:
        print(f"Error stitching highlights: {e}")


if __name__ == "__main__":
    # File paths
    base_dir = os.path.abspath(os.path.dirname(__file__))  # Current script directory
    project_dir = os.path.join(base_dir, "../../")         # Project root directory

    json_file = os.path.join(project_dir, "app/data/json/highlight_analysis.json")
    highlights_dir = os.path.join(project_dir, "app/data/highlights/")
    reels_dir = os.path.join(project_dir, "app/data/reels/")
    
    os.makedirs(reels_dir, exist_ok=True)
    output_file = os.path.join(reels_dir, "highlightReel.mp4")

    # Read the highlight analysis JSON
    sequences = read_highlight_analysis(json_file)

    # Filter and map highlight files
    highlight_files = get_highlight_files(sequences, highlights_dir)

    # Stitch together the highlights
    stitch_highlights(highlight_files, output_file)
