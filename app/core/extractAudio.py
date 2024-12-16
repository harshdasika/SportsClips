import ffmpeg


def extract_audio(video_file: str, split_audio_file: str):
    """
    Extract audio (AAC format) from a video file.

    Args:
        video_file (str): Path to the input video file.
        split_audio_file (str): Path to save the extracted audio file (AAC format).

    Returns:
        None
    """
    try:
        ffmpeg.input(video_file).output(split_audio_file, acodec="aac").run(
            overwrite_output=True
        )
        print(f"Audio extracted to {split_audio_file}")
    except ffmpeg.Error as e:
        print(f"Error extracting audio: {e}")
        raise
