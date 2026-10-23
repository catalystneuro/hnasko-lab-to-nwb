from pathlib import Path

import dandi.download
import dandi.organize
import dandi.upload
import pytest

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


def test_organize_copies_the_nwb_files_of_the_sandbox_draft_and_keeps_them(tmp_path, fake_dandi):
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
