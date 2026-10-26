# DANDI staging

The converted files are shared in [DANDI:001528](https://dandiarchive.org/dandiset/001528). Uploads go to the draft
of the dandiset; a published version is a fixed snapshot of the draft. Upload by hand, after reviewing the NWB files
and the conversion summary.

Each step takes `--dandi-instance`: `dandi` for the archive, `dandi-sandbox` for the
[sandbox](https://sandbox.dandiarchive.org), a separate test server where a copy of the dandiset can be tried first.
The dandiset ID defaults to `001528` (`--dandiset-id` to change it, for example for a sandbox dandiset).

## 1. Review the converted files

Before staging, check in the output folder:

- `conversion_summary.csv`: every session `converted`, no `CRITICAL` or `ERROR` inspector messages, and
  `herd_references` above 0.
- `inspector_reports/`: the NWB Inspector report of each file.
- A few files opened with PyNWB or Neurosift (see [NWB file structure](nwb_file_structure.md)).

## 2. Organize and validate

```bash
hadjas-2025 organize "<output folder>" "<dandiset folder>" --dandi-instance dandi
```

This downloads the dandiset metadata into `<dandiset folder>/001528`, copies the NWB files there with the names DANDI
expects (`sub-<subject>/sub-<subject>_ses-<session>.nwb`), and copies external video files next to them. The files of
the output folder are not changed. It then:

- validates the organized files and the dandiset metadata, as `dandi upload` would, and prints the errors;
- writes `draft_asset_report.csv` next to the dandiset folder, with the status of each draft asset:
  - `replaced`: the upload replaces it with a file at the same path.
  - `superseded`: a new file of the same subject and session has another path (for example a subject ID that was
    lower case). The upload adds the new file; the old asset stays on the draft until it is removed.
  - `not reconverted`: no new file for its subject and session.
  - `new`: an organized file that is not on the draft yet.

Run `organize` on an empty dandiset folder; it stops if the folder already holds organized files.

## 3. Upload

Set your DANDI API key (from your account page on the archive or the sandbox) in the environment:
`DANDI_API_KEY` for the archive, `DANDI_SANDBOX_API_KEY` for the sandbox. Then:

```bash
hadjas-2025 upload "<dandiset folder>" --dandi-instance dandi
```

This validates the organized folder again and uploads it to the draft. Nothing is uploaded if validation finds an
error. Superseded assets are not removed; remove them on the dandiset page or with `dandi delete` once the new files
are checked.

## Dandiset metadata

The name and description of the dandiset are kept in
`src/hnasko_lab_to_nwb/hadjas_2025/metadata/dandiset_description.md`, so that they are reviewed with the conversion.
Copy them to the dandiset metadata on the DANDI website when they change.
