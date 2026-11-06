"""List the sessions in the overview sheet that have no NWB file on the DANDI draft."""

from pathlib import Path
from typing import Union

import pandas as pd
from dandi.dandiapi import DandiAPIClient


def get_sessions_missing_on_dandi(
    subjects_metadata_file_path: Union[str, Path],
    dandiset_id: str = "001528",
    session_ids: tuple[str, ...] = ("varying-durations", "varying-frequencies"),
) -> list[dict]:
    """Return the sessions listed in the overview sheet that have no NWB file on the draft of a dandiset.

    Parameters
    ----------
    subjects_metadata_file_path : Union[str, Path]
        The path to the Excel overview file. Every sheet is read and must have an "Animal ID" column.
    dandiset_id : str, optional
        The dandiset to check, by default "001528".
    session_ids : tuple[str, ...], optional
        The session IDs expected for each subject, by default ("varying-durations", "varying-frequencies").

    Returns
    -------
    list[dict]
        One entry per missing session, with keys "sheet_name", "subject_id" and "session_id".
    """
    sheets = pd.read_excel(subjects_metadata_file_path, sheet_name=None)
    missing_sessions = []
    with DandiAPIClient() as client:
        dandiset = client.get_dandiset(dandiset_id, "draft")
        for sheet_name, subjects_metadata in sheets.items():
            for subject_id in subjects_metadata["Animal ID"]:
                for session_id in session_ids:
                    pattern = f"sub-{subject_id}/sub-{subject_id}_ses-{session_id}*.nwb"
                    if next(dandiset.get_assets_by_glob(pattern=pattern), None) is None:
                        missing_sessions.append(
                            {"sheet_name": sheet_name, "subject_id": subject_id, "session_id": session_id}
                        )
    return missing_sessions


if __name__ == "__main__":
    subjects_metadata_file_path = Path("D:/Hnasko-CN-data-share/ASAP FP Overview.xlsx")
    for missing_session in get_sessions_missing_on_dandi(subjects_metadata_file_path=subjects_metadata_file_path):
        print(missing_session)
