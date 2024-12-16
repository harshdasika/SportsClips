import os
import subprocess
from typing import List, Tuple

import ffmpeg
import librosa
import numpy as np


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

        Args:
            scores (np.ndarray): Excitement scores over time.
            sr (int): Sample rate of the audio.
            hop_length (int): Number of samples between successive frames.

        Returns:
            List[Tuple[float, float]]: List of start and end times of exciting moments.
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

    Args:
        video_file (str): Path to the video file.
        output_file (str): Path to save the extracted MP3 file.
    """
    try:
        output_dir = os.path.dirname(output_file)
        os.makedirs(output_dir, exist_ok=True)

        # Run ffmpeg to extract audio in MP3 format
        ffmpeg.input(video_file).output(output_file, acodec="libmp3lame").run(
            overwrite_output=True
        )
        print(f"Audio extracted as MP3 to {output_file}")
    except ffmpeg.Error as e:
        print(f"Error extracting audio as MP3: {e}")


def extract_highlight_clips(
    video_file: str, segments: List[Tuple[float, float]], output_dir: str
) -> None:
    """
    Extract highlight clips from a video based on provided timestamps.

    Args:
        video_file (str): Path to the video file.
        segments (List[Tuple[float, float]]): List of start and end times for highlights.
        output_dir (str): Directory to save the extracted clips.

    Adds a 2-second buffer before and after each segment.
    """
    os.makedirs(output_dir, exist_ok=True)

    for i, (start, end) in enumerate(segments, 1):
        # Add a 2-second buffer to the start and end times
        buffered_start = max(0, start - 2)  # Ensure start doesn't go below 0
        buffered_end = end + 2

        output_file = os.path.join(output_dir, f"highlight_{i}.mp4")
        command = [
            "ffmpeg",
            "-i",
            video_file,
            "-ss",
            str(buffered_start),
            "-to",
            str(buffered_end),
            "-c",
            "copy",
            output_file,
        ]
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Extracted clip: {output_file}")


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


if __name__ == "__main__":
    # File paths
    video_file = "/Users/harshdasika/Desktop/celtics-knicks.mp4"
    mp3_file = "/Users/harshdasika/Desktop/extractedAudio.mp3"
    highlights_dir = "/Users/harshdasika/Desktop/highlights"

    # Step 1: Extract audio as MP3
    extract_audio_as_mp3(video_file, mp3_file)

    # Step 2: Detect exciting moments
    detector = AudioExcitementDetector()
    exciting_moments = detector.detect_excitement(mp3_file)

    # Step 3: Merge close segments
    GAP_THRESHOLD = 4.0  # seconds
    merged_moments = merge_close_segments(exciting_moments, gap_threshold=GAP_THRESHOLD)

    # Step 4: Print merged timestamps
    print(f"Found {len(merged_moments)} merged exciting moments:")
    for start, end in merged_moments:
        print(f"Excitement from {start:.1f}s to {end:.1f}s")

    # Step 5: Extract highlight clips with buffer
    extract_highlight_clips(video_file, merged_moments, highlights_dir)
