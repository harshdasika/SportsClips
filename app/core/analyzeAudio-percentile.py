import os
import subprocess
from typing import List, Tuple

import ffmpeg
import librosa
import matplotlib.pyplot as plt
import numpy as np


class AudioExcitementDetector:
    def __init__(self, percentile_threshold: float = 99):
        self.sample_rate = 22050
        self.hop_length = 512
        self.percentile_threshold = percentile_threshold
        self.min_excitement_duration = 1.5

    def detect_excitement(
        self, audio_file: str, plot: bool = False
    ) -> List[Tuple[float, float]]:
        y, sr = librosa.load(audio_file, sr=self.sample_rate)

        mel_spec = librosa.feature.melspectrogram(
            y=y, sr=sr, hop_length=self.hop_length
        )
        mel_db = librosa.power_to_db(mel_spec, ref=np.max)

        high_freq_energy = np.mean(mel_db[40:], axis=0)
        contrast = librosa.feature.spectral_contrast(
            y=y, sr=sr, hop_length=self.hop_length
        )
        contrast_mean = np.mean(contrast, axis=0)
        rms = librosa.feature.rms(y=y, hop_length=self.hop_length)[0]

        excitement_score = (
            0.4 * self._normalize(high_freq_energy)
            + 0.3 * self._normalize(contrast_mean)
            + 0.3 * self._normalize(rms)
        )

        threshold = np.percentile(excitement_score, self.percentile_threshold)

        excited_segments = self._find_excitement_segments(
            excitement_score, sr, self.hop_length, threshold
        )

        if plot:
            self._plot_excitement(
                excitement_score, sr, self.hop_length, threshold, excited_segments
            )

        return excited_segments

    def _normalize(self, array: np.ndarray) -> np.ndarray:
        return (array - np.min(array)) / (np.max(array) - np.min(array))

    def _find_excitement_segments(
        self, scores: np.ndarray, sr: int, hop_length: int, threshold: float
    ) -> List[Tuple[float, float]]:
        segments = []
        start_time = None
        times = librosa.times_like(scores, sr=sr, hop_length=hop_length)

        for time, score in zip(times, scores):
            if score > threshold:
                if start_time is None:
                    start_time = time
            elif start_time is not None:
                if time - start_time >= self.min_excitement_duration:
                    segments.append((start_time, time))
                start_time = None

        if start_time is not None and (
            times[-1] - start_time >= self.min_excitement_duration
        ):
            segments.append((start_time, times[-1]))

        return segments

    def _plot_excitement(
        self,
        scores: np.ndarray,
        sr: int,
        hop_length: int,
        threshold: float,
        segments: List[Tuple[float, float]],
    ) -> None:
        times = librosa.times_like(scores, sr=sr, hop_length=hop_length)
        plt.figure(figsize=(12, 6))
        plt.plot(times, scores, label="Excitement Score")
        plt.axhline(
            y=threshold,
            color="r",
            linestyle="--",
            label=f"Threshold ({self.percentile_threshold}th Percentile)",
        )

        for start, end in segments:
            plt.axvspan(start, end, color="yellow", alpha=0.3, label="Exciting Segment")

        plt.title("Excitement Score Over Time")
        plt.xlabel("Time (s)")
        plt.ylabel("Score")
        plt.legend()
        plt.grid()
        plt.show()


# Supporting Functions
def extract_audio_as_mp3(video_file: str, output_file: str) -> None:
    try:
        output_dir = os.path.dirname(output_file)
        os.makedirs(output_dir, exist_ok=True)

        # Run ffmpeg to extract audio in MP3 format
        ffmpeg.input(video_file).output(output_file, acodec="libmp3lame").global_args(
            "-nostdin"
        ).run(overwrite_output=True)
        print(f"Audio extracted as MP3 to {output_file}")
    except ffmpeg.Error as e:
        print(f"Error extracting audio as MP3: {e}")


def extract_highlight_clips(
    video_file: str, segments: List[Tuple[float, float]], output_dir: str
) -> None:
    """Extract highlight clips from video."""
    os.makedirs(output_dir, exist_ok=True)
    for i, (start, end) in enumerate(segments, 1):
        buffered_start = max(0, start - 2)
        buffered_end = end + 2
        output_file = os.path.join(output_dir, f"highlight_{i}.mp4")
        subprocess.run(
            [
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
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"Extracted clip: {output_file}")


def merge_close_segments(
    segments: List[Tuple[float, float]], gap_threshold: float = 4.0
) -> List[Tuple[float, float]]:
    if not segments:
        return []

    merged_segments = [segments[0]]

    for start, end in segments[1:]:
        last_start, last_end = merged_segments[-1]

        if start - last_end <= gap_threshold:
            merged_segments[-1] = (last_start, max(last_end, end))
        else:
            merged_segments.append((start, end))

    return merged_segments


if __name__ == "__main__":
    video_file = "/Users/harshdasika/Desktop/celtics-knicks.mp4"
    mp3_file = "/Users/harshdasika/Desktop/extractedAudio.mp3"
    highlights_dir = "/Users/harshdasika/Desktop/highlights"

    # Step 1: Extract audio
    extract_audio_as_mp3(video_file, mp3_file)

    # Step 2: Detect exciting moments
    detector = AudioExcitementDetector(percentile_threshold=99)  # Adjusted threshold
    exciting_moments = detector.detect_excitement(mp3_file, plot=True)

    # Step 3: Merge close segments
    merged_moments = merge_close_segments(exciting_moments, gap_threshold=4.0)

    # Step 4: Print merged timestamps
    print(f"Found {len(merged_moments)} merged exciting moments:")
    for start, end in merged_moments:
        print(f"Excitement from {start:.1f}s to {end:.1f}s")

    # Step 5: Extract highlight clips
    extract_highlight_clips(video_file, merged_moments, highlights_dir)
