from datetime import datetime
from zoneinfo import ZoneInfo

import cv2
import numpy as np

from hnasko_lab_to_nwb.hadjas_2025.nwbconverter import Hadjas2025NWBConverter

VIDEO_STARTING_TIME = 100.0


def write_video(file_path, num_frames: int = 10, frame_rate: float = 10.0):
    writer = cv2.VideoWriter(str(file_path), cv2.VideoWriter_fourcc(*"mp4v"), frame_rate, (16, 16))
    for _ in range(num_frames):
        writer.write(np.zeros((16, 16, 3), dtype="uint8"))
    writer.release()
    return file_path


def test_converter_shifts_video_frame_times_and_adds_video_trial(tmp_path):
    video_file_path = write_video(tmp_path / "C0001_1s.mp4")
    converter = Hadjas2025NWBConverter(
        source_data=dict(Video_1s=dict(file_paths=[video_file_path], video_name="BehavioralVideo_1s")),
        verbose=False,
        video_time_alignment_dict=dict(Video_1s=dict(video_starting_time=VIDEO_STARTING_TIME)),
    )
    metadata = converter.get_metadata()
    metadata["NWBFile"]["session_start_time"] = datetime(2024, 1, 17, 10, 15, tzinfo=ZoneInfo("America/Los_Angeles"))

    converter.temporally_align_data_interfaces(metadata=metadata)
    nwbfile = converter.create_nwbfile(metadata=metadata)

    frame_times = VIDEO_STARTING_TIME + np.arange(10) / 10.0
    video_series = nwbfile.acquisition["BehavioralVideo_1s"]
    if video_series.timestamps is not None:
        written_times = np.asarray(video_series.timestamps)
    else:
        written_times = video_series.starting_time + np.arange(10) / video_series.rate
    np.testing.assert_allclose(written_times, frame_times)
    trials = nwbfile.trials.to_dataframe()
    np.testing.assert_allclose(trials["start_time"], [frame_times[0]])
    np.testing.assert_allclose(trials["stop_time"], [frame_times[-1]])
    assert list(trials["tags"]) == [["1s"]]


def test_converter_adds_one_trial_per_block():
    block_trials = [dict(start_time=0.0, stop_time=5.0, tags="4s"), dict(start_time=591.0, stop_time=594.0, tags="1s")]
    converter = Hadjas2025NWBConverter(source_data=dict(), verbose=False, block_trials=block_trials)
    metadata = converter.get_metadata()
    metadata["NWBFile"]["session_start_time"] = datetime(2024, 3, 13, 14, 2, tzinfo=ZoneInfo("America/Los_Angeles"))

    trials = converter.create_nwbfile(metadata=metadata).trials.to_dataframe()

    assert list(trials["start_time"]) == [0.0, 591.0]
    assert list(trials["tags"]) == [["4s"], ["1s"]]
