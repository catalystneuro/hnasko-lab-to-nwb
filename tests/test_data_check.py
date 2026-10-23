from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from hnasko_lab_to_nwb.hadjas_2025.data_check import check_dataset, check_session
from hnasko_lab_to_nwb.hadjas_2025.utils import tdt_blocks
from test_convert_all_sessions import make_blocks, write_overview

SUBJECT_METADATA = {"Animal ID": "C0001", "Sex": "M", "Hemisphere": "R", "Recording Site": "DLS"}
EPOC_NAMES = ("H05_", "H10_", "H20_", "H40_", "s1s_")  # one epoc of each protocol


@pytest.fixture
def block_train_durations(monkeypatch):
    """Serve every TDT block as a 10 s RZ10x block with one train per frequency epoc and one s1s_ train.

    The trains last the duration that the returned dict gives for the block folder name, or else the duration of
    the block's varFreq_* folder, or else 1 s.
    """
    train_duration_by_block = dict()
    folder_train_durations = dict(varFreq_250ms=0.25, varFreq_1s=1.0, varFreq_4s=4.0)

    def read_block(folder_path, **kwargs):
        folder_path = Path(folder_path)
        duration = train_duration_by_block.get(
            folder_path.name, folder_train_durations.get(folder_path.parent.name, 1.0)
        )
        epocs = {
            name: SimpleNamespace(onset=np.array([1.0]), offset=np.array([1.0 + duration]), data=np.array([1.0]))
            for name in EPOC_NAMES
        }
        return SimpleNamespace(
            streams=dict(Fi1r=SimpleNamespace(data=np.ones(10, dtype="float32"), fs=6103.515625)),
            epocs=epocs,
            info=SimpleNamespace(start_date=datetime(2024, 1, 17, 10, 15, tzinfo=ZoneInfo("America/Los_Angeles"))),
        )

    monkeypatch.setattr(tdt_blocks, "_read_block", read_block)
    tdt_blocks.clear_tdt_block_cache()
    yield train_duration_by_block
    tdt_blocks.clear_tdt_block_cache()


def make_frequency_blocks(protocol_folder_path: Path, subject_id: str) -> None:
    for duration, time in (("250ms", "110000"), ("1s", "120000"), ("4s", "130000")):
        (protocol_folder_path / f"varFreq_{duration}" / f"{subject_id}-240117-{time}").mkdir(parents=True)


def test_check_session_warns_about_a_varfreq_folder_with_other_train_durations(tmp_path, block_train_durations):
    # e.g. C4604 and C8972, whose varFreq_250ms and varFreq_4s folders are swapped
    protocol_folder_path = tmp_path / "GRABDA recordings" / "PPN" / "Fiber photometry_TDT" / "Varying frequencies"
    make_frequency_blocks(protocol_folder_path, "C0001")
    block_train_durations.update({"C0001-240117-110000": 4.0, "C0001-240117-130000": 0.25})

    findings = check_session(
        subject_metadata=SUBJECT_METADATA,
        protocol_folder_path=protocol_folder_path,
        recording_type="GRABDA recordings",
        stimulus_location="PPN",
        protocol="Varying frequencies",
        data_streams=dict(processed=False),
    )

    assert [(finding["severity"], finding["check"]) for finding in findings] == [("warning", "train duration")] * 2
    assert findings[0]["detail"].startswith("C0001-240117-110000 has 4s trains but is in varFreq_250ms")


def test_check_session_reports_every_error_of_a_session(tmp_path, block_train_durations):
    protocol_folder_path = tmp_path / "GRABDA recordings" / "PPN" / "Fiber photometry_TDT" / "Varying frequencies"
    make_frequency_blocks(protocol_folder_path, "C0001")
    block_train_durations["C0001-240117-120000"] = 2.0  # not a train duration of the protocol

    findings = check_session(
        subject_metadata=dict(SUBJECT_METADATA, Hemisphere=np.nan),
        protocol_folder_path=protocol_folder_path,
        recording_type="GRABDA recordings",
        stimulus_location="PPN",
        protocol="Varying frequencies",
    )

    assert [(finding["severity"], finding["check"]) for finding in findings] == [
        ("error", "hemisphere"),
        ("error", "stimulation trains"),
        ("error", "processed data"),
    ]
    assert "Expected one .mat file" in findings[2]["detail"]


def test_check_dataset_lists_blocks_that_no_session_converts(tmp_path, block_train_durations):
    overview_file_path = tmp_path / "overview.xlsx"
    write_overview(overview_file_path, {"GRAB DA": [["C0001", "M", "VGlut2-cre", "PPN", "DLS", "R"]]})
    make_blocks(tmp_path, "C0001", "GRABDA recordings", "PPN")
    make_blocks(tmp_path, "C0002", "GRABDA recordings", "PPN")  # not in the overview sheet
    make_blocks(tmp_path, "C0003", "GRABDA recordings", "SNr")  # input not in the session config

    data_check = check_dataset(
        data_dir_path=tmp_path, subjects_metadata_file_path=overview_file_path, data_streams=dict(processed=False)
    )

    assert data_check[["subject_id", "protocol", "check"]].values.tolist() == [
        ["C0002", "Varying durations", "unconverted block"],
        ["C0002", "Varying frequencies", "unconverted block"],
        ["C0003", "Varying durations", "unconverted block"],
        ["C0003", "Varying frequencies", "unconverted block"],
    ]
