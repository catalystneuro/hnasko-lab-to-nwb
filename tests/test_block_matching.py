from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from hnasko_lab_to_nwb.hadjas_2025 import convert_session
from hnasko_lab_to_nwb.hadjas_2025.convert_session import (
    get_block_trials,
    get_train_duration_label,
    get_train_duration_trials,
    match_mat_segments,
)

FREQUENCY_EPOCS = ["H10_", "H20_", "H40_", "H05_"]


def trains(onsets, duration):
    onsets = np.asarray(onsets, dtype=float)
    return dict(onset=onsets, offset=onsets + duration)


def test_train_duration_label_comes_from_the_epocs_not_the_folder(monkeypatch):
    # C4604 (GRAB-DA PPN): the varFreq_250ms folder holds the block with 4 s trains
    epocs = {"H10_": trains([10, 31], 4.0), "H40_": trains([52], 4.01), "Tick": trains([0], 1.0)}
    monkeypatch.setattr(convert_session, "read_tdt_epocs", lambda folder_path: epocs)

    label = get_train_duration_label(Path("varFreq_250ms") / "C4604-240313-140222", FREQUENCY_EPOCS)

    assert label == "4s"


def test_train_duration_label_fails_on_an_unknown_duration(monkeypatch):
    monkeypatch.setattr(convert_session, "read_tdt_epocs", lambda folder_path: {"H10_": trains([10], 2.0)})

    with pytest.raises(ValueError, match="not one of the protocol's"):
        get_train_duration_label(Path("C0001-240101-120000"), FREQUENCY_EPOCS)


@pytest.fixture
def block_sample_counts(monkeypatch):
    counts = {}

    def read_tdt_stream(folder_path, store):
        return SimpleNamespace(data=np.zeros(counts[folder_path.name]), fs=100.0)

    monkeypatch.setattr(convert_session, "read_tdt_stream", read_tdt_stream)
    return counts


def test_match_mat_segments_by_number_of_samples(tmp_path, write_processed_mat_file, block_sample_counts):
    segments = {"s250ms": np.ones(3), "s1s": np.ones(5), "s4s": np.ones(7)}
    file_path = write_processed_mat_file(tmp_path / "processed.mat", "Gc_raw", "DLS", "C4604", segments)
    folder_paths = [Path("C4604-240313-140222"), Path("C4604-240313-141213"), Path("C4604-240313-142052")]
    block_sample_counts.update({"C4604-240313-140222": 7, "C4604-240313-141213": 3, "C4604-240313-142052": 5})

    segment_names = match_mat_segments(file_path, "DLS", "C4604", folder_paths, epoc_names=FREQUENCY_EPOCS)

    assert segment_names == ["s4s", "s250ms", "s1s"]


def test_match_mat_segments_reads_the_length_of_segments_stored_as_columns(
    tmp_path, write_processed_mat_file, block_sample_counts
):
    # The Gc_raw segments of the GRAB-DA STN varying-frequencies file are (number of samples, 1)
    segments = {"s250ms": np.ones(3), "s1s": np.ones(5)}
    file_path = write_processed_mat_file(
        tmp_path / "processed.mat", "Gc_raw", "DLS", "C3018", segments, as_columns=True
    )
    folder_paths = [Path("C3018-240213-152012"), Path("C3018-240213-153002")]
    block_sample_counts.update({"C3018-240213-152012": 5, "C3018-240213-153002": 3})

    assert match_mat_segments(file_path, "DLS", "C3018", folder_paths, epoc_names=FREQUENCY_EPOCS) == ["s1s", "s250ms"]


def test_match_mat_segments_breaks_a_length_tie_with_the_recorded_train_duration(
    tmp_path, write_processed_mat_file, block_sample_counts, monkeypatch
):
    # C0926 (Str DA terminal STN): the s250ms and s1s segments have the same number of samples
    segments = {"s250ms": np.ones(5), "s1s": np.zeros(5), "s4s": np.ones(7)}
    file_path = write_processed_mat_file(tmp_path / "processed.mat", "Gc_raw", "DLS", "C0926", segments)
    folder_paths = [Path("C0926-221206-140912"), Path("C0926-221206-141944"), Path("C0926-221206-142938")]
    block_sample_counts.update(dict.fromkeys(["C0926-221206-140912", "C0926-221206-141944"], 5))
    block_sample_counts["C0926-221206-142938"] = 7
    block_train_durations = {"C0926-221206-140912": 1.0, "C0926-221206-141944": 0.25, "C0926-221206-142938": 4.0}
    monkeypatch.setattr(
        convert_session,
        "read_tdt_epocs",
        lambda folder_path: {"H10_": trains([10], block_train_durations[folder_path.name])},
    )

    segment_names = match_mat_segments(file_path, "DLS", "C0926", folder_paths, epoc_names=FREQUENCY_EPOCS)

    assert segment_names == ["s1s", "s250ms", "s4s"]


def test_match_mat_segments_fails_without_a_segment_of_the_block_length(
    tmp_path, write_processed_mat_file, block_sample_counts
):
    file_path = write_processed_mat_file(
        tmp_path / "processed.mat", "Gc_raw", "SNc", "B8364", {"LP1mW": np.ones(3), "LP5mW": np.ones(5)}
    )
    block_sample_counts["B8364-220426-130909"] = 4

    with pytest.raises(ValueError, match="with 4 samples"):
        match_mat_segments(file_path, "SNc", "B8364", [Path("B8364-220426-130909")], epoc_names=[])


def test_match_mat_segments_uses_the_only_segment_of_a_single_block_session(tmp_path, write_processed_mat_file):
    # e.g. C3163 varying durations: the lab trimmed the recording, so the lengths differ
    file_path = write_processed_mat_file(tmp_path / "processed.mat", "Gc_raw", "SNc", "C3163", {"LP5mW": np.ones(3)})

    assert match_mat_segments(file_path, "SNc", "C3163", [Path("C3163-240227-080654")], epoc_names=[]) == ["LP5mW"]


def test_block_trials_span_each_block_and_carry_its_train_duration(monkeypatch, block_sample_counts):
    folder_paths = [Path("C4604-240313-140222"), Path("C4604-240313-141213")]
    block_sample_counts.update({"C4604-240313-140222": 501, "C4604-240313-141213": 301})
    block_epocs = {
        "C4604-240313-140222": {"H10_": trains([1.0], 4.0)},
        "C4604-240313-141213": {"H10_": trains([1.0], 1.0)},
    }
    monkeypatch.setattr(convert_session, "read_tdt_epocs", lambda folder_path: block_epocs[folder_path.name])

    block_trials = get_block_trials(folder_paths, [0.0, 591.0], FREQUENCY_EPOCS)

    assert block_trials == [
        dict(start_time=0.0, stop_time=5.0, tags="4s"),
        dict(start_time=591.0, stop_time=594.0, tags="1s"),
    ]
    assert get_block_trials(folder_paths[:1], [0.0], FREQUENCY_EPOCS) == []


def test_single_block_frequencies_trials_span_the_trains_of_each_duration(monkeypatch):
    # SN pan GABA PPN (e.g. C4550): one block with the 250 ms, then 1 s, then 4 s trains of every frequency
    epocs = {
        "H05_": dict(onset=np.array([34.5, 522.3, 1167.1]), offset=np.array([34.75, 523.3, 1171.1])),
        "H40_": dict(onset=np.array([95.3, 585.3, 1239.1]), offset=np.array([95.56, 586.3, 1243.1])),
        "H10_": dict(onset=np.array([54.8, 60.0]), offset=np.array([55.05, 60.0])),  # zero-length train, dropped
    }
    monkeypatch.setattr(convert_session, "read_tdt_epocs", lambda folder_path: epocs)

    trials = get_train_duration_trials(Path("C4550-240117-133254"), FREQUENCY_EPOCS)

    assert trials == [
        dict(start_time=34.5, stop_time=95.56, tags="250ms"),
        dict(start_time=522.3, stop_time=586.3, tags="1s"),
        dict(start_time=1167.1, stop_time=1243.1, tags="4s"),
    ]


def test_single_block_trials_fail_when_train_durations_alternate(monkeypatch):
    epocs = {"H10_": dict(onset=np.array([10.0, 31.0, 52.0]), offset=np.array([10.25, 32.0, 52.25]))}
    monkeypatch.setattr(convert_session, "read_tdt_epocs", lambda folder_path: epocs)

    with pytest.raises(ValueError, match="alternate"):
        get_train_duration_trials(Path("C0001-240101-120000"), FREQUENCY_EPOCS)
