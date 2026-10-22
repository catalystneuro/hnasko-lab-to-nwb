from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from hnasko_lab_to_nwb.hadjas_2025.convert_session import (
    add_led_modulation_to_metadata,
    get_led_modulation,
    load_cohort_metadata,
)

LAB_TIME_ZONE = ZoneInfo("America/Los_Angeles")


@pytest.mark.parametrize(
    "session_start_time, calcium_signal_in_hz, isosbestic_control_in_hz",
    [
        (datetime(2022, 4, 26, 13, 9, tzinfo=LAB_TIME_ZONE), 210.0, 330.0),  # RZ5P, 2022 cohorts
        (datetime(2023, 6, 7, 11, 0, tzinfo=LAB_TIME_ZONE), 210.0, 330.0),  # C2450 and C2454, RZ10x at 6 kHz
        (datetime(2023, 12, 31, 23, 59, tzinfo=LAB_TIME_ZONE), 210.0, 330.0),
        (datetime(2024, 1, 1, 0, 0, tzinfo=LAB_TIME_ZONE), 330.0, 210.0),
        (datetime(2025, 11, 4, 10, 0, tzinfo=LAB_TIME_ZONE), 330.0, 210.0),
    ],
)
def test_get_led_modulation_follows_the_recording_date(
    session_start_time, calcium_signal_in_hz, isosbestic_control_in_hz
):
    assert get_led_modulation(session_start_time) == dict(
        calcium_signal_in_hz=calcium_signal_in_hz, isosbestic_control_in_hz=isosbestic_control_in_hz
    )


def test_get_led_modulation_fails_before_the_first_entry():
    with pytest.raises(ValueError, match="No LED modulation"):
        get_led_modulation(datetime(2021, 12, 31, tzinfo=LAB_TIME_ZONE))


def test_add_led_modulation_to_metadata_states_the_frequency_of_each_led():
    metadata = load_cohort_metadata("GRABDA recordings")

    add_led_modulation_to_metadata(
        metadata=metadata, led_modulation=dict(calcium_signal_in_hz=330.0, isosbestic_control_in_hz=210.0)
    )

    assert metadata["Devices"]["excitation_source_calcium_signal"]["description"].endswith("Modulated at 330 Hz.")
    assert metadata["Devices"]["excitation_source_isosbestic_control"]["description"].endswith("Modulated at 210 Hz.")
    for site in ("DLS", "TS"):
        assert "Demodulated at 330 Hz" in metadata["FiberPhotometry"][f"Gc_raw_{site}"]["description"]
        assert "Demodulated at 210 Hz" in metadata["FiberPhotometry"][f"af_raw_{site}"]["description"]
        assert "Demodulated" not in metadata["FiberPhotometry"][f"Gc_{site}"]["description"]
