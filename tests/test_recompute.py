import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile

from hnasko_lab_to_nwb.hadjas_2025.convert_session import load_cohort_metadata
from hnasko_lab_to_nwb.hadjas_2025.interfaces.fiber_photometry_table import add_fiber_photometry_table_region
from hnasko_lab_to_nwb.hadjas_2025.processing import process_raw_signal
from hnasko_lab_to_nwb.hadjas_2025.recompute import (
    add_recomputed_processed_series,
    get_block_bounds,
    get_recomputed_description,
)

SAMPLING_FREQUENCY = 2000.0
LED_MODULATION = dict(calcium_signal_in_hz=330.0, isosbestic_control_in_hz=210.0)
BLOCK_STARTING_TIMES = [0.0, 100.0]


def get_raw_block(duration: float) -> np.ndarray:
    """Return a raw signal with both LEDs modulated and slowly bleaching amplitudes."""
    t = np.arange(int(duration * SAMPLING_FREQUENCY)) / SAMPLING_FREQUENCY
    bleaching = 1 + 0.2 * np.exp(-t / 30)
    return 0.5 + 0.04 * bleaching * np.sin(2 * np.pi * 330.0 * t) + 0.02 * bleaching * np.sin(2 * np.pi * 210.0 * t)


@pytest.fixture
def metadata() -> dict:
    return load_cohort_metadata("SN pan GABA recordings")


@pytest.fixture
def nwbfile_with_raw_series(metadata):
    from ndx_fiber_photometry import FiberPhotometryResponseSeries

    nwbfile = mock_NWBFile()
    blocks = [get_raw_block(duration=20.0) for _ in BLOCK_STARTING_TIMES]
    timestamps = np.concatenate(
        [start + np.arange(len(block)) / SAMPLING_FREQUENCY for start, block in zip(BLOCK_STARTING_TIMES, blocks)]
    )
    nwbfile.add_acquisition(
        FiberPhotometryResponseSeries(
            name=metadata["FiberPhotometry"]["Fi1r_SNr"]["name"],
            description="raw signal",
            data=np.concatenate(blocks),
            unit="V",
            timestamps=timestamps,
            fiber_photometry_table_region=add_fiber_photometry_table_region(
                nwbfile=nwbfile, metadata=metadata, metadata_key="Fi1r_SNr"
            ),
        )
    )
    return nwbfile, blocks


def test_get_block_bounds_splits_at_gaps():
    timestamps = np.concatenate([np.arange(5) / 10, 100 + np.arange(3) / 10])

    assert get_block_bounds(timestamps, sampling_frequency=10.0) == [(0, 5), (5, 8)]


def test_get_recomputed_description_replaces_the_lab_provenance():
    description = "dF/F of the GCaMP6f signal in SNr, in percent, computed by the lab with custom MATLAB code."

    recomputed = get_recomputed_description(description)

    assert "computed by the lab" not in recomputed
    assert "recomputed from the raw signal with hadjas_2025.processing of hnasko-lab-to-nwb" in recomputed


def test_add_recomputed_processed_series_writes_each_block_as_the_lab_path(nwbfile_with_raw_series, metadata):
    nwbfile, blocks = nwbfile_with_raw_series

    add_recomputed_processed_series(
        nwbfile=nwbfile, metadata=metadata, raw_metadata_key="Fi1r_SNr", led_modulation=LED_MODULATION
    )

    expected = [process_raw_signal(block, SAMPLING_FREQUENCY, **LED_MODULATION) for block in blocks]
    for stream_name in ("Gc_raw", "af_raw", "Gc", "af", "dF"):
        series_metadata = metadata["FiberPhotometry"][f"{stream_name}_SNr"]
        series = nwbfile.processing["ophys"][series_metadata["name"]]
        rate = SAMPLING_FREQUENCY if stream_name.endswith("_raw") else 100.0
        # the sampling frequency is read back from the timestamps, which changes the last digits, and the
        # bi-exponential fit of dF/F amplifies that change (to below 0.001 % of dF/F)
        tolerance = dict(rtol=0, atol=1e-3) if stream_name == "dF" else dict(rtol=1e-9)
        np.testing.assert_allclose(series.data, np.concatenate([e[stream_name] for e in expected]), **tolerance)
        number_of_samples = len(expected[0][stream_name])
        assert series.timestamps[0] == BLOCK_STARTING_TIMES[0]
        assert series.timestamps[number_of_samples] == BLOCK_STARTING_TIMES[1]
        assert series.timestamps[1] == pytest.approx(1 / rate)
        assert "recomputed from the raw signal" in series.description
        assert series.unit == series_metadata["unit"]
        assert list(series.fiber_photometry_table_region.data) == [
            list(metadata["FiberPhotometry"]["FiberPhotometryTable"]["rows"]).index(row)
            for row in series_metadata["fiber_photometry_table_region"]
        ]
