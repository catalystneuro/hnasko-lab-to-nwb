from datetime import datetime
from pathlib import Path
from typing import Union

import pandas as pd


def get_video_aligned_starting_time(
    video_metadata_file_path: Union[Path, str], video_file_path: Union[Path, str], session_starting_time: datetime
) -> float:
    """Get the time offset to align the video with the session starting time.

    Args:
        video_metadata_file (Path, str):
            Path to the video metadata excel file.
        video_file_path (Path, str):
            Path to the video file.
        session_starting_time (datetime):
            The starting time of the session.

    Returns:
        float:
            The time offset in seconds to align the video with the session starting time.
    """
    video_metadata_file_path = Path(video_metadata_file_path)
    video_file_path = Path(video_file_path)
    assert video_metadata_file_path.exists(), f"Video metadata file does not exist: {video_metadata_file_path}"
    video_metadata = pd.read_excel(video_metadata_file_path)
    # There is one column file_name that contains the video file name and a column start_time that contains the starting time of the video in datetime format.
    assert "file_name" in video_metadata.columns, "Column 'file_name' not found in video metadata."
    assert "start_time" in video_metadata.columns, "Column 'start_time' not found in video metadata."
    video_metadata = video_metadata[video_metadata["file_name"] == video_file_path.name]
    assert not video_metadata.empty, f"No metadata found for video file: {video_file_path.name}"
    video_starting_time = pd.to_datetime(video_metadata["start_time"].values[0])
    assert isinstance(video_starting_time, pd.Timestamp), "Video starting time is not a valid timestamp."
    # Calculate the time offset in seconds
    time_offset = (video_starting_time - session_starting_time).total_seconds()
    assert time_offset >= 0, "Video starting time is before the session starting time."
    return time_offset


if __name__ == "__main__":
    # Example usage
    video_metadata_file = Path(
        r"D:\Hnasko-CN-data-share\SN pan GABA recordings\PPN\AnyMaze videos_slk\converted_video\Varying durations\video_metadata.xlsx"
    )
    video_file = Path(
        r"D:\Hnasko-CN-data-share\SN pan GABA recordings\PPN\AnyMaze videos_slk\converted_video\Varying durations\C4550.mp4"
    )
    session_start_time = datetime(2024, 1, 18, 7, 0, 0)

    offset = get_video_aligned_starting_time(video_metadata_file, video_file, session_start_time)
    print(f"Video starting time offset: {offset} seconds")
