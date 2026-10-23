from pathlib import Path

import dandi.download
import dandi.organize
import dandi.upload
import pytest
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from hnasko_lab_to_nwb.hadjas_2025 import upload_to_DANDI
from hnasko_lab_to_nwb.hadjas_2025.upload_to_DANDI import organize_nwbfiles, upload_organized_files


@pytest.fixture
def fake_dandi(monkeypatch):
    """Replace the dandi download, organize and upload functions with fakes that record their arguments."""
    calls = dict()

    def download(urls, output_dir, **kwargs):
        calls["download"] = urls
        dandiset_path = f"{output_dir}/{urls.split('/')[-2]}"
        Path(dandiset_path).mkdir()
        (Path(dandiset_path) / "dandiset.yaml").write_text("identifier: DANDI:001528\n")

    def organize(paths, dandiset_path, **kwargs):
        calls["organize"] = dict(paths=paths, dandiset_path=dandiset_path, **kwargs)

    def upload(paths, dandi_instance, **kwargs):
        calls["upload"] = dict(paths=paths, dandi_instance=dandi_instance)

    monkeypatch.setattr(dandi.download, "download", download)
    monkeypatch.setattr(dandi.organize, "organize", organize)
    monkeypatch.setattr(dandi.upload, "upload", upload)
    return calls


def test_organize_copies_the_nwb_files_of_the_sandbox_draft_and_keeps_them(tmp_path, fake_dandi, monkeypatch):
    monkeypatch.setattr(upload_to_DANDI, "validate_organized_files", lambda dandiset_path: [])
    nwb_folder_path = tmp_path / "nwb"
    nwb_folder_path.mkdir()
    (nwb_folder_path / "sub-C0001_ses-varying_durations.nwb").touch()

    dandiset_path = organize_nwbfiles(
        nwb_folder_path=nwb_folder_path,
        dandiset_folder_path=tmp_path / "dandisets",
        dandiset_id="001528",
        dandi_instance="dandi-sandbox",
    )
    upload_organized_files(dandiset_path=dandiset_path, dandi_instance="dandi-sandbox")

    assert fake_dandi["download"] == "https://sandbox.dandiarchive.org/dandiset/001528/draft"
    assert fake_dandi["organize"]["files_mode"] == dandi.organize.FileOperationMode.COPY
    assert fake_dandi["organize"]["required_fields"] == ["session_id"]
    assert fake_dandi["upload"] == dict(paths=[str(tmp_path / "dandisets" / "001528")], dandi_instance="dandi-sandbox")
    assert (nwb_folder_path / "sub-C0001_ses-varying_durations.nwb").exists()


def test_organize_fails_on_a_dandiset_folder_organized_before(tmp_path, fake_dandi):
    organized_folder_path = tmp_path / "dandisets" / "001528" / "sub-C0001"
    organized_folder_path.mkdir(parents=True)
    (organized_folder_path / "sub-C0001_ses-varying-durations.nwb").touch()

    with pytest.raises(FileExistsError):
        organize_nwbfiles(
            nwb_folder_path=tmp_path / "nwb",
            dandiset_folder_path=tmp_path / "dandisets",
            dandiset_id="001528",
            dandi_instance="dandi",
        )


def test_unknown_dandi_instance_raises(tmp_path, fake_dandi):
    with pytest.raises(ValueError, match="Unknown DANDI instance"):
        upload_organized_files(dandiset_path=tmp_path, dandi_instance="sandbox")


def test_nothing_is_uploaded_if_a_file_or_the_dandiset_metadata_is_invalid(tmp_path, fake_dandi):
    dandiset_path = tmp_path / "001528"
    (dandiset_path / "sub-C0001").mkdir(parents=True)
    # no description, and an older schema version, as in the metadata of the 001528 draft
    (dandiset_path / "dandiset.yaml").write_text("identifier: DANDI:001528\nname: Hadjas 2025\nschemaVersion: 0.6.10\n")
    with NWBHDF5IO(dandiset_path / "sub-C0001" / "sub-C0001_ses-varying-durations.nwb", "w") as io:
        io.write(mock_NWBFile())  # no subject

    with pytest.raises(ValueError, match="2 validation errors") as error:
        upload_organized_files(dandiset_path=dandiset_path, dandi_instance="dandi-sandbox")

    assert "description\n  Field required" in str(error.value)
    assert "Subject is missing" in str(error.value)
    assert "upload" not in fake_dandi
