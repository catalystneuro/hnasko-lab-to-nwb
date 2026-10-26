"""Convert one shock session to NWB.

A shock session is one TDT block of an SN pan GABA PPN mouse, recorded while it heard auditory cues paired (CS+) or
not paired (CS-) with a shock. The conversion reuses the parts of hadjas_2025: the metadata of the base cohort, the
raw TDT interface, and the processed signals recomputed from the raw signal (there is no lab .mat file for these
sessions).
"""

from pathlib import Path

from hnasko_lab_to_nwb.hadjas_2025.convert_session import load_cohort_metadata
from neuroconv.utils import dict_deep_update, load_dict_from_file

METADATA_FOLDER_PATH = Path(__file__).parent / "metadata"
SESSION_CONFIG_FILE_PATH = METADATA_FOLDER_PATH / "session_config.yaml"
SHOCK_SESSIONS_METADATA_FILE_PATH = METADATA_FOLDER_PATH / "shock_sessions_metadata.yaml"


def load_session_config() -> dict:
    """Load the settings of the shock session conversion (metadata/session_config.yaml)."""
    return load_dict_from_file(SESSION_CONFIG_FILE_PATH)


def load_shock_session_metadata() -> dict:
    """Load the metadata of the shock sessions: the base cohort's, updated with metadata/shock_sessions_metadata.yaml.

    Lists of the shock file (e.g. keywords) replace those of the base cohort. The optogenetics metadata is removed:
    there is no optogenetic stimulation in these sessions.

    Returns
    -------
    dict
        The merged metadata.
    """
    metadata = load_cohort_metadata(load_session_config()["base_cohort"])
    metadata = dict_deep_update(metadata, load_dict_from_file(SHOCK_SESSIONS_METADATA_FILE_PATH), append_list=False)
    metadata.pop("Optogenetics")
    return metadata
