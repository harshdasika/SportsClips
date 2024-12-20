import json
import logging
import os
import subprocess
from typing import List, Tuple

import ffmpeg
import librosa
import numpy as np

from app.core.analyzeImages import extract_frames
from app.core.storage import S3Storage


class AudioExcitementDetector:
    """
    Class to analyze audio and detect moments of excitement based on specific features.
    """

    def __init__(self):
        # Configurable parameters
        self.sample_rate = 22050  # Audio sample rate for loading
        self.hop_length = 512  # Number of samples between successive frames
        self.excitement_threshold = 0.5  # Minimum score to consider a moment exciting
        self.min_excitement_duration = (
            1.5  # Minimum duration (seconds) for a segment to qualify as exciting
        )

    def detect_excitement(self, audio_file: str) -> List[Tuple[float, float]]:
        """
        Detect exciting moments based on audio analysis.

        Args:
            audio_file (str): Path to the audio file.

        Returns:
            List[Tuple[float, float]]: List of start and end times of exciting moments.
        """
        # Load audio file and resample to target sample rate
        y, sr = librosa.load(audio_file, sr=self.sample_rate)

        # Compute the Mel spectrogram and convert it to dB scale
        mel_spec = librosa.feature.melspectrogram(
            y=y, sr=sr, hop_length=self.hop_length
        )
        mel_db = librosa.power_to_db(mel_spec, ref=np.max)

        # Calculate features indicating excitement:
        high_freq_energy = np.mean(
            mel_db[40:], axis=0
        )  # Energy in higher frequency bands
        contrast = librosa.feature.spectral_contrast(
            y=y, sr=sr, hop_length=self.hop_length
        )
        contrast_mean = np.mean(contrast, axis=0)  # Average spectral contrast
        rms = librosa.feature.rms(y=y, hop_length=self.hop_length)[
            0
        ]  # Root Mean Square (RMS) energy

        # Combine features into an excitement score (weighted average)
        excitement_score = (
            0.4 * self._normalize(high_freq_energy)
            + 0.3 * self._normalize(contrast_mean)
            + 0.3 * self._normalize(rms)
        )

        # Identify continuous excitement segments
        excited_segments = self._find_excitement_segments(
            excitement_score, sr, self.hop_length
        )

        return excited_segments

    def _normalize(self, array: np.ndarray) -> np.ndarray:
        """
        Normalize an array to the range [0, 1].

        Args:
            array (np.ndarray): Array to normalize.

        Returns:
            np.ndarray: Normalized array.
        """
        min_val = np.min(array)
        max_val = np.max(array)
        return (array - min_val) / (max_val - min_val)

    def _find_excitement_segments(
        self, scores: np.ndarray, sr: int, hop_length: int
    ) -> List[Tuple[float, float]]:
        """
        Find continuous segments of high excitement based on scores.
        """
        segments = []
        start_time = None

        # Convert frame indices to time in seconds
        times = librosa.times_like(scores, sr=sr, hop_length=hop_length)

        for time, score in zip(times, scores):
            if score > self.excitement_threshold:
                # Start a new excitement segment if not already in one
                if start_time is None:
                    start_time = time
            elif start_time is not None:
                # End the segment if it drops below the threshold
                if time - start_time >= self.min_excitement_duration:
                    segments.append((start_time, time))
                start_time = None

        # Handle ongoing segment at the end of the audio
        if start_time is not None:
            if times[-1] - start_time >= self.min_excitement_duration:
                segments.append((start_time, times[-1]))

        return segments


def extract_audio_as_mp3(video_file: str, output_file: str) -> None:
    """
    Extract audio directly as MP3 from a video file using ffmpeg.
    """
    try:
        output_dir = os.path.dirname(output_file)
        os.makedirs(output_dir, exist_ok=True)

        ffmpeg.input(video_file).output(output_file, acodec="libmp3lame").run(
            overwrite_output=True
        )
        print(f"Audio extracted as MP3 to {output_file}")
    except ffmpeg.Error as e:
        print(f"Error extracting audio as MP3: {e}")


def extract_highlight_clips(
    video_file: str, segments: List[Tuple[float, float]], output_dir: str
) -> List[dict]:
    """
    Extract highlight clips from a video based on provided timestamps with optimized FFmpeg settings.
    Adds a 2-second buffer before and after each segment while maintaining quality and performance.

    Args:
        video_file: Path to the input video file
        segments: List of (start_time, end_time) tuples in seconds
        output_dir: Directory to save extracted clips

    Returns:
        List[dict]: List of metadata with start times and clip filenames.
    """
    os.makedirs(output_dir, exist_ok=True)
    metadata = []

    for i, (start, end) in enumerate(segments, 1):
        # Add buffer while ensuring start doesn't go below 0
        buffered_start = max(0, start - 2)
        buffered_end = end + 2
        duration = buffered_end - buffered_start

        output_file = os.path.join(output_dir, f"highlight_{i}.mp4")

        # Two-pass approach for more reliable seeking
        # First, create an accurate cut with copied streams
        temp_file = os.path.join(output_dir, f"temp_{i}.ts")

        first_pass = [
            "ffmpeg",
            "-y",
            "-ss",
            str(buffered_start),
            "-i",
            video_file,
            "-t",
            str(duration),
            "-c",
            "copy",  # Copy streams without re-encoding
            "-avoid_negative_ts",
            "1",
            temp_file,
        ]

        # Second pass: re-encode the accurately cut segment
        second_pass = [
            "ffmpeg",
            "-y",
            "-i",
            temp_file,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "23",
            "-movflags",
            "+faststart",
            "-vsync",
            "1",
            "-af",
            "aresample=async=1:min_hard_comp=0.100000",  # Handle audio sync
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-ac",
            "2",
            output_file,
        ]

        try:
            # First pass - accurate cutting
            subprocess.run(
                first_pass, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
            )

            # Second pass - re-encoding
            subprocess.run(
                second_pass, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
            )

            # Clean up temporary file
            if os.path.exists(temp_file):
                os.remove(temp_file)

            print(f"Successfully extracted clip: {output_file}")

            metadata.append(
                {
                    "start_time": start,
                    "end_time": end,
                    "highlight_file": os.path.basename(output_file),
                }
            )

        except subprocess.CalledProcessError as e:
            print(f"Error extracting clip {i}:")
            print(f"Error message: {e.stderr.decode('utf-8')}")
            # Clean up temporary file if it exists
            if os.path.exists(temp_file):
                os.remove(temp_file)
            continue

    return metadata


def merge_close_segments(
    segments: List[Tuple[float, float]], gap_threshold: float
) -> List[Tuple[float, float]]:
    """
    Merge consecutive excitement segments if they occur within a specified gap threshold.

    Args:
        segments (List[Tuple[float, float]]): List of start and end times of excitement segments.
        gap_threshold (float): Maximum gap in seconds to merge segments.

    Returns:
        List[Tuple[float, float]]: Merged segments.
    """
    if not segments:
        return []

    merged_segments = [segments[0]]

    for start, end in segments[1:]:
        last_start, last_end = merged_segments[-1]

        if start - last_end <= gap_threshold:
            # Merge the current segment with the previous one
            merged_segments[-1] = (last_start, max(last_end, end))
        else:
            # Add a new segment
            merged_segments.append((start, end))

    return merged_segments


def save_metadata_to_json(metadata: List[dict], output_file: str) -> None:
    """
    Save metadata to a JSON file.

    Args:
        metadata (List[dict]): List of metadata dictionaries.
        output_file (str): Path to the JSON file.
    """
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(metadata, f, indent=4)
    print(f"Metadata saved to {output_file}")


def shortlist_highlights(video_id: str):
    """
    Process video to detect and extract highlight segments.

    Args:
        video_id (str): ID of the video to process

    Returns:
        None
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Starting highlight detection for video {video_id}")

    # Initialize S3 storage
    s3 = S3Storage()

    # Set up local paths
    base_dir = os.path.abspath(os.path.dirname(__file__))
    project_dir = os.path.join(base_dir, "../../")

    video_file = os.path.join(project_dir, f"app/data/games/{video_id}.mp4")
    mp3_file = os.path.join(project_dir, f"app/data/audios/{video_id}.mp3")
    highlights_dir = os.path.join(project_dir, "app/data/highlights/")
    metadata_file = os.path.join(project_dir, f"app/data/json/{video_id}_metadata.json")

    # Create directories if they don't exist
    os.makedirs(os.path.dirname(video_file), exist_ok=True)
    os.makedirs(os.path.dirname(mp3_file), exist_ok=True)
    os.makedirs(highlights_dir, exist_ok=True)
    os.makedirs(os.path.dirname(metadata_file), exist_ok=True)

    # Download video and audio from S3
    logger.info("Downloading video and audio files from S3")
    s3.download_raw_video(video_id, video_file)
    s3.download_split_audio(video_id, mp3_file)

    # Detect exciting moments
    logger.info("Detecting exciting moments in audio")
    detector = AudioExcitementDetector()
    exciting_moments = detector.detect_excitement(mp3_file)
    logger.info(f"Found {len(exciting_moments)} initial exciting moments")

    # Merge close segments
    logger.info("Merging close segments")
    merged_moments = merge_close_segments(exciting_moments, gap_threshold=4.0)
    logger.info(f"Merged into {len(merged_moments)} segments")

    # Print merged timestamps
    print(f"Found {len(merged_moments)} merged exciting moments:")
    for start, end in merged_moments:
        print(f"Excitement from {start:.1f}s to {end:.1f}s")

    # Extract highlight clips with buffer
    logger.info("Extracting highlight clips")
    highlight_metadata = extract_highlight_clips(
        video_file, merged_moments, highlights_dir
    )

    # Save metadata to JSON
    logger.info("Saving highlight metadata")
    save_metadata_to_json(highlight_metadata, metadata_file)

    extract_frames(metadata_file)

    # Clean up local files
    # logger.info("Cleaning up temporary files")
    # os.remove(video_file)
    # os.remove(mp3_file)


if __name__ == "__main__":
    # File paths
    base_dir = os.path.abspath(
        os.path.dirname(__file__)
    )  # Directory of the current script
    project_dir = os.path.join(base_dir, "../../")  # Project root directory

    # Define file paths relative to the project directory
    video_file = os.path.join(project_dir, "app/data/games/celtics-knicks.mp4")
    mp3_file = os.path.join(project_dir, "app/data/audios/extractedAudio.mp3")
    highlights_dir = os.path.join(project_dir, "app/data/highlights/")
    metadata_file = os.path.join(project_dir, "app/data/json/highlight_metadata.json")

    # Step 1: Extract audio as MP3
    extract_audio_as_mp3(video_file, mp3_file)

    # Step 2: Detect exciting moments
    detector = AudioExcitementDetector()
    exciting_moments = detector.detect_excitement(mp3_file)

    # Step 3: Merge close segments
    merged_moments = merge_close_segments(exciting_moments, gap_threshold=4.0)

    # Step 4: Print merged timestamps
    print(f"Found {len(merged_moments)} merged exciting moments:")
    for start, end in merged_moments:
        print(f"Excitement from {start:.1f}s to {end:.1f}s")

    # Step 5: Extract highlight clips with buffer
    highlight_metadata = extract_highlight_clips(
        video_file, merged_moments, highlights_dir
    )

    # Step 6: Save metadata to JSON
    save_metadata_to_json(highlight_metadata, metadata_file)
