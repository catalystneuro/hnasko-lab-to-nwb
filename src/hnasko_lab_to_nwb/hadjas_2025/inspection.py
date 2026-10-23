"""Inspect converted NWB files with NWB Inspector and keep a summary of the conversion.

Each NWB file gets an NWB Inspector report, inspector_reports/<file stem>.txt in the output folder. The conversion
summary, conversion_summary.csv in the output folder, has one row per NWB file with its session, the status of its
last conversion, the number of inspector messages per importance level and the number of HERD references (ontology
terms, see metadata/external_resources_metadata.yaml), which is 0 if the terms were not written.
"""

from pathlib import Path
from typing import Union

import pandas as pd

INSPECTOR_REPORT_FOLDER_NAME = "inspector_reports"
CONVERSION_SUMMARY_FILE_NAME = "conversion_summary.csv"
IMPORTANCE_LEVELS = ["ERROR", "PYNWB_VALIDATION", "CRITICAL", "BEST_PRACTICE_VIOLATION", "BEST_PRACTICE_SUGGESTION"]
CONVERSION_SUMMARY_COLUMNS = [
    "nwbfile_name",
    "subject_id",
    "protocol",
    "protocol_folder_path",
    "status",
    "error",
    *IMPORTANCE_LEVELS,
    "herd_references",
]
NWBFILE_SUMMARY_COLUMNS = [*IMPORTANCE_LEVELS, "herd_references"]


def inspect_nwbfile_and_save_report(nwbfile_path: Union[str, Path]) -> dict:
    """Run NWB Inspector with the DANDI configuration on one NWB file and save its report.

    The report is saved to inspector_reports/<file stem>.txt in the folder of the NWB file, replacing an earlier one.

    Parameters
    ----------
    nwbfile_path : Union[str, Path]
        Path to the NWB file.

    Returns
    -------
    dict
        The number of inspector messages per importance level of IMPORTANCE_LEVELS.
    """
    from nwbinspector import format_messages, inspect_nwbfile, load_config, save_report

    nwbfile_path = Path(nwbfile_path)
    messages = list(inspect_nwbfile(nwbfile_path=nwbfile_path, config=load_config("dandi")))
    report_folder_path = nwbfile_path.parent / INSPECTOR_REPORT_FOLDER_NAME
    report_folder_path.mkdir(exist_ok=True)
    save_report(
        report_file_path=report_folder_path / f"{nwbfile_path.stem}.txt",
        formatted_messages=format_messages(messages, levels=["importance", "check_function_name"]),
        overwrite=True,
    )
    return {level: sum(message.importance.name == level for message in messages) for level in IMPORTANCE_LEVELS}


def count_herd_references(nwbfile_path: Union[str, Path]) -> int:
    """Count the HERD references (ontology terms of the values of the file) of an NWB file."""
    from pynwb import NWBHDF5IO

    with NWBHDF5IO(nwbfile_path, "r") as io:
        external_resources = io.read().external_resources
        return 0 if external_resources is None else len(external_resources.to_dataframe())


def summarize_nwbfile(nwbfile_path: Union[str, Path]) -> dict:
    """Inspect an NWB file and count its HERD references, for the conversion summary.

    Parameters
    ----------
    nwbfile_path : Union[str, Path]
        Path to the NWB file.

    Returns
    -------
    dict
        The fields of NWBFILE_SUMMARY_COLUMNS: the counts of inspect_nwbfile_and_save_report (which saves the
        report) and "herd_references" from count_herd_references.
    """
    return dict(**inspect_nwbfile_and_save_report(nwbfile_path), herd_references=count_herd_references(nwbfile_path))


def update_conversion_summary(output_dir_path: Union[str, Path], rows: list[dict]) -> pd.DataFrame:
    """Write rows to the conversion summary of an output folder, replacing the rows of the same NWB files.

    Parameters
    ----------
    output_dir_path : Union[str, Path]
        The folder of the NWB files.
    rows : list[dict]
        One row per NWB file, with keys from CONVERSION_SUMMARY_COLUMNS. A row updates the fields it has of the
        existing row of its NWB file.

    Returns
    -------
    pd.DataFrame
        The updated summary, sorted by NWB file name.
    """
    summary_file_path = Path(output_dir_path) / CONVERSION_SUMMARY_FILE_NAME
    nwbfile_name_to_row = dict()
    if summary_file_path.exists():
        summary = pd.read_csv(summary_file_path, dtype=str, keep_default_na=False)
        nwbfile_name_to_row = {row["nwbfile_name"]: row for row in summary.to_dict(orient="records")}
    for row in rows:
        nwbfile_name_to_row[row["nwbfile_name"]] = dict(nwbfile_name_to_row.get(row["nwbfile_name"], {}), **row)
    summary = pd.DataFrame(
        [nwbfile_name_to_row[nwbfile_name] for nwbfile_name in sorted(nwbfile_name_to_row)],
        columns=CONVERSION_SUMMARY_COLUMNS,
    )
    summary.to_csv(summary_file_path, index=False)
    return summary


def inspect_output_folder(output_dir_path: Union[str, Path]) -> pd.DataFrame:
    """Inspect every NWB file of an output folder again, count its HERD references and update the conversion summary.

    Parameters
    ----------
    output_dir_path : Union[str, Path]
        The folder of the NWB files.

    Returns
    -------
    pd.DataFrame
        The updated conversion summary.
    """
    rows = [
        dict(nwbfile_name=nwbfile_path.name, **summarize_nwbfile(nwbfile_path))
        for nwbfile_path in sorted(Path(output_dir_path).glob("*.nwb"))
    ]
    return update_conversion_summary(output_dir_path=output_dir_path, rows=rows)
