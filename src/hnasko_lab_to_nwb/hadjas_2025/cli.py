"""Command line of the Hadjas 2025 conversion: check, convert, inspect, organize and upload.

Run "hadjas-2025 <command> --help" for the arguments of each command. A typical run, as sessions are added:

    hadjas-2025 check <data folder> <output folder>
    hadjas-2025 convert <data folder> <output folder>
    hadjas-2025 organize <output folder> <dandiset folder> --dandi-instance dandi-sandbox
    hadjas-2025 upload <dandiset folder> --dandi-instance dandi-sandbox

check writes session_inventory.csv and data_check.csv to the output folder. convert converts the sessions that have
no NWB file yet, inspects each new file and updates conversion_summary.csv (see the inspection module). inspect
inspects every NWB file again. organize copies the NWB files into <dandiset folder>/<dandiset ID>, validates them and
writes draft_asset_report.csv next to it; upload validates and uploads that folder to the draft.
"""

import argparse
from pathlib import Path

OVERVIEW_FILE_NAME = "ASAP FP Overview.xlsx"
DANDISET_ID = "001528"


def check(args: argparse.Namespace) -> int:
    """Write the session inventory and the data check to the output folder; return 1 if the check has errors."""
    from hnasko_lab_to_nwb.hadjas_2025.convert_all_sessions import get_session_inventory
    from hnasko_lab_to_nwb.hadjas_2025.data_check import check_dataset

    args.output_dir_path.mkdir(parents=True, exist_ok=True)
    overview_file_path = args.overview_file_path or args.data_dir_path / OVERVIEW_FILE_NAME
    inventory = get_session_inventory(data_dir_path=args.data_dir_path, subjects_metadata_file_path=overview_file_path)
    inventory.to_csv(args.output_dir_path / "session_inventory.csv", index=False)
    data_check = check_dataset(data_dir_path=args.data_dir_path, subjects_metadata_file_path=overview_file_path)
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
        verbose=False,
    )
    print(f"{len(failed_sessions)} sessions failed; see convert_all_sessions.log in {args.output_dir_path}")
    return int(len(failed_sessions) > 0)


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

    for command, function in (("check", check), ("convert", convert)):
        subparser = subparsers.add_parser(command, help=function.__doc__)
        subparser.add_argument("data_dir_path", type=Path, help="data folder (the lab's data share)")
        subparser.add_argument("output_dir_path", type=Path, help="folder of the NWB files")
        subparser.add_argument(
            "--overview-file-path", type=Path, help=f"overview sheet (default: <data folder>/{OVERVIEW_FILE_NAME})"
        )
        subparser.set_defaults(function=function)
    subparsers.choices["convert"].add_argument(
        "--overwrite", action="store_true", help="convert again the sessions whose NWB file exists"
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
