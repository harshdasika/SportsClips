import os
import librosa
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
import ffmpeg


def extract_audio_as_mp3(video_file, output_file):
    """
    Extract audio directly as MP3 from a video file using ffmpeg.

    Args:
        video_file (str): Path to the input video file.
        output_file (str): Path to save the MP3 file.

    Returns:
        None
    """
    try:
        # Ensure the output directory exists
        output_dir = os.path.dirname(output_file)
        os.makedirs(output_dir, exist_ok=True)

        # Extract and convert directly to MP3
        ffmpeg.input(video_file).output(output_file, acodec='libmp3lame').run(overwrite_output=True)
        print(f"Audio extracted as MP3 to {output_file}")
    except ffmpeg.Error as e:
        print(f"Error extracting audio as MP3: {e}")


def analyze_audio(audio_file):
    """
    Analyze audio to detect high-energy peaks.

    Args:
        audio_file (str): Path to the MP3 audio file.

    Returns:
        list: Timestamps of detected peaks.
    """
    # Load the audio
    audio, sr = librosa.load(audio_file, sr=None)

    # Calculate RMS energy
    rms = librosa.feature.rms(y=audio).flatten()
    timestamps = librosa.frames_to_time(range(len(rms)), sr=sr)

    # Plot RMS to visualize peaks
    plt.plot(timestamps, rms)
    plt.title('Audio RMS Energy')
    plt.xlabel('Time (s)')
    plt.ylabel('RMS Energy')
    plt.show()

    # Detect peaks
    threshold = 0.02  # Adjust based on your audio
    peaks, _ = find_peaks(rms, height=threshold)
    highlight_timestamps = timestamps[peaks]

    print("Potential Highlight Timestamps:", highlight_timestamps)
    return highlight_timestamps


if __name__ == "__main__":
    # File paths
    video_file = "/Users/harshdasika/Desktop/celtics-knicks.mp4"
    mp3_file = "/Users/harshdasika/Desktop/extractedAudio.mp3"

    # Extract audio directly as MP3
    extract_audio_as_mp3(video_file, mp3_file)

    # Analyze audio
    highlight_timestamps = analyze_audio(mp3_file)
