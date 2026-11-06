"""Build the metadata of each cohort of the Hadjas 2025 dataset.

The values shared by all cohorts are in metadata/general_metadata.yaml, including the sentences the cohorts share
(TextTemplates). This module holds what differs between cohorts and fills the shared sentences in: each recording
site gets its fiber, virus injection, indicator, FiberPhotometryTable rows and series, and each stimulated input
gets its virus injection, effector and optogenetic site.
"""

import copy

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


CHRIMSONR_AAV5_VIRUS = dict(
    name="viral_vector_ogen",
    description=(
        "pAAV-Syn-FLEX-rc[ChrimsonR-tdTomato] (AAV5) viral vector was used for optogenetic experiments. The titer was "
        "4 to 8.5e12 vg/ml across mice; titer_in_vg_per_ml is the upper bound."
    ),
    manufacturer="Addgene (catalog number 62723)",
    construct_name="pAAV-Syn-FLEX-rc[ChrimsonR-tdTomato] (AAV5)",
    titer_in_vg_per_ml=8.5e12,
)

# Glutamatergic inputs to SN injected with ChrimsonR: injection name, coordinates (AP, ML, DV from bregma, in mm) and
# how the surgery text gives them.
CHRIMSONR_INPUTS = dict(
    STN=dict(
        name="Subthalamic Nucleus (STN)",
        coordinates=(-2.0, 1.6, -4.5),
        surgery_text="STN (AP -2.00, ML +/-1.6, DV -4.5)",
    ),
    PPN=dict(
        name="Pedunculopontine Nucleus (PPN)",
        coordinates=(-4.48, 1.1, -3.75),
        surgery_text="PPN (AP -4.48, ML +/- 1.1, DV -3.75)",
    ),
)


def build_chrimsonr_input(text_templates: dict, input_name: str, virus: dict, manufacturer: str) -> dict:
    """Build the virus, injection and effector of a ChrimsonR-expressing input.

    Parameters
    ----------
    text_templates : dict
        The TextTemplates of general_metadata.yaml.
    input_name : str
        The input, a key of CHRIMSONR_INPUTS (e.g. "STN").
    virus : dict
        The metadata of the virus expressing ChrimsonR, with its key as "name".
    manufacturer : str
        Manufacturer of the effector.

    Returns
    -------
    dict
        The input for build_optogenetics_metadata.
    """
    chrimsonr_input = CHRIMSONR_INPUTS[input_name]
    injection_key = f"viral_vector_injection_{input_name}"
    return dict(
        input=input_name,
        virus=virus,
        injection=build_virus_injection_metadata(
            name=injection_key,
            description=text_templates["chrimsonr_injection"].format(name=chrimsonr_input["name"]),
            location=LOCATIONS[input_name],
            coordinates=chrimsonr_input["coordinates"],
            volume_in_uL=0.2,
            virus_key=virus["name"],
        ),
        effector=dict(
            name=f"chrimsonR_{input_name}",
            description=text_templates["chrimsonr_effector"].format(input=input_name),
            manufacturer=manufacturer,
            label="ChrimsonR-tdTomato",
            viral_vector_injection_metadata_key=injection_key,
        ),
    )


def get_chrimsonr_surgery_text(text_templates: dict, input_names: list[str]) -> str:
    """Get the surgery sentence of the AAV5 ChrimsonR injection in the given inputs.

    Parameters
    ----------
    text_templates : dict
        The TextTemplates of general_metadata.yaml.
    input_names : list of str
        The inputs, keys of CHRIMSONR_INPUTS; two inputs read "either <first> or <second>".

    Returns
    -------
    str
        The surgery sentence.
    """
    surgery_texts = [CHRIMSONR_INPUTS[input_name]["surgery_text"] for input_name in input_names]
    inputs = surgery_texts[0] if len(surgery_texts) == 1 else f"either {surgery_texts[0]} or {surgery_texts[1]}"
    return text_templates["surgery_chrimsonr"].format(inputs=inputs)


def build_optogenetics_metadata(inputs: list[dict], stimulation_fiber: str) -> dict:
    """Build the optogenetics metadata of a cohort from its stimulated inputs.

    The shared optogenetics values (laser, pulse length, table names and descriptions) are in
    general_metadata.yaml. The conversion keeps only the entries of the session's input
    (convert_session.filter_optogenetics_metadata), so the names of injections, effectors and site rows contain the
    input name.

    Parameters
    ----------
    inputs : list of dict
        One dict per stimulated input, with "input" (e.g. "STN"), "virus", "injection" and "effector" metadata, as
        built by build_chrimsonr_input.
    stimulation_fiber : str
        Key of the fiber that delivered the light.

    Returns
    -------
    dict
        "Optogenetics" metadata.
    """
    return dict(
        Optogenetics=dict(
            OptogeneticViruses={item["virus"]["name"]: item["virus"] for item in inputs},
            OptogeneticVirusInjections={item["injection"]["name"]: item["injection"] for item in inputs},
            OptogeneticEffectors={item["effector"]["name"]: item["effector"] for item in inputs},
            OptogeneticSitesTable=dict(
                rows={
                    item["input"]: dict(
                        excitation_source_metadata_key="optogenetic_excitation_source",
                        optical_fiber_metadata_key=stimulation_fiber,
                        effector_metadata_key=item["effector"]["name"],
                    )
                    for item in inputs
                }
            ),
        )
    )


def _join(*sentences: str) -> str:
    return " ".join(sentences)


def _stimulation_fiber_over_snc() -> dict:
    """Build the fiber over SNc of the striatal cohorts, which delivered the light and did not record."""
    return build_optical_fiber_metadata(
        site="SNc",
        coordinates=(-3.2, 1.4, -4.1),
        model_key="optical_fiber_model_stimulation",
        description="Chronically implanted optic fiber over SNc, through which the optogenetic stimulation was delivered.",
    )


STRIATAL_SITES = [
    dict(site="DLS", injection=(0.5, 2.25, -2.95), fiber=(0.5, 2.25, -2.75), fiber_model="optical_fiber_model_2"),
    dict(site="TS", injection=(-1.25, 2.9, -3.45), fiber=(-1.25, 2.9, -3.25), fiber_model="optical_fiber_model_2"),
]

STRIATAL_TABLE_DESCRIPTION = (
    "For monitoring DA release in striatal subregions, a fiber was implanted in SNc and a second fiber was implanted "
    "in DLS or TS."
)

VGLUT2_CRE_LINE = (
    "VGLUT2-Cre (Slc17a6tm2(cre)Lowl, RRID:IMSR_JAX:016963) mice were obtained from the Jackson Laboratory and "
    "maintained backcrossed on to C57BL/6J (RRID:IMSR_JAX:000664)."
)

DAT_FLP_LINE = (
    "DAT-Flp mice were provided by Dr. Helen Bateup (UC Berkeley; Slc6a3em1(flpo)Hbat, RRID:IMSR_JAX:035436) or by "
    "Dr. Rajeshwar Awatramani (Northwestern)."
)

AAV1_GCAMP6F_VIRUS = dict(
    name="viral_vector_gcamp6f",
    manufacturer="Addgene (catalog number 128315)",
    construct_name="AAV1-Ef1a-fDIO-GCaMP6f",
    titer_in_vg_per_ml=4.0e12,
)

GRABDA_VIRUS = dict(
    name="viral_vector_grabda",
    description=(
        "AAV9 viral vector expressing GRABDA2m dopamine sensor under EF1a promoter for fiber photometry recording in "
        "DLS or TS"
    ),
    manufacturer="Addgene (catalog number 140553)",
    construct_name="AAV9-EF1a-GRABDA2m",
    titer_in_vg_per_ml=2.0e12,
)


def _chrimsonr_aav5_inputs(text_templates: dict, input_names: tuple) -> list[dict]:
    return [
        build_chrimsonr_input(text_templates, input_name, CHRIMSONR_AAV5_VIRUS, manufacturer="Addgene")
        for input_name in input_names
    ]


def _grabda_surgery_text(text_templates: dict, genotype: str, fiber_preposition: str) -> str:
    """Get the surgery sentences of the GRAB-DA cohorts, up to the stimulated input."""
    return _join(
        text_templates["surgery_anesthesia"],
        f"For monitoring DA release in striatal subregions (DLS and TS) in {genotype} mice were injected with 300 nl "
        "of AAV9-EF1a-GRABDA2m (2e12 vg/mL, Addgene 140553) in either DLS (AP +0.5, ML +/-2.25, DV -2.95) or TS (AP "
        "-1.25, ML +/-2.9, DV -3.45). A fiber (200-um core, 0.39 NA, L = 6 mm, 1.25-mm white ceramic ferrule, RWD) was "
        f"implanted {fiber_preposition} SNc (AP -3.2, ML +/-1.4, DV -4.1) for optogenetic stimulation, and a second "
        "fiber (400-um core, 0.39 NA, L = 4 mm, 1.25-mm black ceramic ferrule, RWD) was implanted in either DLS (AP "
        "+0.5, ML +/-2.25, DV -2.75) or TS (AP -1.25, ML +/-2.9, DV -3.25).",
    )


def _grabda_recording_metadata(text_templates: dict) -> dict:
    """Build the fibers and fiber photometry of the GRAB-DA cohorts."""
    return dict_deep_update(
        _stimulation_fiber_over_snc(),
        build_fiber_photometry_metadata(
            text_templates=text_templates,
            label="GRABDA2m",
            virus=GRABDA_VIRUS,
            sites=STRIATAL_SITES,
            indicator_target="{site}",
            table_description=STRIATAL_TABLE_DESCRIPTION,
        ),
    )


def sn_pan_gaba_recordings_metadata(text_templates: dict) -> dict:
    """Build the metadata of the SNr pan-GABA GCaMP6f recordings, STN and PPN stimulation."""
    metadata = dict(
        NWBFile=dict(
            keywords=[
                "SNr fiber photometry recordings",
                "SNr GABAergic neurons",
                "VGLUT2-Cre x VGAT-Flp",
                "STN optogenetic stimulation",
                "PPN optogenetic stimulation",
                "Parkinson's disease",
            ],
            experiment_description=_join(
                "Activity of SNr GABA neurons during optogenetic stimulation of excitatory inputs to the substantia "
                "nigra (SN). In VGLUT2-Cre x VGAT-Flp mice, GCaMP6f was expressed in SNr GABA neurons and ChrimsonR was "
                "expressed in glutamatergic neurons of either the subthalamic nucleus (STN) or the pedunculopontine "
                "nucleus (PPN). Light was delivered through the SNr recording fiber.",
                text_templates["stimulation_trains"],
                text_templates["protocols"],
            ),
            surgery=_join(
                text_templates["surgery_anesthesia"],
                "For calcium recordings in VGLUT2-Cre x VGAT-Flp mice were injected with 300 nl of "
                "AAV1-Ef1a-fDIO-GCaMP6f (4e12 vg/mL, Addgene 128315) in SNr (AP -3.3, ML +/-1.3, DV -4.6). A fiber "
                "(400-um core, 0.39 NA, 6-mm length, 1.25-mm diameter black ceramic ferrule, RWD) was implanted in SNr "
                "(AP -3.3, ML +/-1.4, DV -4.4).",
                get_chrimsonr_surgery_text(text_templates, ["STN", "PPN"]),
            ),
        ),
        Subject=dict(
            description=_join(
                text_templates["subject_housing"],
                "VGLUT2-Cre (Slc17a6tm2(cre)Lowl, RRID:IMSR_JAX:016963) and VGAT-Flp (Slc32a1tm1.1(flpo)Hze, "
                "RRID:IMSR_JAX:029591) mice were obtained from the Jackson Laboratory and maintained backcrossed on to "
                "C57BL/6J (RRID:IMSR_JAX:000664).",
                text_templates["subject_genotype"].format(genotype="VGLUT2-Cre x VGAT-Flp"),
            ),
            genotype="VGLUT2-Cre x VGAT-Flp",
        ),
        Behavior=dict(
            ExternalVideos=dict(
                BehavioralVideo=dict(
                    description=(
                        "Video recording of the mouse's behavior. Recorded using a camera mounted on the ceiling above "
                        "the chambers.\n"
                    ),
                    device=dict(
                        name="BehavioralCamera",
                        description="Camera mounted on ceiling above chambers for behavioral recording",
                    ),
                )
            )
        ),
    )
    metadata = dict_deep_update(
        metadata,
        build_fiber_photometry_metadata(
            text_templates=text_templates,
            label="GCaMP6f",
            virus=dict(
                AAV1_GCAMP6F_VIRUS,
                description=(
                    "AAV1 viral vector expressing GCaMP6f calcium sensor under EF1a promoter for fiber photometry "
                    "recording in SNr"
                ),
            ),
            sites=[
                dict(
                    site="SNr",
                    injection=(-3.3, 1.3, -4.6),
                    fiber=(-3.3, 1.4, -4.4),
                    fiber_model="optical_fiber_model_1",
                )
            ],
            indicator_target="{site} GABAergic neurons",
            table_description="For monitoring calcium dynamics in SNr GABAergic neurons, a fiber was implanted in SNr.",
        ),
    )
    inputs = _chrimsonr_aav5_inputs(text_templates, ("STN", "PPN"))
    return dict_deep_update(metadata, build_optogenetics_metadata(inputs, stimulation_fiber="optical_fiber_SNr"))


def sn_pan_da_recordings_metadata(text_templates: dict) -> dict:
    """Build the metadata of the SNc pan-DA GCaMP6f recordings, STN and PPN stimulation."""
    metadata = dict(
        NWBFile=dict(
            keywords=[
                "SNc fiber photometry recordings",
                "SNc pan-dopaminergic neurons",
                "VGLUT2-Cre x DAT-Flp",
                "STN optogenetic stimulation",
                "PPN optogenetic stimulation",
                "Parkinson's disease",
            ],
            experiment_description=_join(
                "Activity of SNc dopamine neurons during optogenetic stimulation of excitatory inputs to the substantia "
                "nigra (SN). In VGLUT2-Cre x DAT-Flp mice, GCaMP6f was expressed in SNc dopamine neurons and ChrimsonR "
                "was expressed in glutamatergic neurons of either the subthalamic nucleus (STN) or the "
                "pedunculopontine nucleus (PPN). Light was delivered through the SNc recording fiber.",
                text_templates["stimulation_trains"],
                text_templates["protocols"],
            ),
            surgery=_join(
                text_templates["surgery_anesthesia"],
                "For calcium recordings in VGLUT2-Cre x DAT-Flp mice were injected with 300 nl of "
                "AAV1-Ef1a-fDIO-GCaMP6f (4e12 vg/mL, Addgene 128315) in SNc (AP -3.2, ML +/-1.3, DV -4.3). A fiber "
                "(400-um core, 0.39 NA, 6-mm length, 1.25-mm diameter black ceramic ferrule, RWD) was implanted in SNc "
                "(AP -3.2, ML +/-1.4, DV -4.1).",
                get_chrimsonr_surgery_text(text_templates, ["STN", "PPN"]),
            ),
        ),
        Subject=dict(
            description=_join(
                text_templates["subject_housing"],
                VGLUT2_CRE_LINE,
                DAT_FLP_LINE,
                text_templates["subject_genotype"].format(genotype="VGLUT2-Cre x DAT-Flp"),
            ),
            genotype="VGLUT2-Cre x DAT-Flp",
        ),
    )
    metadata = dict_deep_update(
        metadata,
        build_fiber_photometry_metadata(
            text_templates=text_templates,
            label="GCaMP6f",
            virus=dict(
                AAV1_GCAMP6F_VIRUS,
                description=(
                    "AAV1 viral vector expressing GCaMP6f calcium sensor under EF1a promoter for fiber photometry "
                    "recording in SNc"
                ),
            ),
            sites=[
                dict(
                    site="SNc",
                    injection=(-3.2, 1.3, -4.3),
                    fiber=(-3.2, 1.4, -4.1),
                    fiber_model="optical_fiber_model_1",
                )
            ],
            indicator_target="{site} dopaminergic neurons",
            table_description="For monitoring calcium dynamics in SNc dopaminergic neurons, a fiber was implanted in SNc.",
        ),
    )
    inputs = _chrimsonr_aav5_inputs(text_templates, ("STN", "PPN"))
    return dict_deep_update(metadata, build_optogenetics_metadata(inputs, stimulation_fiber="optical_fiber_SNc"))


def grabda_recordings_metadata(text_templates: dict) -> dict:
    """Build the metadata of the striatal GRAB-DA recordings (DLS and TS), STN and PPN stimulation."""
    metadata = dict(
        NWBFile=dict(
            keywords=[
                "DLS fiber photometry recordings",
                "TS fiber photometry recordings",
                "Dopamine release",
                "VGLUT2-Cre",
                "STN optogenetic stimulation",
                "PPN optogenetic stimulation",
                "Parkinson's disease",
            ],
            experiment_description=_join(
                "Dopamine release in the dorsolateral striatum (DLS) or the tail of the striatum (TS) during "
                "optogenetic stimulation of excitatory inputs to the substantia nigra (SN). In VGLUT2-Cre mice, the "
                "dopamine sensor GRAB-DA2m was expressed in DLS or TS and ChrimsonR was expressed in glutamatergic "
                "neurons of either the subthalamic nucleus (STN) or the pedunculopontine nucleus (PPN). Light was "
                "delivered through a separate fiber over SNc.",
                text_templates["stimulation_trains"],
                text_templates["protocols"],
            ),
            surgery=_join(
                _grabda_surgery_text(text_templates, genotype="VGLUT2-Cre", fiber_preposition="in"),
                get_chrimsonr_surgery_text(text_templates, ["STN", "PPN"]),
                "Mice were allowed to recover for 4 weeks before starting experiments.",
            ),
        ),
        Subject=dict(
            description=_join(text_templates["subject_housing"], VGLUT2_CRE_LINE),
            genotype="VGLUT2-Cre",
        ),
    )
    metadata = dict_deep_update(metadata, _grabda_recording_metadata(text_templates))
    inputs = _chrimsonr_aav5_inputs(text_templates, ("STN", "PPN"))
    return dict_deep_update(metadata, build_optogenetics_metadata(inputs, stimulation_fiber="optical_fiber_SNc"))


def grabda_recordings_stn_mcherry_metadata(text_templates: dict) -> dict:
    """Build the metadata of the striatal GRAB-DA recordings (DLS and TS), mCherry controls for STN stimulation.

    The control virus (construct, manufacturer, titer, volume) is not known yet; the fields marked "lab question 12"
    hold placeholders until the lab answers.
    """
    metadata = dict(
        NWBFile=dict(
            keywords=[
                "DLS fiber photometry recordings",
                "TS fiber photometry recordings",
                "Dopamine release",
                "VGLUT2-Cre",
                "STN optogenetic stimulation",
                "mCherry control",
                "Parkinson's disease",
            ],
            experiment_description=_join(
                "Control experiment for the optogenetic stimulation of STN inputs to the substantia nigra (SN), with "
                "dopamine release recorded in the dorsolateral striatum (DLS) or the tail of the striatum (TS). In "
                "VGLUT2-Cre mice, the dopamine sensor GRAB-DA2m was expressed in DLS or TS and mCherry, without an "
                "opsin, was expressed in the subthalamic nucleus (STN). Light was delivered through a separate fiber "
                "over SNc. Freely moving mice in a plastic tub received trains of 635 nm laser pulses while "
                "fluorescence was recorded, as in the mice expressing ChrimsonR.",
                text_templates["protocols"],
            ),
            surgery=_join(
                _grabda_surgery_text(text_templates, genotype="VGLUT2-Cre", fiber_preposition="in"),
                "As a control for optogenetic stimulation, a virus expressing mCherry without an opsin was injected in "
                "STN (AP -2.00, ML +/-1.6, DV -4.5). Mice were allowed to recover for 4 weeks before starting "
                "experiments.",
            ),
        ),
        Subject=dict(
            description=_join(text_templates["subject_housing"], VGLUT2_CRE_LINE),
            genotype="VGLUT2-Cre",
        ),
    )
    metadata = dict_deep_update(metadata, _grabda_recording_metadata(text_templates))
    mcherry_input = dict(
        input="STN_mCherry",
        virus=dict(
            name="viral_vector_mcherry",
            description="Control viral vector expressing mCherry without an opsin.",
            manufacturer="unknown",  # lab question 12
            construct_name="unknown",  # lab question 12
            titer_in_vg_per_ml=float("nan"),  # lab question 12
        ),
        injection=build_virus_injection_metadata(
            name="viral_vector_injection_STN_mCherry",
            description="Viral injection of the mCherry control virus into the Subthalamic Nucleus (STN).",
            location=LOCATIONS["STN"],
            coordinates=CHRIMSONR_INPUTS["STN"]["coordinates"],
            volume_in_uL=float("nan"),  # lab question 12
            virus_key="viral_vector_mcherry",
        ),
        effector=dict(
            name="mCherry_STN_mCherry",
            description=(
                "mCherry, a fluorescent protein without an opsin, expressed in the STN as a control for optogenetic "
                "stimulation."
            ),
            label="mCherry",
            viral_vector_injection_metadata_key="viral_vector_injection_STN_mCherry",
        ),
    )
    return dict_deep_update(
        metadata, build_optogenetics_metadata([mcherry_input], stimulation_fiber="optical_fiber_SNc")
    )


def grabda_recordings_snr_metadata(text_templates: dict) -> dict:
    """Build the metadata of the striatal GRAB-DA recordings (DLS and TS), SNr GABA input stimulation.

    The opsin (construct, manufacturer, titer, volume) is not known yet; the fields marked "lab question 10" hold
    placeholders until the lab answers.
    """
    metadata = dict(
        NWBFile=dict(
            keywords=[
                "DLS fiber photometry recordings",
                "TS fiber photometry recordings",
                "Dopamine release",
                "VGAT-Cre",
                "SNr optogenetic stimulation",
                "Parkinson's disease",
            ],
            experiment_description=_join(
                "Dopamine release in the dorsolateral striatum (DLS) or the tail of the striatum (TS) during "
                "optogenetic stimulation of GABAergic neurons of the substantia nigra pars reticulata (SNr). In "
                "VGAT-Cre mice, the dopamine sensor GRAB-DA2m was expressed in DLS or TS and an opsin was expressed in "
                "SNr. Light was delivered through a separate fiber over SNc. Freely moving mice in a plastic tub "
                "received trains of laser pulses while fluorescence was recorded.",
                text_templates["protocols"],
            ),
            surgery=_join(
                _grabda_surgery_text(text_templates, genotype="VGAT-Cre", fiber_preposition="over"),
                "For optogenetic stimulation, an opsin was expressed by viral injection in SNr (AP -3.3, ML +/-1.3, DV "
                "-4.6).",
            ),
        ),
        Subject=dict(
            description=_join(text_templates["subject_housing"], "The experiment used VGAT-Cre mice."),
            genotype="VGAT-Cre",
        ),
    )
    metadata = dict_deep_update(metadata, _grabda_recording_metadata(text_templates))
    snr_input = dict(
        input="SNr",
        virus=dict(
            name="viral_vector_ogen_SNr",
            description="Viral vector expressing the opsin in SNr GABAergic neurons.",
            manufacturer="unknown",  # lab question 10
            construct_name="unknown",  # lab question 10
            titer_in_vg_per_ml=float("nan"),  # lab question 10
        ),
        injection=build_virus_injection_metadata(
            name="viral_vector_injection_SNr",
            description=(
                "Viral injection of the opsin into the Substantia Nigra pars reticulata (SNr), at the site of the SNr "
                "GCaMP6f injections of the SN pan GABA recordings."
            ),
            location=LOCATIONS["SNr"],
            coordinates=(-3.3, 1.3, -4.6),
            volume_in_uL=float("nan"),  # lab question 10
            virus_key="viral_vector_ogen_SNr",
        ),
        effector=dict(
            name="opsin_SNr",
            description="Opsin used for optogenetic stimulation, expressed in GABAergic neurons of the SNr.",
            label="unknown",  # lab question 10
            viral_vector_injection_metadata_key="viral_vector_injection_SNr",
        ),
    )
    return dict_deep_update(metadata, build_optogenetics_metadata([snr_input], stimulation_fiber="optical_fiber_SNc"))


def str_da_terminal_recordings_metadata(text_templates: dict) -> dict:
    """Build the metadata of the striatal DA terminal GCaMP6f recordings (DLS and TS), STN stimulation."""
    metadata = dict(
        NWBFile=dict(
            keywords=[
                "DLS fiber photometry recordings",
                "TS fiber photometry recordings",
                "dopaminergic axon terminals",
                "VGLUT2-Cre x DAT-Flp",
                "STN optogenetic stimulation",
                "Parkinson's disease",
            ],
            experiment_description=_join(
                "Activity of dopamine axon terminals in the dorsolateral striatum (DLS) or the tail of the striatum "
                "(TS) during optogenetic stimulation of subthalamic nucleus (STN) inputs to the substantia nigra (SN). "
                "In VGLUT2-Cre x DAT-Flp mice, GCaMP6f was expressed in dopamine neurons and ChrimsonR in STN "
                "glutamatergic neurons. Light was delivered through a separate fiber over SNc.",
                text_templates["stimulation_trains"],
                text_templates["protocols"],
            ),
            surgery=_join(
                text_templates["surgery_anesthesia"],
                "For calcium recordings of striatal DA terminals in VGLUT2-Cre x DAT-Flp mice were injected with 300 nl "
                "of AAV1-Ef1a-fDIO-GCaMP6f (4e12 vg/mL, Addgene 128315) in either DLS (AP +0.5, ML +/-2.25, DV -2.95) "
                "or TS (AP -1.25, ML +/-2.9, DV -3.45). A fiber (200-um core, 0.39 NA, L = 6 mm, 1.25-mm white ceramic "
                "ferrule, RWD) was implanted in SNc (AP -3.2, ML +/-1.4, DV -4.1) for optogenetic stimulation, and a "
                "second fiber (400-um core, 0.39 NA, L = 4 mm, 1.25-mm black ceramic ferrule, RWD) was implanted in DLS "
                "(AP +0.5, ML +/-2.25, DV -2.75) or TS (AP -1.25, ML +/-2.9, DV -3.25).",
                get_chrimsonr_surgery_text(text_templates, ["STN"]),
            ),
        ),
        Subject=dict(
            description=_join(
                text_templates["subject_housing"],
                VGLUT2_CRE_LINE,
                DAT_FLP_LINE,
                text_templates["subject_genotype"].format(genotype="VGLUT2-Cre x DAT-Flp"),
            ),
            genotype="VGLUT2-Cre x DAT-Flp",
        ),
    )
    metadata = dict_deep_update(metadata, _stimulation_fiber_over_snc())
    metadata = dict_deep_update(
        metadata,
        build_fiber_photometry_metadata(
            text_templates=text_templates,
            label="GCaMP6f",
            virus=dict(
                AAV1_GCAMP6F_VIRUS,
                description=(
                    "AAV1 viral vector expressing GCaMP6f calcium sensor under EF1a promoter for fiber photometry "
                    "recording in DA neurons."
                ),
            ),
            sites=STRIATAL_SITES,
            indicator_target="{site}",
            table_description=STRIATAL_TABLE_DESCRIPTION,
        ),
    )
    inputs = _chrimsonr_aav5_inputs(text_templates, ("STN",))
    return dict_deep_update(metadata, build_optogenetics_metadata(inputs, stimulation_fiber="optical_fiber_SNc"))


def cell_type_recordings_vglut2_metadata(text_templates: dict) -> dict:
    """Build the metadata of the Parkinson's-resilient Vglut2+ dopamine subtype recordings, STN and PPN stimulation."""
    metadata = dict(
        NWBFile=dict(
            keywords=[
                "SNc fiber photometry recordings",
                "Vglut2+ dopamine subtypes",
                "VGLUT2-Cre x DAT-Flp",
                "STN optogenetic stimulation",
                "PPN optogenetic stimulation",
                "Parkinson's disease",
            ],
            experiment_description=_join(
                "Activity of Vglut2+ dopamine neurons in SNc during optogenetic stimulation of excitatory inputs to the "
                "substantia nigra (SN). In VGLUT2-Cre x DAT-Flp mice, GCaMP6f was expressed in neurons expressing both "
                "Cre and Flp (Vglut2+ dopamine neurons) and ChrimsonR was expressed in glutamatergic neurons of either "
                "the subthalamic nucleus (STN) or the pedunculopontine nucleus (PPN). Light was delivered through the "
                "SNc recording fiber.",
                text_templates["stimulation_trains"],
                text_templates["protocols"],
            ),
            surgery=_join(
                text_templates["surgery_anesthesia"],
                "For recording from Vglut2+ DA neurons in SNc, VGLUT2-Cre x DAT-Flp animals were injected with 300 nl "
                "of AAV8-Ef1a-ConFon-GCaMP6f (2.3e12 vg/ml, Addgene 137122) in SNc (AP -3.20, ML +/-1.5, DV -4.20), "
                "and AAV5-Syn-FLEX-ChrimsonR-TdTomato was injected in STN or PPN as above. A fiber (400-um core, 0.39 "
                "NA, L = 6 mm, 1.25 mm black ceramic ferrule, RWD) was implanted in SNc (AP -3.20, ML +/-1.60, DV "
                "-4.00).",
            ),
        ),
        Subject=dict(
            description=_join(
                text_templates["subject_housing"],
                VGLUT2_CRE_LINE,
                DAT_FLP_LINE,
                text_templates["subject_genotype"].format(genotype="VGLUT2-Cre x DAT-Flp"),
            ),
            genotype="VGLUT2-Cre x DAT-Flp",
        ),
    )
    metadata = dict_deep_update(
        metadata,
        build_fiber_photometry_metadata(
            text_templates=text_templates,
            label="GCaMP6f",
            virus=dict(
                name="viral_vector_gcamp6f",
                description=(
                    "AAV8 viral vector expressing GCaMP6f calcium sensor under EF1a promoter for fiber photometry "
                    "recording in SNc"
                ),
                manufacturer="Addgene (catalog number 137122)",
                construct_name="AAV8-Ef1a-ConFon-GCaMP6f",
                titer_in_vg_per_ml=2.3e12,
            ),
            sites=[
                dict(
                    site="SNc",
                    injection=(-3.2, 1.5, -4.2),
                    fiber=(-3.2, 1.6, -4.0),
                    fiber_model="optical_fiber_model_1",
                )
            ],
            indicator_target="{site} Vglut2+ DA neurons",
            table_description="For monitoring calcium dynamics in SNc Vglut2+ DA neurons, a fiber was implanted in SNc.",
        ),
    )
    inputs = _chrimsonr_aav5_inputs(text_templates, ("STN", "PPN"))
    return dict_deep_update(metadata, build_optogenetics_metadata(inputs, stimulation_fiber="optical_fiber_SNc"))


def cell_type_recordings_anxa1_metadata(text_templates: dict) -> dict:
    """Build the metadata of the Parkinson's-vulnerable Anxa1+ dopamine subtype recordings, STN and PPN stimulation."""
    metadata = dict(
        NWBFile=dict(
            keywords=[
                "SNc fiber photometry recordings",
                "DLS fiber photometry recordings",
                "Anxa1+ dopamine subtypes",
                "VGLUT2-PhiC31 x Anxa1-Cre",
                "STN optogenetic stimulation",
                "PPN optogenetic stimulation",
                "Parkinson's disease",
            ],
            experiment_description=_join(
                "Activity of Anxa1+ dopamine neurons in SNc and of their axon terminals in the dorsolateral striatum "
                "(DLS) during optogenetic stimulation of excitatory inputs to the substantia nigra (SN). In "
                "VGLUT2-PhiC31 x Anxa1-Cre mice, GCaMP8f was expressed in Anxa1+ neurons and a PhiC31-dependent "
                "ChrimsonR in glutamatergic neurons of either the subthalamic nucleus (STN) or the pedunculopontine "
                "nucleus (PPN). Fibers were implanted in SNc and DLS, and each recording site is a separate session. "
                "Light was delivered through the SNc fiber.",
                text_templates["stimulation_trains"],
                text_templates["protocols"],
            ),
            surgery=_join(
                text_templates["surgery_anesthesia"],
                "For recording from Anxa1+ neurons and terminals projecting to DLS, VGLUT2-PhiC x Anxa1-Cre mice were "
                "injected with 150-200 nl of AAVDJ-Ef1a-pSIO-ChrimsonR-tdTomato (1e13 vg/ml, Vectorbuilder) in STN or "
                "PPN at the same coordinates as above. And injected with 300 nl of AAV5-Syn-FLEX-GCaMP8f (1e13 vg/ml, "
                "Addgene 162379) in SNc (AP -3.20, ML +/-1.30, DV -4.30). Optic fibers were implanted in both SNc and "
                "DLS (400-um core, 0.39 NA, L = 6 or 4 mm, 1.25-mm black ceramic ferrule, RWD).",
            ),
        ),
        Subject=dict(
            description=_join(
                text_templates["subject_housing"],
                "VGLUT2-PhiC31 mice (Jeong et al. 2024) were provided by Dr. Byung Kook Lim (UC San Diego) and "
                "Anxa1-Cre mice (RRID:MMRRC_069931-MU) by Dr. Rajeshwar Awatramani (Northwestern).",
                text_templates["subject_genotype"].format(genotype="VGLUT2-PhiC31 x Anxa1-Cre"),
            ),
            genotype="VGLUT2-PhiC31 x Anxa1-Cre",
        ),
    )
    metadata = dict_deep_update(
        metadata,
        build_fiber_photometry_metadata(
            text_templates=text_templates,
            label="GCaMP8f",
            virus=dict(
                name="viral_vector_gcamp8f",
                description=(
                    "AAV5 viral vector expressing GCaMP8f under the synapsin promoter in Cre-expressing (Anxa1+) "
                    "neurons (FLEX), for fiber photometry recording in SNc and DLS."
                ),
                manufacturer="Addgene (catalog number 162379)",
                construct_name="AAV5-Syn-FLEX-GCaMP8f",
                titer_in_vg_per_ml=1.0e13,
            ),
            sites=[
                dict(
                    site="SNc",
                    injection=(-3.2, 1.3, -4.3),
                    fiber=(-3.2, 1.4, -4.1),
                    fiber_model="optical_fiber_model_1",
                ),
                dict(
                    site="DLS",
                    injection=(0.5, 2.25, -2.95),
                    fiber=(0.5, 2.25, -2.75),
                    fiber_model="optical_fiber_model_2",
                ),
            ],
            indicator_target="{site} Anxa1+ neurons and terminals",
            table_description=(
                "For monitoring calcium dynamics in Anxa1+ neurons and terminals, a fiber was implanted in SNc and DLS."
            ),
        ),
    )
    chrimsonr_aavdj_virus = dict(
        name="viral_vector_ogen",
        description=(
            "AAVDJ viral vector expressing ChrimsonR-tdTomato under the EF1a promoter in PhiC31-expressing (VGLUT2+) "
            "neurons (pSIO), used for optogenetic stimulation."
        ),
        manufacturer="Vectorbuilder",
        construct_name="AAVDJ-Ef1a-pSIO-ChrimsonR-tdTomato",
        titer_in_vg_per_ml=1.0e13,
    )
    inputs = [
        build_chrimsonr_input(text_templates, input_name, chrimsonr_aavdj_virus, manufacturer="Vectorbuilder")
        for input_name in ("STN", "PPN")
    ]
    return dict_deep_update(metadata, build_optogenetics_metadata(inputs, stimulation_fiber="optical_fiber_SNc"))


COHORT_METADATA_FUNCTIONS = {
    "SN pan GABA recordings": sn_pan_gaba_recordings_metadata,
    "SN pan DA recordings": sn_pan_da_recordings_metadata,
    "GRABDA recordings": grabda_recordings_metadata,
    "GRABDA recordings_STN_mCherry": grabda_recordings_stn_mcherry_metadata,
    "GRABDA recordings_SNr": grabda_recordings_snr_metadata,
    "Str_DA_terminal recordings": str_da_terminal_recordings_metadata,
    "Cell_type recordings_Vglut2": cell_type_recordings_vglut2_metadata,
    "Cell_type recordings_Anxa1": cell_type_recordings_anxa1_metadata,
}


def build_cohort_metadata(recording_type: str, text_templates: dict) -> dict:
    """Build the metadata of one cohort, which updates the metadata shared by all cohorts.

    Parameters
    ----------
    recording_type : str
        The cohort, a key of COHORT_METADATA_FUNCTIONS (e.g. "SN pan GABA recordings").
    text_templates : dict
        The TextTemplates of general_metadata.yaml.

    Returns
    -------
    dict
        The cohort metadata, a new copy at each call, so that a session can change it in place.
    """
    return copy.deepcopy(COHORT_METADATA_FUNCTIONS[recording_type](text_templates))
