"""Command line of the Hadjas 2025 conversion: check, convert, inspect, organize, upload and compare-processing.

Run "hadjas-2025 <command> --help" for the arguments of each command. A typical run, as sessions are added:

    hadjas-2025 check <data folder> <output folder>
    hadjas-2025 convert <data folder> <output folder>
    hadjas-2025 organize <output folder> <dandiset folder> --dandi-instance dandi-sandbox
    hadjas-2025 upload <dandiset folder> --dandi-instance dandi-sandbox

check writes session_inventory.csv and data_check.csv to the output folder. convert converts the sessions that have
no NWB file yet, inspects each new file and updates conversion_summary.csv (see the inspection module). inspect
inspects every NWB file again. organize copies the NWB files into <dandiset folder>/<dandiset ID>, validates them and
writes draft_asset_report.csv next to it; upload validates and uploads that folder to the draft.

compare-processing recomputes the processed signals of each session from its raw signal (hadjas_2025.processing)
and writes their comparison with the lab's .mat files to processing_comparison.csv in the output folder; with
--plot-dir-path it also plots the isosbestic fits and dF/F of each session.
"""

import argparse
from pathlib import Path

OVERVIEW_FILE_NAME = "ASAP FP Overview.xlsx"
DANDISET_ID = "001528"


def get_data_streams(args: argparse.Namespace) -> dict | None:
    """Return the data streams set on the command line ("processed" from --processed), or None for the config."""
    if args.processed is None:
        return None
    return dict(processed=False if args.processed == "none" else args.processed)


def check(args: argparse.Namespace) -> int:
    """Write the session inventory and the data check to the output folder; return 1 if the check has errors."""
    from hnasko_lab_to_nwb.hadjas_2025.convert_all_sessions import get_session_inventory
    from hnasko_lab_to_nwb.hadjas_2025.data_check import check_dataset

    args.output_dir_path.mkdir(parents=True, exist_ok=True)
    overview_file_path = args.overview_file_path or args.data_dir_path / OVERVIEW_FILE_NAME
    inventory = get_session_inventory(data_dir_path=args.data_dir_path, subjects_metadata_file_path=overview_file_path)
    inventory.to_csv(args.output_dir_path / "session_inventory.csv", index=False)
    data_check = check_dataset(
        data_dir_path=args.data_dir_path,
        subjects_metadata_file_path=overview_file_path,
        data_streams=get_data_streams(args),
    )
    data_check.to_csv(args.output_dir_path / "data_check.csv", index=False)
    print(f"{len(inventory)} sessions; data check findings by severity and check:")
    print(data_check.groupby(["severity", "check"]).size().to_string() if len(data_check) else "none")
    return int((data_check["severity"] == "error").any())


def convert(args: argparse.Namespace) -> int:
    """Convert the sessions without an NWB file (all with --overwrite); return 1 if a session failed."""
    from hnasko_lab_to_nwb.hadjas_2025.convert_all_sessions import dataset_to_nwb

    failed_sessions = dataset_to_nwb(
        data_dir_path=args.data_dir_path,
        output_dir_path=args.output_dir_path,
        subjects_metadata_file_path=args.overview_file_path or args.data_dir_path / OVERVIEW_FILE_NAME,
        overwrite=args.overwrite,
        data_streams=get_data_streams(args),
        verbose=False,
    )
    print(f"{len(failed_sessions)} sessions failed; see convert_all_sessions.log in {args.output_dir_path}")
    return int(len(failed_sessions) > 0)


def compare_processing(args: argparse.Namespace) -> int:
    """Recompute the processed signals and compare them with the lab's .mat files; return 1 if a session failed."""
    from hnasko_lab_to_nwb.hadjas_2025.processing_comparison import compare_dataset_processing

    args.output_dir_path.mkdir(parents=True, exist_ok=True)
    comparison = compare_dataset_processing(
        data_dir_path=args.data_dir_path,
        subjects_metadata_file_path=args.overview_file_path or args.data_dir_path / OVERVIEW_FILE_NAME,
        subject_ids=args.subject_ids,
        plot_dir_path=args.plot_dir_path,
    )
    comparison.to_csv(args.output_dir_path / "processing_comparison.csv", index=False)
    compared = comparison[comparison["error"].isna()]
    number_of_sessions = compared.groupby(["subject_id", "protocol_folder_path"]).ngroups
    print(f"{number_of_sessions} sessions compared; correlation by stream:")
    print(compared.groupby("stream")["correlation"].describe()[["count", "min", "50%"]].to_string())
    failed = comparison[comparison["error"].notna()]
    for _, row in failed.iterrows():
        print(f"{row['subject_id']} {row['protocol']}: {row['error']}")
    return int(len(failed) > 0)


def inspect(args: argparse.Namespace) -> int:
    """Inspect every NWB file of the output folder again and update the conversion summary."""
    from hnasko_lab_to_nwb.hadjas_2025.inspection import IMPORTANCE_LEVELS, inspect_output_folder

    summary = inspect_output_folder(args.output_dir_path)
    print(summary[["nwbfile_name", *IMPORTANCE_LEVELS, "herd_references"]].to_string(index=False))
    return 0


def organize(args: argparse.Namespace) -> int:
    """Organize the NWB files, validate them and report the draft assets; return 1 if validation has errors."""
    from hnasko_lab_to_nwb.hadjas_2025.upload_to_DANDI import (
        organize_nwbfiles,
        report_draft_assets,
        validate_organized_files,
    )

    dandiset_path = organize_nwbfiles(
        nwb_folder_path=args.output_dir_path,
        dandiset_folder_path=args.dandiset_folder_path,
        dandiset_id=args.dandiset_id,
        dandi_instance=args.dandi_instance,
    )
    report = report_draft_assets(
        dandiset_path=dandiset_path, dandiset_id=args.dandiset_id, dandi_instance=args.dandi_instance
    )
    report_file_path = args.dandiset_folder_path / "draft_asset_report.csv"
    report.to_csv(report_file_path, index=False)
    print(f"Draft assets by status ({report_file_path}):")
    print(report["status"].value_counts().to_string())
    errors = validate_organized_files(dandiset_path)
    print(f"{len(errors)} validation errors")
    print("\n".join(errors))
    return int(len(errors) > 0)


def upload(args: argparse.Namespace) -> int:
    """Validate the organized dandiset folder and upload it to the draft."""
    from hnasko_lab_to_nwb.hadjas_2025.upload_to_DANDI import upload_organized_files

    upload_organized_files(
        dandiset_path=args.dandiset_folder_path / args.dandiset_id, dandi_instance=args.dandi_instance
    )
    return 0


def get_parser() -> argparse.ArgumentParser:
    """Build the parser of the command line, with one subcommand per step."""
    from hnasko_lab_to_nwb.hadjas_2025.upload_to_DANDI import DANDI_INSTANCES

    parser = argparse.ArgumentParser(prog="hadjas-2025", description=__doc__.splitlines()[0])
    subparsers = parser.add_subparsers(required=True)

    for command, function in (("check", check), ("convert", convert), ("compare-processing", compare_processing)):
        subparser = subparsers.add_parser(command, help=function.__doc__)
        subparser.add_argument("data_dir_path", type=Path, help="data folder (the lab's data share)")
        subparser.add_argument("output_dir_path", type=Path, help="folder of the NWB files")
        subparser.add_argument(
            "--overview-file-path", type=Path, help=f"overview sheet (default: <data folder>/{OVERVIEW_FILE_NAME})"
        )
        subparser.set_defaults(function=function)
    for command in ("check", "convert"):
        subparsers.choices[command].add_argument(
            "--processed",
            choices=["lab", "recomputed", "none"],
            help="processed signals from the lab's .mat files, recomputed from the raw signal, or none (default: "
            "data_streams.processed of the session config)",
        )
    subparsers.choices["convert"].add_argument(
        "--overwrite", action="store_true", help="convert again the sessions whose NWB file exists"
    )

    subparsers.choices["compare-processing"].add_argument(
        "--subject-ids", nargs="+", help="compare only the sessions of these subjects (default: all)"
    )
    subparsers.choices["compare-processing"].add_argument(
        "--plot-dir-path",
        type=Path,
        help="write one plot per session (isosbestic fits and dF/F) to this folder; needs matplotlib",
    )

    subparser = subparsers.add_parser("inspect", help=inspect.__doc__)
    subparser.add_argument("output_dir_path", type=Path, help="folder of the NWB files")
    subparser.set_defaults(function=inspect)

    for command, function in (("organize", organize), ("upload", upload)):
        subparser = subparsers.add_parser(command, help=function.__doc__)
        if command == "organize":
            subparser.add_argument("output_dir_path", type=Path, help="folder of the NWB files")
        subparser.add_argument("dandiset_folder_path", type=Path, help="folder of the organized dandiset folder")
        subparser.add_argument(
            "--dandi-instance", required=True, choices=DANDI_INSTANCES, help="the DANDI archive or the sandbox"
        )
        subparser.add_argument("--dandiset-id", default=DANDISET_ID, help=f"dandiset (default: {DANDISET_ID})")
        subparser.set_defaults(function=function)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command line; return the exit code of the command."""
    args = get_parser().parse_args(argv)
    return args.function(args)


if __name__ == "__main__":
    raise SystemExit(main())
