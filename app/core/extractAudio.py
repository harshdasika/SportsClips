import ffmpeg

def extract_audio(video_file, audio_file):
    """
    Extract audio from a video file using the ffmpeg-python library.

    Args:
        video_file (str): Path to the input video file.
        audio_file (str): Path to save the extracted audio file.

    Returns:
        None
    """
    try:
        # Extract audio to a compatible format (e.g., AAC)
        ffmpeg.input(video_file).output(audio_file, acodec='aac').run(overwrite_output=True)
        print(f"Audio extracted to {audio_file}")
    except ffmpeg.Error as e:
        print(f"Error extracting audio: {e}")
