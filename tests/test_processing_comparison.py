import numpy as np
import pandas as pd
import pytest

from hnasko_lab_to_nwb.hadjas_2025.cli import main
from hnasko_lab_to_nwb.hadjas_2025.processing_comparison import compare_signals, read_lab_segment
from test_convert_all_sessions import make_blocks, write_overview
from test_data_check import block_train_durations  # noqa: F401 (fixture)


def test_compare_signals_uses_the_common_samples():
    lab = np.array([1.0, 2.0, 3.0, 4.0])
    recomputed = np.array([1.5, 2.5, 3.5, 4.5, 9.0])

    comparison = compare_signals(recomputed=recomputed, lab=lab)

    assert comparison["recomputed_samples"] == 5
    assert comparison["lab_samples"] == 4
    assert comparison["correlation"] == pytest.approx(1.0)
    assert comparison["mean_difference"] == pytest.approx(0.5)
    assert comparison["max_absolute_difference"] == pytest.approx(0.5)
    assert comparison["lab_standard_deviation"] == pytest.approx(np.std(lab))


@pytest.mark.parametrize("as_columns", [False, True])
def test_read_lab_segment_reads_rows_and_columns(tmp_path, write_processed_mat_file, as_columns):
    file_path = write_processed_mat_file(
        file_path=tmp_path / "processed.mat",
        stream_name="Gc_raw",
        target_area="DLS",
        subject_id="C0001",
        segments={"s1s": np.arange(5.0)},
        as_columns=as_columns,
    )

    segment = read_lab_segment(file_path, "Gc_raw", "DLS", "C0001", "s1s")

    np.testing.assert_array_equal(segment, np.arange(5.0))


def test_compare_processing_reports_sessions_without_a_lab_file(tmp_path, block_train_durations):  # noqa: F811
    data_dir_path = tmp_path / "data"
    data_dir_path.mkdir()
    write_overview(
        data_dir_path / "ASAP FP Overview.xlsx", {"GRAB DA": [["C0001", "M", "VGlut2-cre", "PPN", "DLS", "R"]]}
    )
    make_blocks(data_dir_path, "C0001", "GRABDA recordings", "PPN")
    output_dir_path = tmp_path / "comparison"

    exit_code = main(["compare-processing", str(data_dir_path), str(output_dir_path)])

    assert exit_code == 1
    comparison = pd.read_csv(output_dir_path / "processing_comparison.csv")
    assert list(comparison["protocol"]) == ["Varying durations", "Varying frequencies"]
    assert comparison["error"].str.contains(".mat").all()
