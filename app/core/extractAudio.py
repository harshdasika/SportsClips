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


def extract_video_without_audio(video_file: str, split_video_file: str):
    """
    Extract video (no audio) from a video file, copying the original video codec.

    Args:
        video_file (str): Path to the input video file.
        split_video_file (str): Path to save the extracted video file (no audio).

    Returns:
        None
    """
    try:
        ffmpeg.input(video_file).output(split_video_file, an=None, vcodec="copy").run(
            overwrite_output=True
        )
        print(f"Video without audio extracted to {split_video_file}")
    except ffmpeg.Error as e:
        print(f"Error extracting video without audio: {e}")
        raise
