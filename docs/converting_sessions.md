# Converting sessions

A session is one protocol of one subject (one site for Anxa1 mice) and becomes one NWB file,
`sub-<subject>_ses-<session>.nwb`. Sessions are converted with the `hadjas-2025` command, installed with the package
(see the [README](../README.md#installation)). Run it from the conda environment of the package:

```bash
conda activate hnasko-lab-to-nwb-env
hadjas-2025 --help
```

Each command takes the data folder (the lab's data share, see [Data organization](data_organization.md)) and an
output folder for the NWB files and reports. Run `hadjas-2025 <command> --help` for all options.

## 1. Check the data

```bash
hadjas-2025 check "<data folder>" "<output folder>"
```

This reads the overview sheet, the TDT blocks and the lab's `.mat` files without writing any NWB file, and writes two
tables to the output folder:

- `session_inventory.csv`: one row per session that will be converted, with its NWB file name and TDT blocks.
- `data_check.csv`: one row per finding, with its `severity`, `check` and `detail`.

Errors are problems that make the conversion of a session fail, for example an unknown hemisphere in the sheet, a
block that cannot be read, or a `.mat` file without a segment for a block. Warnings are cases the conversion handles,
such as a `varFreq_*` folder whose name disagrees with the recorded train duration, or a block that no row of the
sheet converts. See [Troubleshooting](troubleshooting.md) for what to do with each.

The command returns a non-zero exit code if there are errors.

## 2. Convert

```bash
hadjas-2025 convert "<data folder>" "<output folder>"
```

Sessions whose NWB file is already in the output folder are skipped, so the same command converts only the new
sessions after recordings are added to the share. Add `--overwrite` to convert every session again, for example
after a change to the metadata.

A session that fails does not stop the others. For each session the command:

- writes the NWB file to the output folder,
- runs NWB Inspector on it and saves the report to `inspector_reports/<file name>.txt`,
- updates `conversion_summary.csv`: the status of the session (`converted` or `failed`), the error if it failed, the
  number of inspector messages per importance level, and the number of ontology references in the file.

The full log, with the traceback of each failure, is appended to `convert_all_sessions.log`.

`--processed lab|recomputed|none` overrides where the processed signals come from for this run (see
[Data streams](data_streams.md)).

## 3. Inspect again

```bash
hadjas-2025 inspect "<output folder>"
```

Runs NWB Inspector again on every NWB file of the output folder and updates the conversion summary, for example after
updating NWB Inspector.

## Converting one session from Python

`session_to_nwb` converts one session. Its arguments are the subject's row of the overview sheet, the protocol folder
and the cohort (an entry of `cohorts` in the session config):

```python
from pathlib import Path

import pandas as pd

from hnasko_lab_to_nwb.hadjas_2025.convert_session import session_to_nwb

data_dir_path = Path("<data folder>")
subjects = pd.read_excel(data_dir_path / "ASAP FP Overview.xlsx", sheet_name="GRAB DA")
subject_metadata = subjects[subjects["Animal ID"] == "C9170"].iloc[0].to_dict()

session_to_nwb(
    output_dir_path=Path("<output folder>"),
    subject_metadata=subject_metadata,
    protocol_folder_path=data_dir_path / "GRABDA recordings" / "STN_mCherry" / "Fiber photometry_TDT" / "Varying durations",
    recording_type="GRABDA recordings_STN_mCherry",
    stimulus_location="STN_mCherry",
    protocol="Varying durations",
    stub_test=True,
)
```

With `stub_test=True` only the first second of each block is written, to the `nwb_stub` subfolder; this is a quick
way to check the metadata of a new cohort. `data_streams` turns data streams on or off for this call (see
[Data streams](data_streams.md)), and `overwrite=True` replaces an existing file.

To find the arguments of every session, `get_session_to_nwb_kwargs_per_session` in
`hadjas_2025/convert_all_sessions.py` returns them as a list, as the `convert` command uses them.
