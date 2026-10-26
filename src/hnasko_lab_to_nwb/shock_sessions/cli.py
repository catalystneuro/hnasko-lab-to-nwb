"""Command line of the shock session conversion: convert and inspect.

Run "shock-sessions <command> --help" for the arguments of each command:

    shock-sessions convert <data folder> <output folder>
    shock-sessions inspect <output folder>

convert converts the shock sessions that have no NWB file yet, inspects each new file and updates
conversion_summary.csv in the output folder; inspect inspects every NWB file again. The shock sessions have no
dandiset, so there is no upload step.
"""

import argparse
from pathlib import Path

OVERVIEW_FILE_NAME = "ASAP FP Overview.xlsx"


def convert(args: argparse.Namespace) -> int:
    """Convert the shock sessions without an NWB file (all with --overwrite); return 1 if a session failed."""
    from hnasko_lab_to_nwb.shock_sessions.convert_all_sessions import dataset_to_nwb

    failed_sessions = dataset_to_nwb(
        data_dir_path=args.data_dir_path,
        output_dir_path=args.output_dir_path,
        subjects_metadata_file_path=args.overview_file_path or args.data_dir_path / OVERVIEW_FILE_NAME,
        overwrite=args.overwrite,
        processed=not args.no_processed,
    )
    print(f"{len(failed_sessions)} sessions failed; see convert_all_sessions.log in {args.output_dir_path}")
    return int(len(failed_sessions) > 0)


def inspect(args: argparse.Namespace) -> int:
    """Inspect every NWB file of the output folder again and update the conversion summary."""
    from hnasko_lab_to_nwb.hadjas_2025.inspection import IMPORTANCE_LEVELS, inspect_output_folder

    summary = inspect_output_folder(args.output_dir_path)
    print(summary[["nwbfile_name", *IMPORTANCE_LEVELS, "herd_references"]].to_string(index=False))
    return 0


def get_parser() -> argparse.ArgumentParser:
    """Build the parser of the command line, with one subcommand per step."""
    parser = argparse.ArgumentParser(prog="shock-sessions", description=__doc__.splitlines()[0])
    subparsers = parser.add_subparsers(required=True)

    subparser = subparsers.add_parser("convert", help=convert.__doc__)
    subparser.add_argument("data_dir_path", type=Path, help="data folder (the lab's data share)")
    subparser.add_argument("output_dir_path", type=Path, help="folder of the NWB files")
    subparser.add_argument(
        "--overview-file-path", type=Path, help=f"overview sheet (default: <data folder>/{OVERVIEW_FILE_NAME})"
    )
    subparser.add_argument("--overwrite", action="store_true", help="convert again the sessions whose NWB file exists")
    subparser.add_argument(
        "--no-processed", action="store_true", help="do not write the processed signals recomputed from the raw signal"
    )
    subparser.set_defaults(function=convert)

    subparser = subparsers.add_parser("inspect", help=inspect.__doc__)
    subparser.add_argument("output_dir_path", type=Path, help="folder of the NWB files")
    subparser.set_defaults(function=inspect)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command line; return the exit code of the command."""
    args = get_parser().parse_args(argv)
    return args.function(args)


if __name__ == "__main__":
    raise SystemExit(main())
