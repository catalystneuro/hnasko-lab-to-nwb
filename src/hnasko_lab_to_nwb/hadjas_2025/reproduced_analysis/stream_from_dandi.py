"""Stream a session's NWB file from the DANDI archive for the reproduced analyses."""

# Standard library imports
import h5py

# Visualization
import remfile
from dandi.dandiapi import DandiAPIClient

# NWB and DANDI access
from pynwb import NWBHDF5IO


def load_nwb_from_dandi(dandiset_id, subject_id, session_id):
    """Open the NWB file of one session on the draft of a dandiset, streamed from S3.

    Parameters
    ----------
    dandiset_id : str
        The dandiset, e.g. "001528".
    subject_id : str
        The subject ID of the session.
    session_id : str
        The session ID, e.g. "varying_durations".

    Returns
    -------
    tuple[NWBFile, NWBHDF5IO]
        The NWB file and its reader; close the reader when done.

    Raises
    ------
    ValueError
        If the draft does not have exactly one file for the session.
    """
    pattern = f"sub-{subject_id}/sub-{subject_id}_ses-{session_id}*.nwb"

    with DandiAPIClient() as client:
        client.dandi_authenticate()
        assets = client.get_dandiset(dandiset_id, "draft").get_assets_by_glob(pattern=pattern, order="path")

        s3_urls = []
        for asset in assets:
            s3_url = asset.get_content_url(follow_redirects=1, strip_query=False)
            s3_urls.append(s3_url)

        if len(s3_urls) != 1:
            raise ValueError(f"Expected 1 file, found {len(s3_urls)} for pattern {pattern}")

        s3_url = s3_urls[0]

    file = remfile.File(s3_url)
    h5_file = h5py.File(file, "r")
    io = NWBHDF5IO(file=h5_file, load_namespaces=True)
    nwbfile = io.read()

    return nwbfile, io
