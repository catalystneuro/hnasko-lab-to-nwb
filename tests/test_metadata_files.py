import re
from pathlib import Path

import pytest

from hnasko_lab_to_nwb.hadjas_2025.convert_session import (
    load_cohort_metadata,
    load_external_resources_metadata,
    load_rig_devices_metadata,
    load_session_config,
)
from neuroconv.utils import dict_deep_update, load_dict_from_file

METADATA_FOLDER_PATH = Path(__file__).parents[1] / "src" / "hnasko_lab_to_nwb" / "hadjas_2025" / "metadata"


def find_values(value, is_match, path=""):
    """Return the paths of values for which is_match is true in a nested metadata structure."""
    if isinstance(value, dict):
        return [found for key, item in value.items() for found in find_values(item, is_match, f"{path}/{key}")]
    if isinstance(value, list):
        return [found for index, item in enumerate(value) for found in find_values(item, is_match, f"{path}/{index}")]
    return [path] if is_match(value) else []


@pytest.mark.parametrize("file_path", sorted(METADATA_FOLDER_PATH.glob("*.yaml")), ids=lambda path: path.name)
def test_metadata_has_no_none_strings(file_path):
    assert find_values(load_dict_from_file(file_path), lambda value: value == "None") == []


@pytest.mark.parametrize("file_path", sorted(METADATA_FOLDER_PATH.glob("*.yaml")), ids=lambda path: path.name)
def test_metadata_has_no_placeholders_or_empty_entries(file_path):
    # unknown optional fields are left out, not written as "<serial number of ...>" or as an empty key
    def is_placeholder(value):
        return isinstance(value, str) and value.startswith("<") and value.endswith(">")

    metadata = load_dict_from_file(file_path)
    assert find_values(metadata, is_placeholder) == []
    assert [path for path in find_values(metadata, lambda value: value is None) if "/rigs/" not in path] == []


def test_load_cohort_metadata_merges_shared_files_with_cohort_overrides():
    metadata = load_cohort_metadata("GRABDA recordings")

    assert metadata["NWBFile"]["lab"] == "Hnasko"
    assert metadata["Subject"]["species"] == "Mus musculus"
    assert metadata["Subject"]["genotype"] == "VGLUT2-Cre"
    isosbestic_model = metadata["DeviceModels"]["excitation_source_model_isosbestic"]
    assert isosbestic_model["source_type"] == "LED"
    assert isosbestic_model["wavelength_range_in_nm"] == [410.0, 420.0]


def test_load_cohort_metadata_updates_the_base_cohort_metadata(tmp_path, monkeypatch):
    from hnasko_lab_to_nwb.hadjas_2025 import convert_session

    for file_name in ("general_metadata.yaml", "subject_metadata.yaml", "devices_metadata.yaml"):
        (tmp_path / file_name).write_text("NWBFile:\n  lab: Hnasko\n")
    (tmp_path / "Base_recordings_metadata.yaml").write_text(
        "NWBFile:\n  keywords: [base keyword]\n  surgery: base surgery\nSubject:\n  genotype: base genotype\n"
    )
    (tmp_path / "Base_recordings_controls_metadata.yaml").write_text(
        "NWBFile:\n  keywords: [control keyword]\n  surgery: control surgery\n"
    )
    session_config = dict(cohorts={"Base recordings_controls": dict(base_cohort="Base recordings")})
    monkeypatch.setattr(convert_session, "METADATA_FOLDER_PATH", tmp_path)
    monkeypatch.setattr(convert_session, "load_session_config", lambda: session_config)

    metadata = load_cohort_metadata("Base recordings_controls")

    assert metadata["NWBFile"] == dict(lab="Hnasko", keywords=["control keyword"], surgery="control surgery")
    assert metadata["Subject"]["genotype"] == "base genotype"


@pytest.mark.parametrize(
    "rig_name, led_manufacturer, photodetector_manufacturer, photodetector_model_number",
    [
        ("RZ5P", "Doric Lenses", "Newport", "2151"),
        ("RZ10x", "Tucker-Davis Technologies", "Tucker-Davis Technologies", "RZ10x"),
    ],
)
def test_rig_devices_complete_the_shared_device_models(
    rig_name, led_manufacturer, photodetector_manufacturer, photodetector_model_number
):
    metadata = dict_deep_update(load_cohort_metadata("SN pan DA recordings"), load_rig_devices_metadata(rig_name))

    device_models = metadata["DeviceModels"]
    assert device_models["excitation_source_model_calcium"]["manufacturer"] == led_manufacturer
    assert device_models["excitation_source_model_isosbestic"]["manufacturer"] == led_manufacturer
    assert device_models["photodetector_model"]["manufacturer"] == photodetector_manufacturer
    assert device_models["photodetector_model"]["model_number"] == photodetector_model_number
    assert device_models["photodetector_model"]["detector_type"] == "photodiode"


def test_every_rig_of_the_session_config_has_a_device_set():
    assert set(load_dict_from_file(METADATA_FOLDER_PATH / "rig_devices_metadata.yaml")) == set(
        load_session_config()["rigs"]
    )


@pytest.mark.parametrize("rig_name", ["RZ5P", "RZ10x"])
@pytest.mark.parametrize("recording_type", sorted(load_session_config()["cohorts"]))
def test_every_device_model_has_a_manufacturer(recording_type, rig_name):
    # manufacturer is required by every ndx-ophys-devices model
    metadata = dict_deep_update(load_cohort_metadata(recording_type), load_rig_devices_metadata(rig_name))

    assert [key for key, model in metadata["DeviceModels"].items() if not model.get("manufacturer")] == []


def test_optogenetic_light_source_is_the_635_nm_laser():
    metadata = load_cohort_metadata("SN pan GABA recordings")

    laser_model = metadata["DeviceModels"]["optogenetic_excitation_source_model"]
    assert (laser_model["manufacturer"], laser_model["model_number"]) == ("Shanghai Laser", "RLM635TA-150FC")
    assert laser_model["source_type"] == "laser"
    assert metadata["Optogenetics"]["excitation_wavelength_in_nm"] == 635.0


@pytest.mark.parametrize("recording_type", ["GRABDA recordings", "Str_DA_terminal recordings"])
def test_striatal_cohorts_have_4_mm_recording_fibers_and_a_200_um_snc_stimulation_fiber(recording_type):
    metadata = load_cohort_metadata(recording_type)

    devices, device_models = metadata["Devices"], metadata["DeviceModels"]
    for site in ("DLS", "TS"):
        recording_fiber_model = device_models[devices[f"optical_fiber_{site}"]["device_model_metadata_key"]]
        assert (recording_fiber_model["core_diameter_in_um"], recording_fiber_model["active_length_in_mm"]) == (400, 4)
    stimulation_fiber = devices["optical_fiber_SNc"]
    assert stimulation_fiber["fiber_insertion"]["insertion_position_ap_in_mm"] == -3.2
    assert device_models[stimulation_fiber["device_model_metadata_key"]]["core_diameter_in_um"] == 200


def test_mcherry_control_sessions_have_only_the_mcherry_optogenetics_entries():
    from hnasko_lab_to_nwb.hadjas_2025.convert_session import filter_optogenetics_metadata

    metadata = load_cohort_metadata("GRABDA recordings_STN_mCherry")
    filter_optogenetics_metadata(metadata=metadata, stimulus_location="STN_mCherry")

    optogenetics = metadata["Optogenetics"]
    assert list(optogenetics["OptogeneticViruses"]) == ["viral_vector_mcherry"]
    assert list(optogenetics["OptogeneticVirusInjections"]) == ["viral_vector_injection_STN_mCherry"]
    assert list(optogenetics["OptogeneticEffectors"]) == ["mCherry_STN_mCherry"]
    assert list(optogenetics["OptogeneticSitesTable"]["rows"]) == ["STN_mCherry"]
    assert "ChrimsonR" not in metadata["NWBFile"]["surgery"]


def test_subject_age_is_the_range_older_than_6_weeks():
    assert load_cohort_metadata("GRABDA recordings")["Subject"]["age"] == "P6W/"


@pytest.mark.parametrize("file_path", sorted(METADATA_FOLDER_PATH.glob("*.yaml")), ids=lambda path: path.name)
def test_fdio_gcamp6f_has_its_addgene_catalog_number(file_path):
    # pAAV-Ef1a-fDIO-GCaMP6f is Addgene 128315; the preprint gives 1283125
    assert "1283125" not in file_path.read_text()


@pytest.mark.parametrize("recording_type", sorted(load_session_config()["cohorts"]))
def test_opsin_injection_volume_and_titer_are_the_upper_bounds_of_the_ranges(recording_type):
    # the preprint gives 150 to 200 nl of ChrimsonR at 4 to 8.5e12 vg/ml (1e13 vg/ml for the Anxa1 cohort)
    optogenetics = load_cohort_metadata(recording_type)["Optogenetics"]

    chrimson_injections = [
        injection
        for injection in optogenetics["OptogeneticVirusInjections"].values()
        if injection["viral_vector_metadata_key"] == "viral_vector_ogen"
    ]
    assert chrimson_injections
    for injection in chrimson_injections:
        assert injection["volume_in_uL"] == 0.2
        assert "150 to 200 nl" in injection["description"]
    expected_titer = 1.0e13 if recording_type == "Cell_type recordings_Anxa1" else 8.5e12
    assert optogenetics["OptogeneticViruses"]["viral_vector_ogen"]["titer_in_vg_per_ml"] == expected_titer


@pytest.mark.parametrize("recording_type", sorted(load_session_config()["cohorts"]))
def test_delta_f_over_f_is_in_percent(recording_type):
    # the lab's MATLAB code computes dF = 100 * (Gc - fit) / fit (issue #21, finding 8)
    fiber_photometry = load_cohort_metadata(recording_type)["FiberPhotometry"]

    delta_f_over_f_keys = [key for key in fiber_photometry if key.startswith("dF_")]
    assert delta_f_over_f_keys
    assert all(fiber_photometry[key]["unit"] == "percent" for key in delta_f_over_f_keys)


def test_related_publication_is_a_doi():
    assert load_cohort_metadata("GRABDA recordings")["NWBFile"]["related_publications"] == [
        "doi:10.1101/2025.06.03.657460"
    ]


@pytest.mark.parametrize("recording_type", sorted(load_session_config()["cohorts"]))
def test_genotype_names_the_mouse_lines_as_the_preprint_does(recording_type):
    # e.g. "VGLUT2-Cre x DAT-Flp": line names of the preprint, joined by " x "
    lines = load_cohort_metadata(recording_type)["Subject"]["genotype"].split(" x ")

    assert set(lines) <= {"VGLUT2-Cre", "VGAT-Flp", "DAT-Flp", "VGLUT2-PhiC31", "Anxa1-Cre"}


@pytest.mark.parametrize("recording_type", sorted(load_session_config()["cohorts"]))
def test_subject_description_names_only_the_cohort_mouse_lines(recording_type):
    subject = load_cohort_metadata(recording_type)["Subject"]

    lines = subject["genotype"].split(" x ")
    for line in ("VGLUT2-Cre", "VGAT-Flp", "DAT-Flp", "VGLUT2-PhiC31", "Anxa1-Cre"):
        assert (f"{line} " in subject["description"]) == (line in lines), line


@pytest.mark.parametrize("recording_type", sorted(load_session_config()["cohorts"]))
def test_experiment_description_mentions_only_the_converted_sessions(recording_type):
    # shock sessions, videos and AnyMaze are not part of the Hadjas 2025 dandiset
    experiment_description = load_cohort_metadata(recording_type)["NWBFile"]["experiment_description"].lower()

    for word in ("shock", "video", "anymaze", "first two days"):
        assert word not in experiment_description


def find_locations(value) -> list[str]:
    """Return the values of every "location" key in a nested metadata structure."""
    if isinstance(value, dict):
        own_location = [value["location"]] if "location" in value else []
        return own_location + [location for item in value.values() for location in find_locations(item)]
    if isinstance(value, list):
        return [location for item in value for location in find_locations(item)]
    return []


@pytest.mark.parametrize("recording_type", sorted(load_session_config()["cohorts"]))
def test_locations_are_full_anatomical_names_with_the_abbreviation(recording_type):
    # e.g. "substantia nigra pars compacta (SNc)"
    locations = find_locations(load_cohort_metadata(recording_type))

    assert locations
    assert [location for location in locations if not re.fullmatch(r"[a-z ]+ \([A-Za-z]+\)", location)] == []


@pytest.mark.parametrize("recording_type", sorted(load_session_config()["cohorts"]))
def test_processed_series_describe_the_lab_processing_steps(recording_type):
    fiber_photometry = load_cohort_metadata(recording_type)["FiberPhotometry"]

    for key, series in fiber_photometry.items():
        description = series.get("description", "")
        if key.startswith(("Gc_raw_", "af_raw_", "Gc_", "af_")):
            assert "lowpass filtered" in description and "6 Hz" in description, key
        if key.startswith(("Gc_", "af_")) and not key.startswith(("Gc_raw_", "af_raw_")):
            assert "downsampled to 100 Hz" in description, key
        if key.startswith("dF_"):
            assert "biexponential" in description and "robust linear regression" in description, key


@pytest.mark.parametrize("recording_type", sorted(load_session_config()["cohorts"]))
def test_every_device_has_a_description(recording_type):
    # NWB Inspector check_description
    devices = load_cohort_metadata(recording_type)["Devices"]

    assert [key for key, device in devices.items() if not device.get("description")] == []


def test_species_has_its_ncbi_taxon_term():
    species = load_cohort_metadata("GRABDA recordings")["Subject"]["species"]

    assert load_external_resources_metadata()["species"][species]["id"] == "NCBITaxon:10090"


@pytest.mark.parametrize("recording_type", sorted(load_session_config()["cohorts"]))
def test_strain_has_its_rrid_term(recording_type):
    strain = load_cohort_metadata(recording_type)["Subject"]["strain"]

    assert load_external_resources_metadata()["strain"][strain]["id"] == "RRID:IMSR_JAX:000664"


@pytest.mark.parametrize("recording_type", sorted(load_session_config()["cohorts"]))
def test_every_location_has_brain_region_terms(recording_type):
    brain_region_terms = load_external_resources_metadata()["brain_regions"]

    locations = find_locations(load_cohort_metadata(recording_type))
    assert [location for location in locations if location not in brain_region_terms] == []
