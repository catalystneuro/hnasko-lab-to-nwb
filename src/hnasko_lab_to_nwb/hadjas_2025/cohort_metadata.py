"""Build the metadata of each cohort of the Hadjas 2025 dataset.

The values shared by all cohorts are in metadata/general_metadata.yaml, including the sentences the cohorts share
(TextTemplates). This module holds what differs between cohorts and fills the shared sentences in: each recording
site gets its fiber, virus injection, indicator, FiberPhotometryTable rows and series, and each stimulated input
gets its virus injection, effector and optogenetic site.
"""

from neuroconv.utils import dict_deep_update

SENSORS = dict(
    GCaMP6f=dict(
        sensor_type="calcium",
        isosbestic_wavelength_in_nm=405.0,
        isosbestic_wavelength_range_in_nm=[400.0, 410.0],
        emission_wavelength_in_nm=515.0,
    ),
    GCaMP8f=dict(
        sensor_type="calcium",
        isosbestic_wavelength_in_nm=405.0,
        isosbestic_wavelength_range_in_nm=[400.0, 410.0],
        emission_wavelength_in_nm=515.0,
    ),
    GRABDA2m=dict(
        sensor_type="dopamine",
        isosbestic_wavelength_in_nm=415.0,
        isosbestic_wavelength_range_in_nm=[410.0, 420.0],
        emission_wavelength_in_nm=520.0,
    ),
)

LOCATIONS = dict(
    SNr="substantia nigra pars reticulata (SNr)",
    SNc="substantia nigra pars compacta (SNc)",
    DLS="dorsolateral striatum (DLS)",
    TS="tail of the striatum (TS)",
    STN="subthalamic nucleus (STN)",
    PPN="pedunculopontine nucleus (PPN)",
)

OPTICAL_FIBER_MODELS = dict(
    optical_fiber_model_1=dict(
        type="OpticalFiberModel",
        name="optical_fiber_model_1",
        description="Chronically implantable optic fiber.",
        manufacturer="RWD",
        numerical_aperture=0.39,
        core_diameter_in_um=400.0,
        active_length_in_mm=6.0,
        ferrule_diameter_in_mm=1.25,
        ferrule_name="black ceramic ferrule",
    ),
    optical_fiber_model_2=dict(
        type="OpticalFiberModel",
        name="optical_fiber_model_2",
        description="Chronically implantable optic fiber.",
        manufacturer="RWD",
        numerical_aperture=0.39,
        core_diameter_in_um=400.0,
        active_length_in_mm=4.0,
        ferrule_diameter_in_mm=1.25,
        ferrule_name="black ceramic ferrule",
    ),
    optical_fiber_model_stimulation=dict(
        type="OpticalFiberModel",
        name="optical_fiber_model_stimulation",
        description="Chronically implantable optic fiber for optogenetic stimulation.",
        manufacturer="RWD",
        numerical_aperture=0.39,
        core_diameter_in_um=200.0,
        active_length_in_mm=6.0,
        ferrule_diameter_in_mm=1.25,
        ferrule_name="white ceramic ferrule",
    ),
)


def build_optical_fiber_metadata(site: str, coordinates: tuple, model_key: str, description: str) -> dict:
    """Build the metadata of an implanted optical fiber and of its model.

    Parameters
    ----------
    site : str
        The implanted site (e.g. "SNc"); the fiber is named optical_fiber_<site>.
    coordinates : tuple
        AP, ML and DV of the fiber tip from bregma, in mm, for a fiber in the right hemisphere.
    model_key : str
        Key of the fiber model in OPTICAL_FIBER_MODELS.
    description : str
        Description of the fiber.

    Returns
    -------
    dict
        "DeviceModels" with the fiber model and "Devices" with the fiber.
    """
    ap, ml, dv = coordinates
    fiber_key = f"optical_fiber_{site}"
    fiber = dict(
        type="OpticalFiber",
        name=fiber_key,
        description=description,
        fiber_insertion=dict(
            insertion_position_ap_in_mm=ap,
            insertion_position_ml_in_mm=ml,
            insertion_position_dv_in_mm=dv,
            position_reference="bregma",
            hemisphere="right",
        ),
        device_model_metadata_key=model_key,
    )
    return dict(DeviceModels={model_key: OPTICAL_FIBER_MODELS[model_key]}, Devices={fiber_key: fiber})


def build_virus_injection_metadata(
    name: str, description: str, location: str, coordinates: tuple, volume_in_uL: float, virus_key: str
) -> dict:
    """Build the metadata of a viral injection in the right hemisphere.

    Parameters
    ----------
    name : str
        Name and key of the injection.
    description : str
        Description of the injection.
    location : str
        Full name of the injected region.
    coordinates : tuple
        AP, ML and DV of the injection from bregma at the cortical surface, in mm.
    volume_in_uL : float
        Injected volume, in uL.
    virus_key : str
        Key of the injected virus.

    Returns
    -------
    dict
        The injection metadata.
    """
    ap, ml, dv = coordinates
    return dict(
        name=name,
        description=description,
        location=location,
        hemisphere="right",
        reference="bregma at the cortical surface",
        ap_in_mm=ap,
        ml_in_mm=ml,
        dv_in_mm=dv,
        volume_in_uL=volume_in_uL,
        viral_vector_metadata_key=virus_key,
    )


def build_fiber_photometry_metadata(
    text_templates: dict,
    label: str,
    virus: dict,
    sites: list[dict],
    indicator_target: str,
    table_description: str,
) -> dict:
    """Build the fiber photometry metadata of a cohort from its sensor and recording sites.

    Each site gets a fiber, a virus injection, an indicator, two FiberPhotometryTable rows (<site>_465 and
    <site>_<isosbestic wavelength>), the raw series Fi1r_<site> and the processed series Gc_raw_<site>,
    af_raw_<site>, Gc_<site>, af_<site> and dF_<site>.

    Parameters
    ----------
    text_templates : dict
        The TextTemplates of general_metadata.yaml.
    label : str
        The sensor, a key of SENSORS (e.g. "GCaMP6f").
    virus : dict
        The metadata of the virus expressing the sensor, with its key as "name".
    sites : list of dict
        One dict per recording site, in the order of the table rows, with "site" (e.g. "SNc"), "injection" (AP, ML
        and DV of the virus injection, in mm), "fiber" (AP, ML and DV of the fiber tip, in mm) and "fiber_model" (a
        key of OPTICAL_FIBER_MODELS).
    indicator_target : str
        What the indicator labels, with {site} for the site (e.g. "{site} dopaminergic neurons").
    table_description : str
        The cohort's sentences describing the FiberPhotometryTable, followed by the shared patch cord sentence.

    Returns
    -------
    dict
        "DeviceModels", "Devices" and "FiberPhotometry" metadata.
    """
    sensor = SENSORS[label]
    isosbestic = f"{sensor['isosbestic_wavelength_in_nm']:g}"
    values = dict(label=label, sensor_type=sensor["sensor_type"], isosbestic=isosbestic)
    metadata = dict(
        DeviceModels=dict(
            excitation_source_model_calcium=dict(
                description=text_templates["excitation_source_model_calcium"].format(**values)
            ),
            excitation_source_model_isosbestic=dict(
                description=text_templates["excitation_source_model_isosbestic"].format(**values),
                wavelength_range_in_nm=sensor["isosbestic_wavelength_range_in_nm"],
            ),
        ),
        Devices=dict(
            excitation_source_calcium_signal=dict(
                description=text_templates["excitation_source_calcium_signal"].format(**values)
            ),
            excitation_source_isosbestic_control=dict(
                description=text_templates["excitation_source_isosbestic_control"].format(**values)
            ),
        ),
    )
    virus_key = virus["name"]
    injections, indicators, rows, series = dict(), dict(), dict(), dict()
    for site_metadata in sites:
        site = site_metadata["site"]
        site_values = dict(values, site=site, location=LOCATIONS[site])
        metadata = dict_deep_update(
            metadata,
            build_optical_fiber_metadata(
                site=site,
                coordinates=site_metadata["fiber"],
                model_key=site_metadata["fiber_model"],
                description=text_templates["optical_fiber"],
            ),
        )
        injection_key = f"viral_vector_injection_{site}"
        injections[injection_key] = build_virus_injection_metadata(
            name=injection_key,
            description=text_templates["fiber_photometry_injection"].format(**site_values),
            location=LOCATIONS[site],
            coordinates=site_metadata["injection"],
            volume_in_uL=0.3,
            virus_key=virus_key,
        )
        indicator_key = f"{label}_{site}"
        indicators[indicator_key] = dict(
            name=indicator_key,
            description=text_templates["indicator"].format(**site_values, target=indicator_target.format(site=site)),
            manufacturer="Addgene",
            label=label,
            viral_vector_injection_metadata_key=injection_key,
        )
        signal_row, control_row = f"{site}_465", f"{site}_{isosbestic}"
        for row_key, wavelength, excitation_source in (
            (signal_row, 465.0, "excitation_source_calcium_signal"),
            (control_row, sensor["isosbestic_wavelength_in_nm"], "excitation_source_isosbestic_control"),
        ):
            rows[row_key] = dict(
                location=LOCATIONS[site],
                excitation_wavelength_in_nm=wavelength,
                emission_wavelength_in_nm=sensor["emission_wavelength_in_nm"],
                indicator_metadata_key=indicator_key,
                optical_fiber_metadata_key=f"optical_fiber_{site}",
                excitation_source_metadata_key=excitation_source,
                photodetector_metadata_key="photodetector",
                emission_filter_metadata_key="emission_filter",
                excitation_filter_metadata_key="excitation_filter",
                dichroic_mirror_metadata_key="dichroic_mirror",
            )
        series[f"Fi1r_{site}"] = dict(
            name=f"raw_signal_{site}",
            description=text_templates["raw_signal"].format(**site_values),
            fiber_photometry_table_region=[signal_row],
            fiber_photometry_table_region_description=text_templates["raw_signal_region"].format(**site_values),
        )
        for metadata_key, name, row_key, region_template, unit in (
            ("Gc_raw", "demodulated_calcium_signal", signal_row, "calcium_signal_region", "a.u."),
            ("af_raw", "demodulated_isosbestic_control", control_row, "isosbestic_control_region", "a.u."),
            ("Gc", "downsampled_calcium_signal", signal_row, "calcium_signal_region", "a.u."),
            ("af", "downsampled_isosbestic_control", control_row, "isosbestic_control_region", "a.u."),
            ("dF", "deltaF_over_F", signal_row, "deltaF_over_F_region", "percent"),
        ):
            series[f"{metadata_key}_{site}"] = dict(
                name=f"{name}_{site}",
                description=text_templates[name].format(**site_values),
                unit=unit,
                fiber_photometry_table_region=[row_key],
                fiber_photometry_table_region_description=text_templates[region_template].format(**site_values),
            )
    metadata["FiberPhotometry"] = dict(
        FiberPhotometryViruses={virus_key: virus},
        FiberPhotometryVirusInjections=injections,
        FiberPhotometryIndicators=indicators,
        FiberPhotometryTable=dict(
            name="fiber_photometry_table",
            description=f"{table_description} {text_templates['patch_cord']}",
            rows=rows,
        ),
        **series,
    )
    return metadata
