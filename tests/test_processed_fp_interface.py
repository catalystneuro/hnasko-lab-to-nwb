from pathlib import Path

from hnasko_lab_to_nwb.hadjas_2025.interfaces.processed_fp_interface import get_series_target_area


def test_get_series_target_area_uses_folder_name_for_anxa1():
    file_path = Path("Cell_type recordings") / "PPN" / "Fiber photometry_TDT" / "Anxa1 DLS" / "processed.mat"
    assert get_series_target_area(target_area="PPN_to_Anxa1", file_path=file_path) == "DLS"
    assert get_series_target_area(target_area="STN_to_Anxa1", file_path=file_path) == "DLS"


def test_get_series_target_area_keeps_other_target_areas():
    file_path = Path("GRABDA recordings") / "PPN" / "Fiber photometry_TDT" / "Varying durations" / "processed.mat"
    assert get_series_target_area(target_area="DLS", file_path=file_path) == "DLS"
